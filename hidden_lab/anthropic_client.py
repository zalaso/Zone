"""Claude Messages API, con output_config JSON Schema ufficiale."""

import os

from .agent_contract import ModelRequest
from .protocol import ValidationError
from .provider_base import ModelReply, ProviderError, count, metadata


def anthropic_payload(request: ModelRequest):
    return {"model": request.model, "max_tokens": request.max_output_tokens,
            "system": request.instructions,
            "messages": [{"role": "user", "content": request.user_content()}],
            "output_config": {"format": {"type": "json_schema", "schema": request.schema}}}


def anthropic_metadata(response):
    usage = getattr(response, "usage", None)
    fields = {name: count(getattr(usage, name, None)) for name in ("input_tokens", "output_tokens")}
    details = {name: count(getattr(usage, name, None)) for name in
               ("cache_creation_input_tokens", "cache_read_input_tokens")}
    return metadata(getattr(response, "id", None), getattr(response, "model", None),
                    getattr(response, "stop_reason", None),
                    {**fields, "total_tokens": None} if usage is not None else None,
                    provider_details={"usage": details} if any(value is not None for value in details.values()) else None)


class AnthropicClient:
    provider = "anthropic"

    def __init__(self, settings, *, transport=None, sdk=None):
        from anthropic import Anthropic, __version__
        import httpx2
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key or not key.strip():
            raise ValidationError("Imposta ANTHROPIC_API_KEY nell'ambiente.")
        self.sdk_version = __version__
        self.generation_settings = {"response_format": "output_config.format/json_schema",
                                    "max_tokens": settings.max_output_tokens, "max_retries": 0,
                                    "timeout_seconds": settings.timeout, "tools": []}
        self.sdk = sdk if sdk is not None else Anthropic(
            api_key=key, base_url="https://api.anthropic.com", max_retries=0, timeout=settings.timeout,
            http_client=httpx2.Client(transport=transport, trust_env=False, timeout=settings.timeout))
        self._owns_sdk = sdk is None

    def complete(self, request: ModelRequest):
        from anthropic import APIConnectionError, APIError, APIStatusError, APITimeoutError
        try:
            response = self.sdk.messages.create(**anthropic_payload(request))
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
            info = anthropic_metadata(response)
            if response.stop_reason != "end_turn":
                return ModelReply("", info, "incomplete_response")
            blocks = [block.text for block in response.content if block.type == "text"]
            if len(blocks) != 1:
                return ModelReply("", info, "incomplete_response")
            return ModelReply(blocks[0], info)
        except (AttributeError, TypeError, ValueError):
            raise ProviderError("provider_error") from None

    def close(self):
        if self._owns_sdk:
            self.sdk.close()
