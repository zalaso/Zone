"""Adattatore OpenAI; esporta ancora i nomi pubblici della v0.2."""

import os

from .agent_contract import ModelRequest, openai_payload
from .protocol import ValidationError
from .provider_base import AgentSettings, ModelReply, ProviderError, count, metadata, validate_remote_settings


def response_metadata(response):
    usage = response.usage
    clean_usage = None
    if usage is not None:
        clean_usage = {}
        for field in ("input_tokens", "output_tokens", "total_tokens"):
            value = getattr(usage, field, None)
            clean_usage[field] = count(value)
        for group, field in (("input_tokens_details", "cached_tokens"), ("output_tokens_details", "reasoning_tokens")):
            value = getattr(getattr(usage, group, None), field, None)
            if count(value) is not None:
                clean_usage[group] = {field: value}
    return metadata(response.id, response.model, response.status, clean_usage)


class OpenAIClient:
    provider = "openai"

    def __init__(self, settings, *, transport=None, api_key=None):
        validate_remote_settings(settings)
        # Creare un client non effettua richieste. La chiave rimane nel solo SDK.
        from openai import OpenAI, __version__
        import httpx
        key = api_key if api_key is not None else os.environ.get("OPENAI_API_KEY")
        if not key or not key.strip():
            raise ValidationError("Imposta OPENAI_API_KEY nell'ambiente prima di avviare il client reale.")
        self.sdk_version = __version__
        self.generation_settings = {"response_format": "json_schema/strict", "store": False,
                                    "tools": [], "truncation": "disabled", "max_output_tokens": settings.max_output_tokens,
                                    "max_retries": 0, "timeout_seconds": settings.timeout}
        self.sdk = OpenAI(api_key=key, base_url="https://api.openai.com/v1", max_retries=0,
                          timeout=settings.timeout,
                          http_client=httpx.Client(transport=transport, trust_env=False, timeout=settings.timeout))

    def complete(self, payload):
        if isinstance(payload, ModelRequest):
            payload = openai_payload(payload)
        from openai import APIConnectionError, APIError, APIStatusError, APITimeoutError
        try:
            response = self.sdk.responses.create(**payload)
        except APITimeoutError:
            raise ProviderError("timeout") from None
        except APIConnectionError:
            raise ProviderError("connection") from None
        except APIStatusError as exc:
            code = {401: "authentication", 403: "authentication", 429: "rate_limit"}.get(exc.status_code)
            raise ProviderError(code or ("server_error" if exc.status_code >= 500 else "request_rejected")) from None
        except APIError:
            raise ProviderError("provider_error") from None
        try:
            metadata = response_metadata(response)
            if response.status != "completed":
                return ModelReply("", metadata, "incomplete_response")
            if any(getattr(part, "type", None) == "refusal" for item in response.output
                   for part in getattr(item, "content", [])):
                return ModelReply("", metadata, "refusal")
            return ModelReply(response.output_text, metadata)
        except (AttributeError, TypeError, ValueError):
            raise ProviderError("provider_error") from None

    def close(self):
        self.sdk.close()
