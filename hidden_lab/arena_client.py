"""Client BYOA minimo e adapter pubblico; nessun retry, filesystem o credenziale nei prompt."""

from dataclasses import replace

from .agent_contract import response_schema
from .protocol import ValidationError
from .web_agent import build_web_request


class _PublicState:
    def __init__(self, snapshot):
        self.phase = snapshot["status"]
        self.executed_count = snapshot["executed_experiments"]
        self.budget = snapshot["rules"]["experiment_budget"]

    def status(self):
        return self.phase


def model_request(snapshot, settings, remaining_calls):
    """Proiezione positiva nel builder esistente: ignora account, token e campi aggiunti."""
    if snapshot["status"] not in ("discovering", "awaiting_submission"):
        raise ValidationError("Attendi l'operatore prima di chiedere un messaggio al modello.")
    request = build_web_request(snapshot["events"], settings, _PublicState(snapshot), remaining_calls,
                                snapshot["rules"]["max_messages"] - snapshot["messages"])
    if snapshot["status"] == "awaiting_submission":
        return request
    kinds = tuple(kind for kind in request.allowed_types if kind not in ("operator_question", "prediction"))
    return replace(request, allowed_types=kinds, schema=response_schema(kinds),
                   context={**request.context, "allowed_types": list(kinds), "arena_version": "1"},
                   instructions=request.instructions + "\nArena v1: solo esplorazione; nessun aiuto teorico dell'operatore.")


class ArenaClient:
    """Transport httpx/TestClient iniettato. Conservare la key per eventuali retry manuali."""
    def __init__(self, transport, token, *, account_key=None):
        self.transport, self.token = transport, token
        self.account_key = account_key

    def headers(self):
        return {"X-Zone-Arena-Version": "1", "X-Zone-Token": self.token,
                **({'Authorization': 'Bearer ' + self.account_key} if self.account_key else {})}

    def read(self, path):
        reply = self.transport.get("/v1/arena/" + path, headers=self.headers())
        reply.raise_for_status()
        return reply.json()

    def write(self, path, body, key):
        reply = self.transport.post("/v1/arena/" + path, json=body,
            headers={**self.headers(), "Idempotency-Key": key})
        reply.raise_for_status()
        return reply.json()
