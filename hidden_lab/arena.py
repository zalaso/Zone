"""Arena locale BYOA v1. Gli agenti propongono; solo l'operatore esegue."""

import asyncio
from hashlib import sha256
import json
import re
import secrets

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from .arena_contract import VERSION, QUOTAS, contract, integer, label, quotas
from .arena_store import ArenaStore, fingerprint
from .backend_state import LabState, finish_run
from .backend_store import ConflictError, NotFoundError
from .identification import IDENTIFICATION_VERSION, identification_material, score_scientific_submission, validate_scientific_submission
from .protocol import ValidationError, apparatus, observation_times, require_keys
from .simulator import parse_config
from .local_worlds import digest


def install_arena(app, repository, operator_token, *, clock=None):
    # Lazy import avoids a circular module dependency; shared public projection is authoritative.
    from .backend import OPERATOR_TYPES, _body, _public_event, _version
    store = ArenaStore(repository, operator_token, clock)
    app.state.arena = store

    def headers(request):
        if request.headers.get("x-zone-arena-version") != VERSION:
            raise HTTPException(426, "Arena richiede X-Zone-Arena-Version: 1.")
        return request.headers.get("x-zone-token", "")

    def challenge(db, cid):
        if not isinstance(cid, str) or not re.fullmatch(r"[0-9a-f]{32}", cid):
            raise NotFoundError()
        row = db.execute("SELECT world_id,name,rules_json,closed FROM arena_challenges WHERE id=?", (cid,)).fetchone()
        if not row:
            raise NotFoundError()
        return {"challenge_id": cid, "world_id": row[0], "name": row[1],
                "rules": json.loads(row[2]), "closed": bool(row[3])}

    def public_challenge(value):
        return {**value, "apparatus": apparatus(value["rules"]["experiment_budget"])}

    def trial(db, sid, principal):
        row = db.execute("SELECT challenge_id,agent_id,cohort_hash FROM arena_trials WHERE session_id=?", (sid,)).fetchone()
        if not row or principal not in ("operator", row[1]):
            raise NotFoundError()
        stored = repository._read_session(db, sid)
        state = LabState(stored["events"], stored["record"]["config"]["experiment_budget"], stored["score"])
        ch = challenge(db, row[0])
        rules = rules_for(stored["record"], ch["rules"]["max_messages"], ch["rules"]["max_points"])
        if (row[2] != fingerprint(ch["rules"]) or rules != ch["rules"] or
                stored["events"][0]["message"] != apparatus(rules["experiment_budget"])):
            raise ValidationError("Cohort incompatibile: mondo, probe, budget o limiti cambiati.")
        return stored, state, ch, row[1]

    def rules_for(record, messages, points):
        if record["sha256"] != digest({key: value for key, value in record.items() if key != "sha256"}):
            raise ValidationError("Record mondo alterato.")
        return {"arena_version": VERSION, "world_hash": record["sha256"],
                "probes_hash": fingerprint(record["probes"]), "scorer_version": "identification-v1",
                "secret_grid_version": IDENTIFICATION_VERSION, "experiment_budget": record["config"]["experiment_budget"],
                "max_messages": messages, "max_points": points, "execution_policy": "exploration_only"}

    def status(db, sid, principal, *, events=False):
        stored, state, ch, aid = trial(db, sid, principal)
        value = {"session_id": sid, "challenge_id": ch["challenge_id"], "agent_id": aid,
                 **state.public_status(), "rules": ch["rules"],
                 "messages": sum(e["actor"] == "agent" for e in stored["events"]),
                 "observations": len(state.observations), "scores": state.score,
                 "account": store.agent(db, aid)}
        calls, invalid = db.execute("SELECT COUNT(*),COALESCE(SUM(status>=400),0) FROM arena_audit "
            "WHERE principal=? AND action LIKE ?", (aid, f"/v1/arena/sessions/{sid}/%")).fetchone()
        value["resources"] = {"agent_requests": calls, "invalid_requests": invalid,
                              "external_model_calls": None, "external_tokens": None, "external_cost": None}
        if events:
            value["events"] = [_public_event(e) for e in stored["events"]]
        return value

    @app.get("/v1/arena/contract")
    async def get_contract():
        return contract()

    @app.get("/v1/arena/challenges")
    async def get_challenges():
        with repository._connect() as db:
            return {"challenges": [public_challenge(challenge(db, row[0])) for row in
                                   db.execute("SELECT id FROM arena_challenges ORDER BY rowid").fetchall()]}

    @app.get("/v1/arena/agents")
    async def agents(request: Request):
        return store.read(headers(request), lambda db, p: {"agents": [
            {**store.agent(db, row[0]), "tokens": [{"token_id": tid, "expires_at": expiry, "revoked": bool(revoked)}
                for tid, expiry, revoked in db.execute("SELECT id,expires,revoked FROM arena_tokens WHERE agent_id=?", (row[0],))]}
            for row in db.execute("SELECT id FROM arena_agents ORDER BY rowid").fetchall()]}, operator=True)

    @app.get("/v1/arena/audit")
    async def audit(request: Request, after: int = 0):
        integer(after, 0, 2**63 - 1)
        def read(db, _p):
            rows = db.execute("SELECT seq,time,principal,action,status,key_hash FROM arena_audit WHERE seq>? ORDER BY seq LIMIT 100", (after,)).fetchall()
            return {"audit": [dict(zip(("seq", "time", "principal", "action", "status", "key_hash"), row)) for row in rows],
                    "next_after": rows[-1][0] if rows else after}
        return store.read(headers(request), read, operator=True)

    @app.get("/v1/arena/challenges/{cid}/trials")
    async def trials(cid: str, request: Request):
        def read(db, p):
            challenge(db, cid)
            rows = db.execute("SELECT session_id,agent_id FROM arena_trials WHERE challenge_id=? ORDER BY rowid", (cid,)).fetchall()
            return {"trials": [status(db, sid, p) for sid, aid in rows if p in ("operator", aid)]}
        return store.read(headers(request), read)

    @app.get("/v1/arena/sessions/{sid}")
    async def get_session(sid: str, request: Request):
        return store.read(headers(request), lambda db, p: status(db, sid, p, events=True))

    @app.get("/v1/arena/challenges/{cid}/leaderboard")
    async def leaderboard(cid: str, request: Request):
        def read(db, p):
            ch = challenge(db, cid)
            if not ch["closed"] and p != "operator":
                raise HTTPException(403, "Leaderboard disponibile agli agenti dopo la chiusura.")
            values = [status(db, row[0], "operator") for row in
                      db.execute("SELECT session_id FROM arena_trials WHERE challenge_id=? ORDER BY rowid", (cid,)).fetchall()]
            # One ranking per dimension; missing metrics never receive a synthetic value.
            dimensions = {
                "acceleration_rmse": ("prediction", "acceleration_rmse"),
                "interpolation_rmse": ("prediction", "by_category", "interpolation", "acceleration_rmse"),
                "extrapolation_rmse": ("prediction", "by_category", "extrapolation", "acceleration_rmse"),
                "functional_rmse": ("functional", "metrics", "acceleration_rmse"),
                "ast_nodes": ("complexity", "node_count"),
                "missed_dependencies": ("dependencies", "missed_count"),
                "spurious_dependencies": ("dependencies", "spurious_count"),
                "calibration_nll": ("calibration", "mean_gaussian_nll"),
            }
            boards = {}
            for name, path in dimensions.items():
                measured = []
                for value in values:
                    metric = value["scores"]
                    for key in path:
                        metric = metric.get(key) if isinstance(metric, dict) else None
                    if type(metric) in (int, float):
                        measured.append({"session_id": value["session_id"], "value": metric})
                measured.sort(key=lambda item: (item["value"], item["session_id"]))
                for index, item in enumerate(measured):
                    item["rank"] = 1 + sum(other["value"] < item["value"] for other in measured[:index])
                boards[name] = measured
            return {"challenge": public_challenge(ch), "dimensions": boards, "trials": values,
                    "notice": "Metriche separate, nessun punteggio combinato. Modello dichiarato, non attestato; costi esterni non misurati."}
        return store.read(headers(request), read)

    def action(db, principal, kind, resource, body):
        if kind == "challenges":
            require_keys(body, ("world_id", "name"), ("max_messages", "max_points"))
            if not isinstance(body["world_id"], str) or not re.fullmatch(r"w[0-9a-f]{16}", body["world_id"]):
                raise ValidationError("ID mondo non valido.")
            row = db.execute("SELECT record_json,manifest_json FROM worlds WHERE id=?", (body["world_id"],)).fetchone()
            if not row:
                raise NotFoundError()
            record, manifest = json.loads(row[0]), json.loads(row[1])
            if "builder_version" in manifest:
                raise ValidationError("Arena accetta solo mondi Forge, senza autore della legge.")
            if db.execute("SELECT 1 FROM events e JOIN sessions s ON s.id=e.session_id WHERE s.world_id=? "
                          "AND json_extract(e.message_json,'$.type')='reveal_recorded'", (body["world_id"],)).fetchone():
                raise ValidationError("Questo mondo è già stato rivelato; genera un mondo nuovo.")
            rules = rules_for(record, integer(body.get("max_messages", 30), 3, 100), integer(body.get("max_points", 9), 2, 25))
            cid = secrets.token_hex(16)
            db.execute("INSERT INTO arena_challenges VALUES(?,?,?,?,0)", (cid, body["world_id"], label(body["name"]), json.dumps(rules)))
            return 201, public_challenge(challenge(db, cid)), None
        if kind == "agents":
            require_keys(body, ("name", "model"), ("kind", "quotas", "ttl_seconds"))
            aid = secrets.token_hex(16)
            category = body.get("kind", "external")
            if category not in ("external", "offline_baseline"):
                raise ValidationError("Tipo agente non valido.")
            meta = {"name": label(body["name"]), "model": label(body["model"]), "kind": category, "model_verified": False}
            limits = quotas(body.get("quotas", QUOTAS))
            db.execute("INSERT INTO arena_agents(id,metadata_json,quotas_json) VALUES(?,?,?)", (aid, json.dumps(meta), json.dumps(limits)))
            issued = store.issue(db, aid, integer(body.get("ttl_seconds", 86400), 60, 2592000))
            return 201, {**store.agent(db, aid), **issued}, None
        if kind == "tokens":
            require_keys(body, (), ("ttl_seconds",))
            return 201, store.issue(db, resource, integer(body.get("ttl_seconds", 86400), 60, 2592000)), None
        if kind == "revoke":
            require_keys(body, ())
            if not db.execute("SELECT 1 FROM arena_tokens WHERE id=?", (resource,)).fetchone():
                raise NotFoundError()
            db.execute("UPDATE arena_tokens SET revoked=1 WHERE id=?", (resource,))
            return 200, {"token_id": resource, "revoked": True}, None
        if kind == "close":
            require_keys(body, ())
            ch = challenge(db, resource)
            states = [trial(db, row[0], "operator")[1] for row in
                      db.execute("SELECT session_id FROM arena_trials WHERE challenge_id=?", (resource,)).fetchall()]
            if ch["closed"] or not all(s.score is not None or s.stopped for s in states):
                raise ValidationError("Arresta o valuta tutti i trial prima di chiudere.")
            db.execute("UPDATE arena_challenges SET closed=1 WHERE id=?", (resource,))
            return 200, public_challenge(challenge(db, resource)), None
        if kind == "sessions":
            require_keys(body, ("challenge_id",))
            if principal == "operator":
                raise HTTPException(403, "Crea il trial con la credenziale dell'agente.")
            ch = challenge(db, body["challenge_id"])
            if ch["closed"]:
                raise ValidationError("Challenge chiusa.")
            account = store.agent(db, principal)
            if (account["quotas"]["experiments"] - account["usage"]["experiments"] < ch["rules"]["experiment_budget"] or
                    account["quotas"]["requests"] - account["usage"]["requests"] < ch["rules"]["max_messages"]):
                raise ValidationError("Quote account residue insufficienti per i limiti della challenge.")
            if db.execute("SELECT 1 FROM arena_trials WHERE challenge_id=? AND agent_id=?", (ch["challenge_id"], principal)).fetchone():
                raise ValidationError("Un solo trial per agente e challenge.")
            store.charge(db, principal, "sessions")
            sid = repository._insert_session(db, ch["world_id"], sha256(secrets.token_bytes(32)).hexdigest(),
                    apparatus(ch["rules"]["experiment_budget"]), {"mode": "arena", "managed_agent": False})
            db.execute("INSERT INTO arena_trials VALUES(?,?,?,?)", (sid, ch["challenge_id"], principal, fingerprint(ch["rules"])))
            return 201, status(db, sid, principal, events=True), None
        stored, state, ch, aid = trial(db, resource, principal)
        fields = {"messages": ("message",), "run": ("request_id",), "stop": ("reason",),
                  "submission": ("submission",), "score": (), "reveal": ("confirm",)}
        require_keys(body, ("expected_version", *fields[kind]))
        if state.version != _version(body["expected_version"]):
            raise ConflictError()
        if kind != "reveal" and ch["closed"]:
            raise ValidationError("Challenge chiusa.")
        if kind == "messages":
            message = state.accept_message(body["message"], "operator" if principal == "operator" else "agent")
            if principal != "operator" and sum(e["actor"] == "agent" for e in stored["events"]) >= ch["rules"]["max_messages"] - 1:
                raise ValidationError("Limite messaggi: riserva l'ultimo posto alla submission o arresta il trial.")
            if (message["type"] in ("operator_question", "operator_answer") or
                    message["type"] == "operator_decision" and message["action"] == "modify" or
                    message["type"] == "execution_mode" and message["mode"] != "exploration"):
                raise ValidationError("Arena v1: solo esplorazione, senza modifiche o suggerimenti teorici.")
            if message["type"] == "operator_decision":
                message["reason"] = "Decisione operativa Arena; nessun suggerimento teorico."
            experiment = message.get("experiment")
            if experiment and len(observation_times(experiment)) > ch["rules"]["max_points"]:
                raise ValidationError("Troppi punti di osservazione.")
            entries = [("operator" if principal == "operator" else "agent", message)]
            if message["type"] == "conclusion":
                entries.append(("apparatus", {"type": "probe_challenge", "world_id": stored["world_id"], "probes": stored["record"]["probes"]}))
            repository._append(db, resource, state.version, entries)
        elif kind == "run":
            started = state.start_run(body["request_id"])
            store.charge(db, aid, "experiments")
            version = repository._append(db, resource, state.version, [("operator", started)])
            return 202, status(db, resource, principal), ("run", resource, version, stored, started)
        elif kind == "stop":
            if state.stopped or state.revealed or state.score is not None or body["reason"] not in ("operator_stop", "interrupted_execution"):
                raise ValidationError("Arresto non disponibile.")
            repository._append(db, resource, state.version, [("apparatus", {"type": "investigation_stopped", "reason": body["reason"]})])
        elif kind in ("submission", "score"):
            if state.stopped or state.revealed or state.challenge is None or state.score is not None:
                raise ValidationError("Valutazione non disponibile.")
            if kind == "submission":
                if principal == "operator" or state.submission is not None:
                    raise ValidationError("Submission già congelata o ruolo non ammesso.")
                normalized = validate_scientific_submission(body["submission"], tuple(p["probe_id"] for p in state.challenge["probes"]))
                if sum(e["actor"] == "agent" for e in stored["events"]) >= ch["rules"]["max_messages"]:
                    raise ValidationError("Budget messaggi agente esaurito.")
                repository._append(db, resource, state.version, [("agent", {"type": "scientific_submission", **normalized})])
            elif state.submission is None:
                raise ValidationError("Nessuna submission congelata.")
            snapshot = repository._read_session(db, resource)
            return 202, status(db, resource, principal), ("score", resource, len(snapshot["events"]), snapshot, None)
        elif kind == "reveal":
            if not ch["closed"] or body["confirm"] != "reveal" or state.revealed:
                raise ValidationError("Reveal solo dopo chiusura, con conferma esplicita.")
            if db.execute("SELECT 1 FROM arena_challenges WHERE world_id=? AND closed=0", (stored["world_id"],)).fetchone():
                raise ValidationError("Un'altra challenge su questo mondo è ancora aperta.")
            repository._append(db, resource, state.version, [("apparatus", {"type": "reveal_recorded", "world_id": stored["world_id"], "manifest_hash": stored["record"]["sha256"]})])
        return 200, status(db, resource, principal), None

    async def mutate(request, kind, resource=""):
        supplied = headers(request)
        if resource and not re.fullmatch(r"[0-9a-f]{32}", resource):
            raise NotFoundError()
        try:
            body = await _body(request)
        except (ValidationError, HTTPException) as exc:
            code = exc.status_code if isinstance(exc, HTTPException) else 422
            def invalid_body(_db, _p):
                raise HTTPException(code, "Corpo JSON Arena non valido.")
            code, value, _work, _receipt = store.perform(supplied, request.headers.get("idempotency-key"),
                request.url.path, {"invalid_transport": code}, invalid_body)
            return JSONResponse(value, status_code=code)
        operator = kind in ("challenges", "agents", "tokens", "revoke", "close", "run", "stop", "score", "reveal")
        if kind == "messages":
            operator = isinstance(body.get("message"), dict) and body["message"].get("type") in OPERATOR_TYPES
        code, value, work, receipt = store.perform(supplied, request.headers.get("idempotency-key"), request.url.path, body,
            lambda db, p: action(db, p, kind, resource, body), operator=operator)
        if work:
            operation, sid, version, stored, started = work
            try:
                if operation == "run":
                    state = LabState(stored["events"], stored["record"]["config"]["experiment_budget"], stored["score"])
                    entries = await asyncio.to_thread(finish_run, parse_config(stored["record"]["config"]), started,
                                                      state.predictions.get(started["request_id"]))
                    def commit(db):
                        repository._append(db, sid, version, entries)
                        return status(db, sid, "operator")
                else:
                    record = stored["record"]
                    state = LabState(stored["events"], record["config"]["experiment_budget"], stored["score"])
                    scores, private_audit = await asyncio.to_thread(score_scientific_submission, state.submission,
                        record["probes"], parse_config(record["config"]).world,
                        identification_material(record["config"]["seed"], record["world_id"], record["sha256"]))
                    def commit(db):
                        repository._save_score(db, sid, version, scores, private_audit)
                        return status(db, sid, "operator")
                code, value = store.complete(receipt, commit)
            except Exception:
                # Durable receipt remains 202. Replaying it only returns state; never repeats a run.
                code, value = 503, {"detail": "Operazione interrotta. Leggi lo stato; arresta l'esecuzione o riprendi solo il punteggio."}
                store.interrupted(receipt)
        return JSONResponse(value, status_code=code)

    @app.post("/v1/arena/challenges")
    async def new_challenge(request: Request):
        return await mutate(request, "challenges")

    @app.post("/v1/arena/agents")
    async def new_agent(request: Request):
        return await mutate(request, "agents")

    @app.post("/v1/arena/agents/{aid}/tokens")
    async def issue_token(aid: str, request: Request):
        return await mutate(request, "tokens", aid)

    @app.post("/v1/arena/tokens/{tid}/revoke")
    async def revoke(tid: str, request: Request):
        return await mutate(request, "revoke", tid)

    @app.post("/v1/arena/challenges/{cid}/close")
    async def close(cid: str, request: Request):
        return await mutate(request, "close", cid)

    @app.post("/v1/arena/sessions")
    async def new_trial(request: Request):
        return await mutate(request, "sessions")

    @app.post("/v1/arena/sessions/{sid}/{kind}")
    async def session_action(sid: str, kind: str, request: Request):
        if kind not in ("messages", "run", "stop", "submission", "score", "reveal"):
            raise NotFoundError()
        return await mutate(request, kind, sid)

    @app.get("/v1/arena/sessions/{sid}/reveal")
    async def reveal(sid: str, request: Request):
        def read(db, p):
            stored, state, _ch, _aid = trial(db, sid, p)
            if not state.revealed:
                raise NotFoundError()
            return {"session_id": sid, "world": stored["record"], "audit": stored["audit"]}
        return store.read(headers(request), read, operator=True)

    return store
