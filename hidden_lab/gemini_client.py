"""Google Gen AI SDK, generate_content con response_json_schema."""

import os

from .agent_contract import ModelRequest
from .protocol import ValidationError
from .provider_base import ModelReply, ProviderError, count, metadata


def gemini_payload(request: ModelRequest):
    return {"model": request.model, "contents": request.user_content(),
            "config": {"system_instruction": request.instructions,
                       "response_mime_type": "application/json",
                       "response_json_schema": request.schema,
                       "max_output_tokens": request.max_output_tokens,
                       "tools": []}}


def gemini_metadata(response, completed):
    usage = getattr(response, "usage_metadata", None)
    native = {name: count(getattr(usage, name, None)) for name in
              ("prompt_token_count", "candidates_token_count", "total_token_count",
               "cached_content_token_count", "thoughts_token_count")}
    # I conteggi Gemini mantengono i nomi originali; non sono ribattezzati
    # come token OpenAI/Anthropic né sommati per ottenere misure sintetiche.
    return metadata(getattr(response, "response_id", None), getattr(response, "model_version", None),
                    "completed" if completed else "incomplete", None,
                    provider_details={"usage": native} if usage is not None else None)


class GeminiClient:
    provider = "gemini"

    def __init__(self, settings, *, sdk=None):
        from google import genai
        from google.genai import types
        key = os.environ.get("GEMINI_API_KEY")
        if not key or not key.strip():
            raise ValidationError("Imposta GEMINI_API_KEY nell'ambiente.")
        self.sdk_version = genai.__version__
        self.generation_settings = {"response_mime_type": "application/json",
                                    "response_json_schema": True, "max_output_tokens": settings.max_output_tokens,
                                    "retry_attempts": 1, "timeout_seconds": settings.timeout, "tools": []}
        options = types.HttpOptions(timeout=int(settings.timeout * 1000),
                                    retry_options=types.HttpRetryOptions(attempts=1),
                                    client_args={"trust_env": False})
        self.sdk = sdk if sdk is not None else genai.Client(api_key=key, vertexai=False, http_options=options)
        self._owns_sdk = sdk is None
        self.http_options = options

    def complete(self, request: ModelRequest):
        from google.genai import errors
        import httpx
        try:
            response = self.sdk.models.generate_content(**gemini_payload(request))
        except errors.APIError as exc:
            code = getattr(exc, "code", None)
            mapped = {401: "authentication", 403: "authentication", 429: "rate_limit"}.get(code)
            raise ProviderError(mapped or ("server_error" if type(code) is int and code >= 500
                                          else "request_rejected")) from None
        except httpx.TimeoutException:
            raise ProviderError("timeout") from None
        except httpx.RequestError:
            raise ProviderError("connection") from None
        except Exception:
            raise ProviderError("provider_error") from None
        try:
            candidates = response.candidates or []
            reason = getattr(candidates[0], "finish_reason", None) if candidates else None
            completed = getattr(reason, "name", str(reason)) == "STOP"
            info = gemini_metadata(response, completed)
            if not completed:
                return ModelReply("", info, "incomplete_response")
            value = response.text
            if not isinstance(value, str) or not value:
                return ModelReply("", info, "incomplete_response")
            return ModelReply(value, info)
        except (AttributeError, TypeError, ValueError):
            raise ProviderError("provider_error") from None

    def close(self):
        if self._owns_sdk:
            self.sdk.close()
