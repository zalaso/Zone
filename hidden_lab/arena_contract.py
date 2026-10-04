"""BYOA v1: soli DTO pubblici, nessun oggetto laboratorio passato agli agenti."""

from .agent_contract import INSTRUCTIONS, response_schema
from .protocol import ValidationError, require_keys

VERSION = "1"
AGENT_TYPES = ("experiment_request", "hypothesis", "conclusion")
QUOTAS = {"sessions": 4, "requests": 100, "experiments": 12}


def integer(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValidationError("Intero fuori dai limiti Arena.")
    return value


def label(value):
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= 80 or any(ord(c) < 32 for c in value):
        raise ValidationError("Etichetta Arena non valida.")
    return value.strip()


def quotas(value):
    require_keys(value, tuple(QUOTAS))
    return {key: integer(value[key], 1, maximum) for key, maximum in
            (("sessions", 100), ("requests", 10000), ("experiments", 400))}


def contract():
    return {"arena_version": VERSION, "message_protocol_version": 2, "scientific_submission_version": 1,
            "instructions": INSTRUCTIONS + "\nArena v1: solo esplorazione; non chiedere aiuto teorico o modifiche all'operatore.",
            "agent_response_schema": response_schema(AGENT_TYPES),
            "authentication": "X-Zone-Token; X-Zone-Arena-Version: 1",
            "mutations": "Idempotency-Key obbligatorio (8–128 caratteri ASCII); CAS expected_version",
            "permissions": {"agent": ["create_trial", "own_history", "agent_messages", "submission"],
                            "operator": ["challenge", "tokens", "approve", "run", "stop", "score", "audit", "reveal"]},
            "submission": {"predictions": "Una ax e ay finite per ogni probe_id, nello stesso ordine del probe_challenge",
                           "optional": ["law_ast_json (AST sicuro, non codice)", "uncertainty_sigma (positiva, una per probe)"]},
            "execution_policy": "exploration_only; niente domande teoriche, modifiche o previsioni di traiettoria in Arena v1",
            "notice": "Nessuna esecuzione implicita. Il silenzio non approva. I token non autorizzano chiamate LLM."}
