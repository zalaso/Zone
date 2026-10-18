"""Contratto minimo condiviso: nessuna dipendenza da SDK o da Session."""

from dataclasses import asdict, dataclass
import re
from typing import Protocol

from .protocol import ValidationError, number

ADAPTER_VERSION = 1


@dataclass(frozen=True)
class AgentSettings:
    model: str
    max_calls: int = 20
    max_turns: int = 15
    max_corrections: int = 2
    timeout: float = 30
    max_output_tokens: int = 2500
    max_points: int = 9
    max_input_bytes: int = 200_000

    def __post_init__(self):
        # Nomi locali Ollama possono includere il namespace, ma non URL.
        if not isinstance(self.model, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}", self.model) or "//" in self.model:
            raise ValidationError("Scegli un ID modello valido tramite --model o la variabile del provider.")
        for name, low, high in (("max_calls", 1, 100), ("max_turns", 1, 100), ("max_corrections", 0, 5),
                                ("max_output_tokens", 256, 16000), ("max_points", 2, 9), ("max_input_bytes", 1000, 500000)):
            value = getattr(self, name)
            if type(value) is not int or not low <= value <= high:
                raise ValidationError(f"Impostazione {name} fuori dai limiti [{low}, {high}].")
        # CPU inference may need longer; remote entry points enforce their 120 s cap.
        number(self.timeout, 1, 600)

    def to_dict(self):
        return asdict(self)


def validate_remote_settings(settings):
    if settings.timeout > 120:
        raise ValidationError("Timeout remoto massimo 120 secondi; fino a 600 solo con Ollama locale.")


@dataclass(frozen=True)
class ModelReply:
    text: str
    metadata: dict
    issue: str | None = None


class ProviderError(Exception):
    """Solo codici locali: mai corpi HTTP, header o eccezioni SDK."""

    def __init__(self, code, *, http_status=None, provider_code=None):
        allowed = {"timeout", "connection", "authentication", "rate_limit", "request_rejected",
                   "server_error", "provider_error", "service_unavailable", "model_unavailable"}
        self.code = code if code in allowed else "provider_error"
        self.http_status = http_status if type(http_status) is int and 400 <= http_status <= 599 else None
        allowed_provider_codes = {
            'subscription_sharing_usage_limit_exceeded', 'subscription_sharing_usage_unavailable',
            'subscription_sharing_user_unavailable', 'subscription_sharing_user_not_eligible',
            'subscription_sharing_invalid_user', 'subscription_sharing_unsupported_capability',
            'subscription_sharing_route_not_supported', 'chatpass_v2_scope_not_authorized',
            'chatpass_v2_invalid_authorization_context'}
        self.provider_code = provider_code if provider_code in allowed_provider_codes else None
        super().__init__(self.code)


class ModelClient(Protocol):
    provider: str
    sdk_version: str | None

    def complete(self, request) -> ModelReply: ...
    def close(self) -> None: ...


def count(value):
    return value if type(value) is int and value >= 0 else None


def metadata(response_id=None, returned_model=None, status=None, usage=None, *, provider_details=None):
    """Campi comuni. I conteggi con nomi diversi restano in provider_details."""
    return {"response_id": response_id if isinstance(response_id, str) and len(response_id) <= 256 else None,
            "returned_model": returned_model if isinstance(returned_model, str) and len(returned_model) <= 128 else None,
            "status": status if isinstance(status, str) and len(status) <= 64 else None,
            "usage": usage,
            "provider_details": provider_details or None}
