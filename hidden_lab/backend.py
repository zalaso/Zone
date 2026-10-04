"""API locale sottile sopra protocollo, simulatore e identificazione esistenti."""

from collections import defaultdict, deque
from hashlib import sha256
import hmac
import os
import re
import secrets
from threading import Lock
import time

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from .agent_contract import PUBLIC_SHAPES, _project
from .backend_state import LabState, finish_run
from .backend_store import ConflictError, NotFoundError, SessionRepository, SQLiteRepository
from .identification import (identification_material, score_scientific_submission,
                             validate_scientific_submission)
from .protocol import (MAX_MESSAGE_BYTES, ValidationError, apparatus, decode,
                       identifier, require_keys)
from .simulator import parse_config

SESSION_ID = re.compile(r"[0-9a-f]{32}\Z")
OPERATOR_TYPES = frozenset(("operator_decision", "operator_answer", "execution_mode"))
PROBE_SHAPE = {"probe_id": None, "category": None, "x": None, "y": None, "vx": None, "vy": None}
EXTRA_SHAPES = {
    "probe_challenge": {"world_id": None, "probes": [PROBE_SHAPE]},
    "scientific_submission": {"predictions": [{"probe_id": None, "ax": None, "ay": None}],
                              "law_ast_json": None, "uncertainty_sigma": [None]},
    "reveal_recorded": {"world_id": None, "manifest_hash": None},
}


class RateLimiter:
    """Limite locale per IP; un deployment multi-processo richiederà uno store condiviso."""

    def __init__(self, *, read=120, write=30, run=10, window=60, clock=None):
        self.limits = {"read": read, "write": write, "run": run}
        self.window = window
        self.clock = clock or time.monotonic
        self.entries = defaultdict(deque)
        self.lock = Lock()

    def allow(self, address, bucket):
        now = self.clock()
        key = (address, bucket)
        with self.lock:
            queue = self.entries[key]
            while queue and queue[0] <= now - self.window:
                queue.popleft()
            if len(queue) >= self.limits[bucket]:
                return False
            queue.append(now)
            return True


def _public_event(event):
    message = event["message"]
    kind = message["type"]
    if kind == "result_recorded":
        # Scores are built by the trusted scorer, never copied from request bodies.
        projected = {"type": kind, "scores": message["scores"]}
    else:
        shape = EXTRA_SHAPES.get(kind, PUBLIC_SHAPES.get(kind))
        if shape is None:
            raise ValidationError("Tipo evento non pubblicabile.")
        projected = {"type": kind, **_project(message, shape)}
    return {"seq": event["seq"], "actor": event["actor"], "message": projected}


async def _body(request):
    if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
        raise HTTPException(415, "È richiesto application/json.")
    chunks, size = [], 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > MAX_MESSAGE_BYTES:
            raise HTTPException(413, "Corpo della richiesta troppo grande.")
        chunks.append(chunk)
    try:
        value = decode(b"".join(chunks).decode("utf-8"))
    except UnicodeDecodeError:
        raise HTTPException(422, "JSON UTF-8 non valido.") from None
    if not isinstance(value, dict):
        raise ValidationError("È richiesto un oggetto JSON.")
    return value


def _version(value):
    if type(value) is not int or value < 1:
        raise ValidationError("Versione attesa non valida.")
    return value


