"""Responses over official subscription OAuth, no API-key fallback or local tools."""
import time
from threading import Lock

from .agent_contract import ModelRequest, openai_payload
from .chatgpt_auth import AuthError, CredentialStore, access_token, auth_http
from .llm import response_metadata
from .protocol import ValidationError, decode
from .provider_base import ModelReply, ProviderError, validate_remote_settings


def chatgpt_payload(request):
    if not isinstance(request, ModelRequest):
        raise ValidationError('Il client ChatGPT accetta solo il contratto pubblico ModelRequest.')
    payload = openai_payload(request)
    del payload['max_output_tokens']
    del payload['truncation']
    payload['stream'] = True
    return payload


def error_code(code, status=None):
    return {'subscription_sharing_usage_limit_exceeded': 'rate_limit',
            'subscription_sharing_usage_unavailable': 'service_unavailable',
            'subscription_sharing_user_unavailable': 'service_unavailable',
            'subscription_sharing_user_not_eligible': 'authentication',
            'subscription_sharing_invalid_user': 'authentication',
            'subscription_sharing_unsupported_capability': 'request_rejected',
            'subscription_sharing_route_not_supported': 'request_rejected',
            'chatpass_v2_scope_not_authorized': 'authentication',
            'chatpass_v2_invalid_authorization_context': 'authentication'}.get(code,
            {401: 'authentication', 403: 'authentication', 429: 'rate_limit', 503: 'service_unavailable'}.get(status,
            'server_error' if status and status >= 500 else 'provider_error'))


def text_diagnostics(text):
    """Structural diagnostics only: never log model text or JSON error excerpts."""
    if not text.strip():
        syntax = 'empty'
    elif text.lstrip().startswith('```'):
        syntax = 'markdown_fence'
    else:
        try:
            decode(text)
            syntax = 'valid'
        except ValidationError:
            syntax = 'invalid'
    return {'json_syntax': syntax, 'response_text_bytes': len(text.encode('utf-8'))}


class TextStream:
    """Collect public text parts, but expose nothing until terminal completion."""

    def __init__(self):
        self.parts = {}
        self.finalized = set()
        self.bytes = 0
        self.delta_count = 0
        self.refused = False

    def consume(self, event):
        if event.type.startswith('response.refusal.'):
            self.refused = True
        if event.type in ('response.output_item.added', 'response.output_item.done'):
            if event.item.type not in ('message', 'reasoning'):
                raise ProviderError('request_rejected')
            if any(part.type == 'refusal' for part in getattr(event.item, 'content', [])):
                self.refused = True
        if event.type not in ('response.output_text.delta', 'response.output_text.done'):
            return
        key = (event.output_index, event.content_index)
        if any(type(index) is not int or index < 0 for index in key):
            raise ProviderError('request_rejected')
        previous = self.parts.get(key, '')
        if event.type == 'response.output_text.delta':
            if key in self.finalized:
                raise ProviderError('request_rejected')
            text = previous + event.delta
            self.delta_count += 1
        else:
            text = event.text
            if previous and previous != text:
                raise ProviderError('request_rejected')
            self.finalized.add(key)
        self.bytes += len(text.encode('utf-8')) - len(previous.encode('utf-8'))
        if self.bytes > 65536:
            raise ProviderError('request_rejected')
        self.parts[key] = text

    def completed(self, response):
        streamed = ''.join(self.parts[key] for key in sorted(self.parts))
        snapshot = response.output_text
        # Both representations must agree when both are supplied. Never repair JSON.
        if snapshot and streamed and snapshot != streamed:
            raise ProviderError('request_rejected')
        text = streamed or snapshot
        if len(text.encode('utf-8')) > 65536:
            raise ProviderError('request_rejected')
        metadata = response_metadata(response)
        metadata['provider_details'] = {**text_diagnostics(text),
                                        'text_delta_events': self.delta_count,
                                        'text_source': 'stream' if streamed else 'completion'}
        return text, metadata


