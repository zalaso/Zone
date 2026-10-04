"""Ollama API nativa, esclusivamente su 127.0.0.1:11434."""

from importlib.metadata import PackageNotFoundError, version

from .agent_contract import ModelRequest
from .protocol import ValidationError
from .provider_base import ModelReply, ProviderError, count, metadata

LOCAL_BASE = "http://127.0.0.1:11434"


def ollama_payload(request: ModelRequest):
    return {"model": request.model,
            "messages": [{"role": "system", "content": request.instructions},
                         {"role": "user", "content": request.user_content()}],
            "format": request.schema, "stream": False,
            "options": {"num_predict": request.max_output_tokens}}


def ollama_metadata(response):
    native = {name: count(response.get(name)) for name in
              ("prompt_eval_count", "prompt_eval_cached_count", "eval_count")}
    return metadata(None, response.get("model"), response.get("done_reason") if response.get("done") else "incomplete",
                    None, provider_details={"usage": native})


class OllamaClient:
    provider = "ollama"

    def __init__(self, settings, *, http_client=None):
        import httpx
        if settings.model.endswith(":cloud"):
            raise ValidationError("Scegli un modello Ollama locale, non un modello :cloud.")
        self.sdk_version = None
        try:
            self.http_version = version("httpx")
        except PackageNotFoundError:
            self.http_version = None
        self.generation_settings = {"format": "json_schema", "stream": False,
                                    "num_predict": settings.max_output_tokens,
                                    "timeout_seconds": settings.timeout, "endpoint": LOCAL_BASE,
                                    "automatic_download": False, "retries": 0}
        self.http = http_client if http_client is not None else httpx.Client(base_url=LOCAL_BASE,
                           trust_env=False, follow_redirects=False, timeout=settings.timeout)
        self._owns_http = http_client is None

    def _send(self, method, path, **kwargs):
        import httpx
        try:
            response = self.http.request(method, LOCAL_BASE + path, **kwargs)
        except httpx.TimeoutException:
            raise ProviderError("timeout") from None
        except httpx.RequestError:
            raise ProviderError("service_unavailable") from None
        if response.status_code == 404:
            raise ProviderError("model_unavailable" if path == "/api/chat" else "service_unavailable") from None
        if response.status_code in (401, 403):
            raise ProviderError("authentication") from None
        if response.status_code == 429:
            raise ProviderError("rate_limit") from None
        if response.status_code >= 500:
            raise ProviderError("server_error") from None
        if response.status_code >= 400:
            raise ProviderError("request_rejected") from None
        try:
            return response.json()
        except ValueError:
            raise ProviderError("provider_error") from None

    def preflight(self, model):
        """Solo elenco locale; non chiama pull, create, show cloud o endpoint remoti."""
        data = self._send("GET", "/api/tags")
        if not isinstance(data, dict) or not isinstance(data.get("models"), list):
            raise ProviderError("provider_error")
        names = {item["name"] for item in data["models"] if isinstance(item, dict) and isinstance(item.get("name"), str)}
        if model not in names:
            raise ProviderError("model_unavailable")

    def complete(self, request: ModelRequest):
        result = self._send("POST", "/api/chat", json=ollama_payload(request))
        if not isinstance(result, dict):
            raise ProviderError("provider_error")
        info = ollama_metadata(result)
        if result.get("done") is not True or result.get("done_reason") not in (None, "stop"):
            return ModelReply("", info, "incomplete_response")
        message = result.get("message")
        if not isinstance(message, dict) or not isinstance(message.get("content"), str):
            return ModelReply("", info, "incomplete_response")
        return ModelReply(message["content"], info)

    def close(self):
        if self._owns_http:
            self.http.close()