def create_app(db_path=None, *, worlds=(), repository: SessionRepository | None = None,
               operator_token=None, rate_limiter=None):
    """Costruisce un'app locale; repository iniettabile e nessun client LLM."""
    token = operator_token if operator_token is not None else os.environ.get("ZONE_OPERATOR_TOKEN")
    if not isinstance(token, str) or len(token) < 32:
        raise ValueError("Imposta ZONE_OPERATOR_TOKEN con almeno 32 caratteri casuali.")
    if repository is None:
        if db_path is None:
            raise ValueError("Percorso SQLite mancante.")
        repository = SQLiteRepository(db_path, worlds)
    limiter = rate_limiter or RateLimiter()
    app = FastAPI(title="Zone local backend", version="1.0", docs_url=None, redoc_url=None)

    @app.exception_handler(ValidationError)
    async def validation_error(_request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=422)

    @app.exception_handler(ConflictError)
    async def conflict_error(_request, _exc):
        return JSONResponse({"detail": "Versione obsoleta o azione già registrata."}, status_code=409)

    @app.exception_handler(NotFoundError)
    async def not_found_error(_request, _exc):
        return JSONResponse({"detail": "Risorsa non trovata."}, status_code=404)

    @app.middleware("http")
    async def limit_requests(request, call_next):
        if request.url.path.startswith("/v1/"):
            bucket = ("run" if request.url.path.endswith("/run") and request.method == "POST" else
                      "read" if request.method in ("GET", "HEAD") else "write")
            address = request.client.host if request.client else "unknown"
            if not limiter.allow(address, bucket):
                return JSONResponse({"detail": "Limite di richieste raggiunto."}, status_code=429,
                                    headers={"Retry-After": str(limiter.window)})
        return await call_next(request)

    def authorize(request, stored, role):
        supplied = request.headers.get("x-zone-token", "")
        if len(supplied) > 256:
            raise HTTPException(401, "Token mancante o non valido.")
        valid = (hmac.compare_digest(supplied, token) if role == "operator" else
                 hmac.compare_digest(sha256(supplied.encode()).hexdigest(), stored["agent_token_hash"]))
        if not valid:
            raise HTTPException(401, "Token mancante o non valido.")

    def load(session_id):
        if not SESSION_ID.fullmatch(session_id):
            raise NotFoundError()
        stored = repository.read_session(session_id)
        state = LabState(stored["events"], stored["record"]["config"]["experiment_budget"], stored["score"])
        return stored, state

    def response(session_id):
        _, state = load(session_id)
        return {"session_id": session_id, **state.public_status()}

    def compute_score(session_id, stored, state):
        record = stored["record"]
        submission = state.submission
        material = identification_material(record["config"]["seed"], record["world_id"], record["sha256"])
        scores, audit = score_scientific_submission(submission, record["probes"],
            parse_config(record["config"]).world, material)
        repository.save_score(session_id, state.version, scores, audit)
        return scores

    @app.get("/v1/worlds")
    async def worlds_public():
        return {"worlds": repository.list_worlds()}

    @app.post("/v1/sessions", status_code=201)
    async def create_session(request: Request):
        authorize(request, None, "operator")
        body = await _body(request)
        require_keys(body, ("world_id",))
        if type(body["world_id"]) is not str or not re.fullmatch(r"w[0-9a-f]{16}", body["world_id"]):
            raise ValidationError("ID mondo non valido.")
        manifest = next((item for item in repository.list_worlds() if item["world_id"] == body["world_id"]), None)
        if manifest is None:
            raise NotFoundError()
        agent_token = secrets.token_urlsafe(32)
        session_id = repository.create_session(body["world_id"], sha256(agent_token.encode()).hexdigest(),
                                               apparatus(manifest["experiment_budget"]))
        return {**response(session_id), "agent_token": agent_token}

    @app.get("/v1/sessions/{session_id}")
    async def get_status(session_id: str):
        return response(session_id)

    @app.get("/v1/sessions/{session_id}/events")
    async def get_events(session_id: str, after: int = 0):
        if type(after) is not int or after < 0:
            raise ValidationError("Cursore eventi non valido.")
        stored, state = load(session_id)
        selected = [event for event in stored["events"] if event["seq"] > after][:100]
        return {"session_id": session_id, "version": state.version,
                "events": [_public_event(event) for event in selected],
                "next_after": selected[-1]["seq"] if selected else after}

    @app.post("/v1/sessions/{session_id}/messages")
    async def post_message(session_id: str, request: Request):
        stored, state = load(session_id)
        body = await _body(request)
        require_keys(body, ("expected_version", "message"))
        kind = body["message"].get("type") if isinstance(body["message"], dict) else None
        role = "operator" if kind in OPERATOR_TYPES else "agent"
        authorize(request, stored, role)
        expected = _version(body["expected_version"])
        if state.version != expected:
            raise ConflictError()
        message = state.accept_message(body["message"], role)
        entries = [(role, message)]
        if message["type"] == "conclusion":
            entries.append(("apparatus", {"type": "probe_challenge", "world_id": stored["world_id"],
                                          "probes": stored["record"]["probes"]}))
        repository.append(session_id, expected, entries)
        return response(session_id)

    @app.post("/v1/sessions/{session_id}/run")
    async def run_experiment(session_id: str, request: Request):
        stored, state = load(session_id)
        authorize(request, stored, "operator")
        body = await _body(request)
        require_keys(body, ("expected_version", "request_id"))
        expected = _version(body["expected_version"])
        if state.version != expected:
            raise ConflictError()
        started = state.start_run(body["request_id"])
        started_version = repository.append(session_id, expected, [("operator", started)])
        config = parse_config(stored["record"]["config"])
        entries = finish_run(config, started, state.predictions.get(started["request_id"]))
        repository.append(session_id, started_version, entries)
        return response(session_id)

    @app.post("/v1/sessions/{session_id}/stop")
    async def stop_session(session_id: str, request: Request):
        stored, state = load(session_id)
        authorize(request, stored, "operator")
        body = await _body(request)
        require_keys(body, ("expected_version", "reason"))
        expected = _version(body["expected_version"])
        if state.version != expected:
            raise ConflictError()
        if state.closed or body["reason"] not in ("operator_stop", "interrupted_execution"):
            raise ValidationError("Arresto non disponibile.")
        repository.append(session_id, expected, [("apparatus", {"type": "investigation_stopped",
                                                   "reason": body["reason"]})])
        return response(session_id)

    @app.post("/v1/sessions/{session_id}/submission")
    async def post_submission(session_id: str, request: Request):
        stored, state = load(session_id)
        authorize(request, stored, "agent")
        body = await _body(request)
        require_keys(body, ("expected_version", "submission"))
        expected = _version(body["expected_version"])
        if state.version != expected:
            raise ConflictError()
        if state.challenge is None or state.submission is not None or state.revealed:
            raise ValidationError("Submission non disponibile prima della conclusione o già registrata.")
        normalized = validate_scientific_submission(body["submission"],
            tuple(probe["probe_id"] for probe in state.challenge["probes"]))
        repository.append(session_id, expected, [("agent", {"type": "scientific_submission", **normalized})])
        stored, state = load(session_id)
        compute_score(session_id, stored, state)
        return response(session_id)

    @app.post("/v1/sessions/{session_id}/score")
    async def resume_score(session_id: str, request: Request):
        stored, state = load(session_id)
        authorize(request, stored, "operator")
        body = await _body(request)
        require_keys(body, ("expected_version",))
        if state.version != _version(body["expected_version"]):
            raise ConflictError()
        if state.submission is None or state.score is not None or state.revealed:
            raise ValidationError("Nessuna valutazione in attesa.")
        compute_score(session_id, stored, state)
        return response(session_id)

    @app.get("/v1/sessions/{session_id}/result")
    async def get_result(session_id: str):
        _, state = load(session_id)
        if state.score is None:
            raise NotFoundError()
        return {"session_id": session_id, "scores": state.score}

    @app.post("/v1/sessions/{session_id}/reveal")
    async def reveal(session_id: str, request: Request):
        stored, state = load(session_id)
        authorize(request, stored, "operator")
        body = await _body(request)
        require_keys(body, ("expected_version", "confirm"))
        if state.version != _version(body["expected_version"]):
            raise ConflictError()
        if body["confirm"] != "reveal" or state.revealed or not (state.score is not None or state.stopped):
            raise ValidationError("Reveal disponibile solo dopo punteggio o arresto, con conferma esplicita.")
        repository.append(session_id, state.version, [("apparatus", {"type": "reveal_recorded",
            "world_id": stored["world_id"], "manifest_hash": stored["record"]["sha256"]})])
        return {"session_id": session_id, "world": stored["record"], "audit": stored["audit"]}

    @app.get("/v1/sessions/{session_id}/reveal")
    async def get_reveal(session_id: str, request: Request):
        stored, state = load(session_id)
        authorize(request, stored, "operator")
        if not state.revealed:
            raise NotFoundError()
        return {"session_id": session_id, "world": stored["record"], "audit": stored["audit"]}

    return app
