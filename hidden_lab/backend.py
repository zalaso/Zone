"""API locale sottile sopra protocollo, simulatore e identificazione esistenti."""

from collections import defaultdict, deque
import asyncio
from dataclasses import replace
from datetime import datetime, timezone
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
                       observation_times, require_keys)
from .local_worlds import build_world, digest
from .provider_base import AgentSettings, ProviderError
from .simulator import parse_config
from .web_agent import OfflineLabClient, build_web_request, decode_reply, safe_generation, safe_metadata
from .world_forge import generate_world

SESSION_ID = re.compile(r"[0-9a-f]{32}\Z")
OPERATOR_TYPES = frozenset(("operator_decision", "operator_answer", "execution_mode"))
PROBE_SHAPE = {"probe_id": None, "category": None, "x": None, "y": None, "vx": None, "vy": None}
EXTRA_SHAPES = {
    "integrity_flagged": {"reason": None},
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
               operator_token=None, rate_limiter=None, agent_client=None, agent_settings=None,
               day_clock=None, integrity_packs=(), static_dir=None):
    """App locale: baseline offline predefinita, provider reale solo se iniettato esplicitamente."""
    token = operator_token if operator_token is not None else os.environ.get("ZONE_OPERATOR_TOKEN")
    if not isinstance(token, str) or len(token) < 32:
        raise ValueError("Imposta ZONE_OPERATOR_TOKEN con almeno 32 caratteri casuali.")
    if repository is None:
        if db_path is None:
            raise ValueError("Percorso SQLite mancante.")
        repository = SQLiteRepository(db_path, worlds)
    limiter = rate_limiter or RateLimiter()
    if integrity_packs:
        if not isinstance(repository, SQLiteRepository):
            raise ValueError("I pacchetti integrità richiedono SQLiteRepository.")
        from .integrity_store import IntegrityCatalog
        from .integrity_suite import validate_pack
        for pack in integrity_packs:
            IntegrityCatalog(repository).import_pack(validate_pack(pack))
    client = agent_client or OfflineLabClient()
    settings = agent_settings or AgentSettings("offline-affine-v1")
    day_clock = day_clock or (lambda: datetime.now(timezone.utc).date())
    in_flight = {}
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
        if request.url.path.startswith(("/v1/", "/health/")):
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
        valid = (hmac.compare_digest(supplied.encode(), token.encode()) if role == "operator" else
                 hmac.compare_digest(sha256(supplied.encode()).hexdigest(), stored["agent_token_hash"]))
        if not valid:
            raise HTTPException(401, "Token mancante o non valido.")

    def load(session_id):
        if not SESSION_ID.fullmatch(session_id):
            raise NotFoundError()
        stored = repository.read_session(session_id)
        if stored["profile"].get("mode") == "arena":
            # Arena histories and credentials must never bypass ownership/version checks.
            raise NotFoundError()
        state = LabState(stored["events"], stored["record"]["config"]["experiment_budget"], stored["score"])
        return stored, state

    def response(session_id):
        stored, state = load(session_id)
        profile = stored["profile"]
        return {"session_id": session_id, **state.public_status(),
                **{key: profile.get(key) for key in ("mode", "managed_agent", "participant", "match_id")},
                "agent": ({**profile["agent"], "calls": len(stored["calls"]),
                           "turns": agent_turns(stored),
                           "invalid_responses": sum(c["outcome"] == "invalid" for c in stored["calls"])}
                          if profile.get("managed_agent") else None)}

    def agent_turns(stored):
        return sum(e["actor"] == "agent" for e in stored["events"])

    def agent_profile():
        return {"mode": "watch_agent", "managed_agent": True,
                "agent": {"provider": client.provider, "model": settings.model,
                          "real_model": client.provider != "offline_baseline", "settings": settings.to_dict(),
                          "generation_settings": safe_generation(client)}}

    def match_records(stored):
        match_id = stored["profile"].get("match_id")
        if not match_id:
            return None
        match = repository.read_match(match_id)
        records = [load(match[key]) for key in ("human_session_id", "agent_session_id")]
        human, agent = records[0][0], records[1][0]
        expected = {"world_hash": human["record"]["sha256"], "probes_hash": digest(human["record"]["probes"]),
                    "apparatus_hash": digest(human["events"][0]["message"]),
                    "max_points": agent["profile"]["agent"]["settings"]["max_points"],
                    "max_turns": agent["profile"]["agent"]["settings"]["max_turns"],
                    "experiment_budget": human["record"]["config"]["experiment_budget"]}
        if (human["record"] != agent["record"] or human["events"][0] != agent["events"][0]
                or match["rules"] != expected):
            raise ValidationError("Confronto incompatibile: mondo, probe, budget o limiti diversi.")
        return match, records

    def mode_guard(stored, message):
        paired = match_records(stored)
        profile = stored["profile"]
        limits = paired[0]["rules"] if paired else settings.to_dict() if profile.get("managed_agent") else None
        if limits:
            if message["type"] not in OPERATOR_TYPES and agent_turns(stored) >= limits["max_turns"]:
                raise ValidationError("Limite turni raggiunto; arresta l'indagine.")
            experiment = message.get("experiment", message.get("modified_experiment"))
            if experiment and len(observation_times(experiment)) > limits["max_points"]:
                raise ValidationError("Troppi punti di osservazione per questa modalità.")
        if paired:
            if (message["type"] in ("operator_question", "operator_answer") or
                    message["type"] == "operator_decision" and message["action"] != "approve" or
                    message["type"] == "execution_mode" and message["mode"] != "exploration"):
                raise ValidationError("Human vs AI: solo approvazione ed esplorazione, senza suggerimenti teorici.")
            if message["type"] == "operator_decision":
                message["reason"] = "Approvazione operativa; nessun suggerimento teorico."

    def score_when_ready(session_id):
        stored, state = load(session_id)
        paired = match_records(stored)
        if paired:
            if not all(s.submission is not None and not s.stopped for _, s in paired[1]):
                return False
            for record, snapshot in paired[1]:
                if snapshot.score is None:
                    compute_score(record["id"], record, snapshot)
        elif state.score is None:
            compute_score(session_id, stored, state)
        return True

    def append_agent_message(session_id, stored, state, message):
        mode_guard(stored, message)
        entries = [("agent", message)]
        if message["type"] == "conclusion":
            entries.append(("apparatus", {"type": "probe_challenge", "world_id": stored["world_id"],
                                          "probes": stored["record"]["probes"]}))
        repository.append(session_id, state.version, entries)

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

    @app.get("/v1/modes")
    async def modes_public():
        return {"modes": ["scientist", "human_vs_ai", "watch_agent", "world_of_day", "build_universe"],
                "agent": agent_profile()["agent"]}

    @app.get("/v1/worlds/daily")
    async def daily():
        day = day_clock()
        manifest = daily_manifest(day)
        return {"day": day.isoformat(), "timezone": "UTC", "world": manifest}

    def daily_manifest(day):
        return repository.daily_world(day.isoformat(), lambda: generate_world(
            secrets.randbits(128), (day.toordinal() % 5) + 1, 3))

    @app.post("/v1/worlds/build", status_code=201)
    async def build_universe(request: Request):
        authorize(request, None, "operator")
        body = await _body(request)
        require_keys(body, ("law", "budget"), ("seed",))
        return {"world": repository.register_world(build_world(body["law"], body["budget"], body.get("seed"))),
                "notice": "L'autore conosce la legge: mondo escluso da Human vs AI."}

    @app.post("/v1/worlds/generate", status_code=201)
    async def forge_universe(request: Request):
        authorize(request, None, "operator")
        body = await _body(request)
        require_keys(body, ("level", "budget"), ("seed",))
        return {"world": repository.register_world(generate_world(body.get("seed"), body["level"], body["budget"]))}

    def find_world(body):
        if type(body["world_id"]) is not str or not re.fullmatch(r"w[0-9a-f]{16}", body["world_id"]):
            raise ValidationError("ID mondo non valido.")
        manifest = next((item for item in repository.list_worlds() if item["world_id"] == body["world_id"]), None)
        if manifest is None:
            raise NotFoundError()
        if manifest.get("integrity", {}).get("split") == "test":
            raise ValidationError("Il test privato è riservato alle challenge Arena.")
        return manifest

    @app.post("/v1/matches", status_code=201)
    async def create_match(request: Request):
        authorize(request, None, "operator")
        body = await _body(request)
        require_keys(body, ("world_id",))
        manifest = find_world(body)
        if "builder_version" in manifest:
            raise ValidationError("Un mondo costruito dall'autore non è una challenge cieca.")
        human_token, hidden_token = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        message = apparatus(manifest["experiment_budget"])
        # Probe identici a quelli del record registrato, senza pubblicarli prima del freeze.
        match = repository.create_match(body["world_id"], sha256(human_token.encode()).hexdigest(),
            sha256(hidden_token.encode()).hexdigest(), message, agent_profile(),
            {"world_hash": manifest["sha256"], "probes_hash": digest(repository.read_world(body["world_id"])["probes"]),
             "apparatus_hash": digest(message), "max_points": settings.max_points,
             "max_turns": settings.max_turns, "experiment_budget": manifest["experiment_budget"]})
        return {**match, "human_agent_token": human_token, "human": response(match["human_session_id"]),
                "agent": response(match["agent_session_id"])}

    @app.get("/v1/matches/{match_id}")
    async def get_match(match_id: str):
        if not SESSION_ID.fullmatch(match_id):
            raise NotFoundError()
        match = repository.read_match(match_id)
        paired = match_records(load(match["human_session_id"])[0])
        complete = all(state.score is not None for _, state in paired[1])
        participants = {}
        for name, (stored, state) in zip(("human", "agent"), paired[1]):
            participants[name] = {**response(stored["id"]), "scores": state.score if complete else None,
                "observations": len(state.observations), "messages": agent_turns(stored)}
        return {**match, "complete": complete, **participants}

    @app.post("/v1/sessions", status_code=201)
    async def create_session(request: Request):
        authorize(request, None, "operator")
        body = await _body(request)
        require_keys(body, ("world_id",), ("mode",))
        manifest = find_world(body)
        mode = body.get("mode", "scientist")
        if mode not in ("scientist", "watch_agent", "world_of_day"):
            raise ValidationError("Modalità non valida.")
        if mode == "world_of_day" and manifest["world_id"] != daily_manifest(day_clock())["world_id"]:
            raise ValidationError("Seleziona il mondo del giorno UTC corrente.")
        profile = agent_profile() if mode == "watch_agent" else {"mode": mode, "managed_agent": False}
        agent_token = secrets.token_urlsafe(32)
        session_id = repository.create_session(body["world_id"], sha256(agent_token.encode()).hexdigest(),
                                               apparatus(manifest["experiment_budget"]), profile)
        return {**response(session_id), "agent_token": None if profile["managed_agent"] else agent_token}

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
        if role == "agent" and stored["profile"].get("managed_agent"):
            raise ValidationError("Agente gestito: usa il passo agente, senza messaggi manuali.")
        expected = _version(body["expected_version"])
        if state.version != expected:
            raise ConflictError()
        message = state.accept_message(body["message"], role)
        mode_guard(stored, message)
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
        if (state.stopped or state.revealed or state.score is not None
                or body["reason"] not in ("operator_stop", "interrupted_execution")):
            raise ValidationError("Arresto non disponibile.")
        repository.append(session_id, expected, [("apparatus", {"type": "investigation_stopped",
                                                   "reason": body["reason"]})])
        return response(session_id)

    @app.post("/v1/sessions/{session_id}/submission")
    async def post_submission(session_id: str, request: Request):
        stored, state = load(session_id)
        authorize(request, stored, "agent")
        if stored["profile"].get("managed_agent"):
            raise ValidationError("La submission dell'agente gestito passa dal passo agente.")
        body = await _body(request)
        require_keys(body, ("expected_version", "submission"))
        expected = _version(body["expected_version"])
        if state.version != expected:
            raise ConflictError()
        if state.challenge is None or state.submission is not None or state.revealed or state.stopped:
            raise ValidationError("Submission non disponibile prima della conclusione o già registrata.")
        normalized = validate_scientific_submission(body["submission"],
            tuple(probe["probe_id"] for probe in state.challenge["probes"]))
        mode_guard(stored, {"type": "scientific_submission", **normalized})
        repository.append(session_id, expected, [("agent", {"type": "scientific_submission", **normalized})])
        score_when_ready(session_id)
        return response(session_id)

    @app.post("/v1/sessions/{session_id}/score")
    async def resume_score(session_id: str, request: Request):
        stored, state = load(session_id)
        authorize(request, stored, "operator")
        body = await _body(request)
        require_keys(body, ("expected_version",))
        if state.version != _version(body["expected_version"]):
            raise ConflictError()
        if state.submission is None or state.score is not None or state.revealed or state.stopped:
            raise ValidationError("Nessuna valutazione in attesa.")
        if not score_when_ready(session_id):
            raise ValidationError("Human vs AI: attendi la submission di entrambi prima dei punteggi.")
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
        paired = match_records(stored)
        if paired and not all(s.score is not None or s.stopped for _, s in paired[1]):
            raise ValidationError("Reveal bloccato fino alla fine di entrambe le indagini.")
        if isinstance(repository, SQLiteRepository) and app.state.arena.world_open(stored["world_id"]):
            raise ValidationError("Reveal bloccato: una challenge Arena sul mondo è ancora aperta.")
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

    @app.get("/v1/sessions/{session_id}/agent/audit")
    async def agent_audit(session_id: str, request: Request):
        stored, _ = load(session_id)
        authorize(request, stored, "operator")
        return {"session_id": session_id, "calls": stored["calls"]}

    @app.post("/v1/sessions/{session_id}/agent/step")
    async def agent_step(session_id: str, request: Request):
        stored, state = load(session_id)
        authorize(request, stored, "operator")
        body = await _body(request)
        require_keys(body, ("expected_version",))
        if state.version != _version(body["expected_version"]):
            raise ConflictError()
        if not stored["profile"].get("managed_agent") or state.status() not in (
                "discovering", "awaiting_prediction", "awaiting_submission"):
            raise ValidationError("Passo agente non disponibile: serve prima l'azione dell'operatore.")
        if stored["profile"]["agent"] != agent_profile()["agent"]:
            raise ValidationError("Configurazione agente cambiata dopo l'avvio; ripristina le impostazioni originali.")
        paired = match_records(stored)
        if paired and paired[1][0][1].submission is None:
            raise ValidationError("Consegna prima la risposta umana; le storie restano separate.")
        if agent_turns(stored) >= settings.max_turns:
            raise ValidationError("Limite turni raggiunto; arresta l'indagine.")
        previous = in_flight.get(session_id)
        if previous is not None and not previous.done():
            raise ConflictError()
        # Reserve this step before yielding: two concurrent clicks cannot start two calls.
        marker = asyncio.get_running_loop().create_future()
        in_flight[session_id] = marker
        task = None
        try:
            for attempt in range(settings.max_corrections + 1):
                stored, state = load(session_id)
                if state.version != body["expected_version"]:
                    raise ConflictError()
                call_index = repository.reserve_call(session_id, state.version, settings.max_calls)
                audit = {"provider": client.provider, "model": settings.model, "settings": settings.to_dict(),
                         "sdk_version": getattr(client, "sdk_version", None),
                         "generation_settings": safe_generation(client)}
                try:
                    payload = build_web_request(stored["events"], settings, state,
                        settings.max_calls - call_index, settings.max_turns - agent_turns(stored), paired=bool(paired))
                    if attempt:
                        payload = replace(payload, context={**payload.context,
                            "correction": "Risposta precedente non valida. Rispetta contratto, fase e limiti pubblici."})
                    if payload.size_bytes() > settings.max_input_bytes:
                        raise ValidationError("Storia pubblica oltre il limite di input.")
                    audit.update(payload.contract_fingerprints())
                    task = asyncio.create_task(asyncio.to_thread(client.complete, payload))
                    reply = await asyncio.wait_for(asyncio.shield(task), timeout=settings.timeout)
                    audit.update(safe_metadata(reply))
                    if len(reply.text.encode("utf-8")) > MAX_MESSAGE_BYTES:
                        raise ValidationError("Risposta agente troppo grande.")
                    raw = decode_reply(reply, payload.allowed_types)
                    if raw["type"] == "scientific_submission":
                        normalized = validate_scientific_submission({k: v for k, v in raw.items() if k != "type"},
                            tuple(p["probe_id"] for p in state.challenge["probes"]))
                        message = {"type": "scientific_submission", **normalized}
                    else:
                        message = state.accept_message(raw, "agent")
                    append_agent_message(session_id, stored, state, message)
                except (TimeoutError, ProviderError) as exc:
                    repository.finish_call(session_id, call_index, "error",
                                           {**audit, "error": "timeout" if isinstance(exc, TimeoutError) else exc.code})
                    raise HTTPException(503, "Chiamata agente non riuscita; nessun esperimento eseguito. Riprova esplicitamente.") from None
                except ValidationError:
                    repository.finish_call(session_id, call_index, "invalid", audit)
                    if attempt == settings.max_corrections:
                        raise ValidationError("Tentativi di correzione esauriti; nessun esperimento eseguito.") from None
                    continue
                except ConflictError:
                    repository.finish_call(session_id, call_index, "stale", audit)
                    raise
                except asyncio.CancelledError:
                    repository.finish_call(session_id, call_index, "interrupted", audit)
                    raise
                except Exception:
                    repository.finish_call(session_id, call_index, "error", {**audit, "error": "provider_error"})
                    raise HTTPException(503, "Errore agente; nessun esperimento eseguito.") from None
                repository.finish_call(session_id, call_index, "accepted", audit)
                if message["type"] == "scientific_submission":
                    score_when_ready(session_id)
                return response(session_id)
        finally:
            if task is not None and not task.done():
                # A timed-out worker may finish late; its reply is never committed.
                in_flight[session_id] = task
                task.add_done_callback(lambda completed: completed.exception() if not completed.cancelled() else None)
            else:
                marker.set_result(None)
                in_flight.pop(session_id, None)

    if isinstance(repository, SQLiteRepository):
        from .arena import install_arena
        install_arena(app, repository, token)
    from .runtime_ops import install_operations
    install_operations(app, repository)
    if static_dir is not None:
        from .static_web import mount_web
        mount_web(app, static_dir)
    return app
