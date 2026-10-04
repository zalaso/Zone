"""Demo Arena in-process: baseline pubblica e operatore simulato, nessuna rete."""

import json
from pathlib import Path
import secrets

from .protocol import ValidationError


def add_parser(commands):
    arena = commands.add_parser("arena", help="Zone Arena BYOA v1 locale")
    sub = arena.add_subparsers(dest="arena_command", required=True)
    demo = sub.add_parser("demo", help="Ciclo offline completo con operatore simulato, senza chiamate LLM")
    demo.add_argument("--db", type=Path, required=True, help="Nuovo database, non deve esistere")
    demo.add_argument("--world", type=Path, required=True, help="Record Forge privato, solo per il server")


def run_command(args):
    from fastapi.testclient import TestClient
    from .arena_client import ArenaClient, model_request
    from .backend import RateLimiter, create_app
    from .provider_base import AgentSettings
    from .web_agent import OfflineLabClient, decode_reply
    from .world_forge import read_world
    if args.db.exists():
        raise ValidationError("La demo richiede un nuovo database.")
    record = read_world(args.world)
    operator_token = secrets.token_urlsafe(32)
    app = create_app(args.db, worlds=[record], operator_token=operator_token,
                     rate_limiter=RateLimiter(read=10000, write=10000, run=10000))
    with TestClient(app) as transport:
        operator = ArenaClient(transport, operator_token)
        challenge = operator.write("challenges", {"world_id": record["world_id"], "name": "Demo offline Arena"}, "demo-challenge")
        issued = operator.write("agents", {"name": "Baseline affine pubblica", "model": "offline-affine-v1", "kind": "offline_baseline"}, "demo-register")
        agent = ArenaClient(transport, issued["token"])
        snapshot = agent.write("sessions", {"challenge_id": challenge["challenge_id"]}, "demo-trial")
        sid, calls, step = snapshot["session_id"], 0, 0
        settings, baseline = AgentSettings("offline-affine-v1"), OfflineLabClient()
        while snapshot["status"] != "scored":
            step += 1
            if step > 50:
                raise ValidationError("Demo oltre il limite di passi.")
            phase = snapshot["status"]
            extra = {}
            if phase in ("discovering", "awaiting_submission"):
                if calls >= settings.max_calls:
                    raise ValidationError("Budget baseline esaurito.")
                request = model_request(snapshot, settings, settings.max_calls - calls)
                message = decode_reply(baseline.complete(request), request.allowed_types)
                calls += 1
                if phase == "awaiting_submission":
                    endpoint, extra = "submission", {"submission": {k: v for k, v in message.items() if k != "type"}}
                else:
                    endpoint, extra = "messages", {"message": message}
                client = agent
            elif phase == "awaiting_decision":
                # Explicit synthetic operator policy. Never used for a real/human session.
                client, endpoint = operator, "messages"
                extra = {"message": {"type": "operator_decision", "request_id": snapshot["pending_request_id"],
                                      "action": "approve", "reason": "Operatore simulato della demo offline."}}
            elif phase == "awaiting_mode":
                client, endpoint = operator, "messages"
                extra = {"message": {"type": "execution_mode", "request_id": snapshot["pending_request_id"], "mode": "exploration"}}
            elif phase == "ready_to_run":
                client, endpoint = operator, "run"
                extra = {"request_id": snapshot["pending_request_id"]}
            else:
                raise ValidationError("Stato inatteso della demo offline.")
            client.write(f"sessions/{sid}/{endpoint}", {"expected_version": snapshot["version"], **extra}, f"demo-step-{step:03d}")
            snapshot = agent.read("sessions/" + sid)
        operator.write("challenges/" + challenge["challenge_id"] + "/close", {}, "demo-close")
        board = agent.read("challenges/" + challenge["challenge_id"] + "/leaderboard")
        operator.write("tokens/" + issued["token_id"] + "/revoke", {}, "demo-revoke")
        revoked = transport.get("/v1/arena/sessions/" + sid, headers=agent.headers()).status_code == 401
        summary = {"notice": "Baseline offline, operatore simulato. Nessun LLM reale; nessun reveal.",
                   "challenge_id": challenge["challenge_id"], "session_id": sid, "status": snapshot["status"],
                   "experiments": snapshot["executed_experiments"], "observations": snapshot["observations"],
                   "baseline_calls": calls, "resources": snapshot["resources"],
                   "dimensions": board["dimensions"], "token_revoked": revoked}
        print(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False))
    return 0