class ChatGPTClient:
    provider = 'chatgpt'

    def __init__(self, settings, *, store=None, transport=None, token_supplier=None):
        validate_remote_settings(settings)
        from openai import OpenAI, __version__, omit
        import httpx
        self.sdk_version = __version__
        self.settings = settings
        self.store = store or CredentialStore()
        self._lock = None
        self.auth = None
        self._supplier = token_supplier  # Tests only; not exposed through CLI/env or payloads.
        self._inference_lock = Lock()
        self.sdk = None
        self.http = None
        try:
            if token_supplier is None:
                self._lock = self.store.lock()
                self._lock.__enter__()
                self.auth = auth_http()
                token = access_token(self.store, self.auth)
            else:
                token = token_supplier()
            self.http = httpx.Client(transport=transport, trust_env=False, timeout=settings.timeout)
            self.sdk = OpenAI(api_key=token, base_url='https://api.openai.com/v1', max_retries=0,
                              timeout=settings.timeout, http_client=self.http,
                              default_headers={'OpenAI-Organization': omit, 'OpenAI-Project': omit})
        except Exception:
            self.close()
            raise
        self.generation_settings = {'authentication': 'chatgpt_plan_oauth', 'response_format': 'json_schema/strict',
                                    'store': False, 'stream': True, 'tools': [], 'max_retries': 0,
                                    'timeout_seconds': settings.timeout, 'max_output_tokens': None,
                                    'max_output_tokens_supported': False, 'local_response_limit_bytes': 65536,
                                    'text_extraction_version': 2}

    def complete(self, request):
        # One refresh owner, including concurrent web sessions. Never queue a late inference.
        if not self._inference_lock.acquire(blocking=False):
            raise ProviderError('rate_limit')
        try:
            return self._complete(request)
        finally:
            self._inference_lock.release()

    def _complete(self, request):
        from openai import APIConnectionError, APIError, APIStatusError, APITimeoutError
        payload = chatgpt_payload(request)
        start = time.monotonic()
        try:
            self.sdk.api_key = self._supplier() if self._supplier else access_token(self.store, self.auth)
            with self.sdk.responses.create(**payload) as stream:
                size = 0
                collector = TextStream()
                for event in stream:
                    if time.monotonic() - start > self.settings.timeout:
                        raise ProviderError('timeout')
                    size += len(event.model_dump_json().encode('utf-8'))
                    if size > 2000000:
                        raise ProviderError('request_rejected')
                    collector.consume(event)
                    if event.type in ('response.failed', 'error'):
                        failure = getattr(getattr(event, 'response', None), 'error', None)
                        code = getattr(failure or event, 'code', None)
                        raise ProviderError(error_code(code), provider_code=code)
                    if event.type == 'response.incomplete':
                        return ModelReply('', response_metadata(event.response), 'incomplete_response')
                    if event.type == 'response.completed':
                        response = event.response
                        if response.status != 'completed':
                            raise ProviderError('provider_error')
                        if any(item.type not in ('message', 'reasoning') for item in response.output):
                            raise ProviderError('request_rejected')
                        if collector.refused or any(part.type == 'refusal' for item in response.output for part in getattr(item, 'content', [])):
                            return ModelReply('', response_metadata(response), 'refusal')
                        text, metadata = collector.completed(response)
                        return ModelReply(text, metadata)
            raise ProviderError('connection')  # EOF without terminal completion is not valid JSON success.
        except AuthError:
            raise ProviderError('authentication') from None
        except APITimeoutError:
            raise ProviderError('timeout') from None
        except APIConnectionError:
            raise ProviderError('connection') from None
        except APIStatusError as exc:
            body = exc.body if isinstance(exc.body, dict) else {}
            code = body.get('code')
            raise ProviderError(error_code(code, exc.status_code), http_status=exc.status_code, provider_code=code) from None
        except APIError:
            raise ProviderError('provider_error') from None
        except ProviderError:
            raise
        except Exception:
            raise ProviderError('provider_error') from None

    def models(self):
        """Catalog only, never a generation or an entitlement guarantee."""
        token = self._supplier() if self._supplier else access_token(self.store, self.auth)
        try:
            response = self.http.get('https://api.openai.com/v1/models', headers={'Authorization': 'Bearer ' + token})
            if response.status_code != 200:
                raise ProviderError(error_code(None, response.status_code), http_status=response.status_code)
            value = response.json()
            return [{'slug': row['slug'], 'display_name': row['display_name']} for row in value['models']
                    if row.get('visibility') == 'list' and isinstance(row.get('slug'), str)
                    and isinstance(row.get('display_name'), str)]
        except ProviderError:
            raise
        except Exception:
            raise ProviderError('provider_error') from None

    def close(self):
        if self.sdk is not None:
            self.sdk.close()
            self.sdk = None
        if self.http is not None:
            self.http.close()
            self.http = None
        if self.auth is not None:
            self.auth.close()
            self.auth = None
        if self._lock is not None:
            self._lock.__exit__(None, None, None)
            self._lock = None
