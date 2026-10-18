"""Subscription route: synthetic OAuth and HTTP only; no account or inference."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import time
import io
from urllib.parse import parse_qs, urlsplit

from hidden_lab.agent_contract import build_request
from hidden_lab.provider_base import AgentSettings, ProviderError
from hidden_lab.session import Session
from test_lab import config
from test_agent import conclusion

try:
    import httpx
    import openai
    import jwt
    from cryptography.hazmat.primitives.asymmetric import rsa
except ImportError:
    httpx = openai = jwt = rsa = None


class SubscriptionPayloadTests(unittest.TestCase):
    def test_explicit_public_payload_omits_unsupported_fields_and_private_truth(self):
        from hidden_lab.chatgpt_client import chatgpt_payload
        with tempfile.TemporaryDirectory() as directory:
            session = Session(Path(directory) / 's', config('constant', 7.654321))
            session.events[0]['message']['private'] = {'secret': 'private-marker'}
            request = build_request(session.events, AgentSettings('chosen-model'), 'choose_next', 8, 8)
        body = chatgpt_payload(request)
        self.assertTrue(body['stream'])
        self.assertFalse(body['store'])
        self.assertEqual(body['tools'], [])
        self.assertEqual(body['instructions'], request.instructions)
        self.assertEqual(body['text']['format']['schema'], request.schema)
        self.assertEqual(json.loads(body['input'][0]['content']), json.loads(request.user_content()))
        for field in ('max_output_tokens', 'truncation', 'temperature', 'previous_response_id', 'metadata'):
            self.assertNotIn(field, body)
        for private in ('private-marker', '7.654321', '"seed"', 'README', 'reproducibility'):
            self.assertNotIn(private, json.dumps(body))

    def test_provider_error_only_accepts_numeric_http_status(self):
        self.assertEqual(ProviderError('server_error', http_status=503).http_status, 503)
        for invalid in (True, 'secret', 200, 600):
            self.assertIsNone(ProviderError('server_error', http_status=invalid).http_status)


class ProtectedStoreTests(unittest.TestCase):
    def test_storage_roundtrip_locking_and_windows_ciphertext(self):
        from hidden_lab.chatgpt_auth import AuthError, CredentialStore
        with tempfile.TemporaryDirectory() as directory:
            store = CredentialStore(Path(directory) / 'auth')
            with store.lock():
                state = store.load()
                original_host = state['host_id']
                state['accounts'] = [{'access_token': 'synthetic-secret'}]
                store.save(state)
                self.assertEqual(store.load(), state)
                with self.assertRaises(AuthError):
                    with store.lock():
                        pass
                if os.name == 'nt':
                    self.assertNotIn(b'synthetic-secret', store.path.read_bytes())
            with store.lock():
                self.assertEqual(store.load()['host_id'], original_host)

    def test_callback_rejects_state_duplicates_and_client_switch(self):
        from hidden_lab.chatgpt_auth import AuthError, LoginAttempt
        attempt = LoginAttempt('urn:uuid:offline', 'http://127.0.0.1:1455/auth/callback', 'oaiapp_saved')
        for query in ('state=wrong&code=x', f'state={attempt.state}&code=x&code=y',
                      f'state={attempt.state}&code=x&client_id=oaiapp_other'):
            with self.assertRaises(AuthError):
                attempt.callback('/auth/callback?' + query)
        fresh = LoginAttempt('urn:uuid:offline', 'http://127.0.0.1:1455/auth/callback', 'oaiapp_saved')
        self.assertEqual(fresh.callback(f'/auth/callback?state={fresh.state}&code=x'), ('x', 'oaiapp_saved'))
        with self.assertRaises(AuthError):
            fresh.callback(f'/auth/callback?state={fresh.state}&code=x')

    def test_authorization_pkce_host_and_new_registration_only(self):
        from hidden_lab.chatgpt_auth import LoginAttempt
        import base64
        import hashlib
        first = LoginAttempt('urn:uuid:offline', 'http://127.0.0.1:1455/auth/callback')
        values = parse_qs(urlsplit(first.url()).query)
        self.assertEqual(values['client_id'], ['dynamic_agent_client'])
        self.assertEqual(values['agent_name_hint'], ['Zone'])
        self.assertEqual(values['ext_agent_host_id'], [first.host_id])
        self.assertEqual(values['code_challenge_method'], ['S256'])
        self.assertEqual(values['code_challenge'], [base64.urlsafe_b64encode(hashlib.sha256(first.verifier.encode()).digest()).decode().rstrip('=')])
        self.assertIn('chatgpt.tokens.use.direct', values['scope'][0])
        repeat = LoginAttempt(first.host_id, first.redirect_uri, 'oaiapp_saved')
        later = parse_qs(urlsplit(repeat.url()).query)
        self.assertNotIn('agent_name_hint', later)
        self.assertNotIn('id_token_hint', later)
        self.assertNotEqual(first.state, repeat.state)
        self.assertNotEqual(first.nonce, repeat.nonce)
        expired = LoginAttempt(first.host_id, first.redirect_uri, deadline=0)
        with self.assertRaises(ValueError):
            expired.callback('/auth/callback?state=x&code=y')


class MemoryStore:
    def __init__(self, state):
        self.state = state
        self.saved = 0

    def load(self):
        return self.state

    def save(self, state):
        self.state = state
        self.saved += 1

    def lock(self):
        from contextlib import nullcontext
        return nullcontext(self)


@unittest.skipUnless(jwt is not None, 'richiede extra chatgpt')
class OAuthIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(cls.key.public_key()))
        cls.jwk['kid'] = 'offline-key'

    def signed(self, **overrides):
        claims = {'iss': 'https://auth.openai.com', 'aud': 'oaiapp_saved', 'sub': 'offline-user',
                  'iat': int(time.time()), 'exp': int(time.time()) + 300, 'nonce': 'expected'}
        return jwt.encode({**claims, **overrides}, self.key, algorithm='RS256', headers={'kid': 'offline-key'})

    def http(self, tokens=None, seen=None):
        def handler(request):
            if seen is not None:
                seen.append(request)
            if request.url.path.endswith('jwks.json'):
                return httpx.Response(200, json={'keys': [self.jwk]})
            return httpx.Response(200, json=tokens)
        client = httpx.Client(transport=httpx.MockTransport(handler))
        self.addCleanup(client.close)
        return client

    def test_signature_issuer_audience_nonce_expiry_and_subject_are_verified(self):
        from hidden_lab.chatgpt_auth import AuthError, verify_identity
        http = self.http()
        self.assertEqual(verify_identity(http, self.signed(), 'oaiapp_saved', nonce='expected')['sub'], 'offline-user')
        for bad in (self.signed(iss='https://attacker.invalid'), self.signed(aud='other'),
                    self.signed(exp=int(time.time()) - 60), self.signed(nonce='wrong'),
                    jwt.encode({'sub': 'forged'}, 'synthetic-secret-at-least-32-bytes-long', algorithm='HS256', headers={'kid': 'offline-key'})):
            with self.subTest(token_case=bad[:5]), self.assertRaises(AuthError):
                verify_identity(http, bad, 'oaiapp_saved', nonce='expected')
        with self.assertRaises(AuthError):
            verify_identity(http, self.signed(), 'oaiapp_saved', subject='other-user')
        # Tampered signature with otherwise valid claims.
        token = self.signed()
        head, body, signature = token.split('.')
        with self.assertRaises(AuthError):
            verify_identity(http, head + '.' + body + '.' + ('A' if signature[0] != 'A' else 'B') + signature[1:], 'oaiapp_saved')

    def test_refresh_rotates_atomically_without_identity_switch_or_missing_scope(self):
        from hidden_lab.chatgpt_auth import AuthError, DIRECT_SCOPE, access_token
        original = {'client_id': 'oaiapp_saved', 'subject': 'offline-user', 'scopes': [DIRECT_SCOPE],
                    'expires_at': 0, 'access_token': 'expired-synthetic', 'refresh_token': 'old-synthetic', 'label': 'one'}
        tokens = {'access_token': 'new-synthetic', 'refresh_token': 'rotated-synthetic',
                  'id_token': self.signed(), 'scope': DIRECT_SCOPE, 'expires_in': 3600, 'token_type': 'Bearer'}
        store = MemoryStore({'active': 'oaiapp_saved', 'accounts': [dict(original)]})
        seen = []
        self.assertEqual(access_token(store, self.http(tokens, seen)), 'new-synthetic')
        self.assertEqual(store.saved, 1)
        self.assertEqual(store.state['accounts'][0]['refresh_token'], 'rotated-synthetic')
        form = parse_qs(seen[0].content.decode())
        self.assertEqual(form['client_id'], ['oaiapp_saved'])
        self.assertNotIn('scope', form)
        for invalid in ({**tokens, 'scope': 'openid'}, {**tokens, 'id_token': self.signed(sub='other')}):
            store = MemoryStore({'active': 'oaiapp_saved', 'accounts': [dict(original)]})
            with self.assertRaises(AuthError):
                access_token(store, self.http(invalid))
            self.assertEqual(store.saved, 0)
            self.assertEqual(store.state['accounts'][0]['refresh_token'], 'old-synthetic')

    def test_login_flow_mock_browser_callback_exchange_and_multiple_accounts(self):
        from hidden_lab.chatgpt_auth import login
        store = MemoryStore({'version': 1, 'host_id': 'urn:uuid:offline', 'active': None, 'accounts': []})
        authorized = {}
        seen = []
        def browser(url):
            authorized.update(parse_qs(urlsplit(url).query))
            return True
        def handler(request):
            seen.append(request)
            if request.url.path.endswith('jwks.json'):
                return httpx.Response(200, json={'keys': [self.jwk]})
            return httpx.Response(200, json={'access_token': 'access-synthetic', 'refresh_token': 'refresh-synthetic',
                  'id_token': self.signed(nonce=authorized['nonce'][0]), 'scope': authorized['scope'][0],
                  'expires_in': 3600, 'token_type': 'Bearer'})
        class FakeServer:
            def __init__(self, address, handler_class):
                self.handler_class = handler_class
                self.server_port = 1455
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def handle_request(self):
                callback = self.handler_class.__new__(self.handler_class)
                callback.path = '/auth/callback?code=synthetic-code&client_id=oaiapp_saved&state=' + authorized['state'][0]
                callback.headers = {'Host': '127.0.0.1:1455'}
                callback.wfile = io.BytesIO()
                callback.send_response = callback.send_header = callback.end_headers = lambda *args: None
                callback.do_GET()
        with httpx.Client(transport=httpx.MockTransport(handler)) as http, \
                patch('hidden_lab.chatgpt_auth.HTTPServer', FakeServer), patch('builtins.print') as output:
            self.assertTrue(login(store, open_browser=browser, http=http))
        self.assertEqual(store.state['active'], 'oaiapp_saved')
        self.assertEqual(len(store.state['accounts']), 1)
        form = parse_qs(seen[0].content.decode())
        self.assertEqual(form['client_id'], ['oaiapp_saved'])
        self.assertEqual(form['redirect_uri'], authorized['redirect_uri'])
        self.assertIn('code_verifier', form)
        self.assertNotIn('client_secret', form)
        self.assertNotIn('access-synthetic', str(output.call_args_list))

    def test_refresh_network_failure_preserves_credentials_but_revocation_clears_tokens(self):
        from hidden_lab.chatgpt_auth import AuthError, DIRECT_SCOPE, access_token
        original = {'client_id': 'oaiapp_saved', 'subject': 'offline-user', 'scopes': [DIRECT_SCOPE],
                    'expires_at': 0, 'access_token': 'expired-synthetic', 'refresh_token': 'old-synthetic'}
        for status, body, cleared in ((500, {'detail': 'secret-body'}, False),
                                      (400, {'error': 'invalid_grant'}, True)):
            store = MemoryStore({'active': 'oaiapp_saved', 'accounts': [dict(original)]})
            with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(status, json=body))) as http:
                with self.assertRaises(AuthError) as error:
                    access_token(store, http)
            self.assertNotIn('secret-body', str(error.exception))
            self.assertEqual('refresh_token' not in store.state['accounts'][0], cleared)
            self.assertEqual(store.state['accounts'][0]['client_id'], 'oaiapp_saved')

    def test_logout_clears_only_selected_account_and_retains_mapping_even_on_network_failure(self):
        from hidden_lab.chatgpt_auth import logout
        first = {'client_id': 'oaiapp_saved', 'subject': 'offline-user', 'scopes': ['openid'],
                 'access_token': 'access-synthetic', 'refresh_token': 'refresh-synthetic', 'id_token': 'id-synthetic'}
        second = {**first, 'client_id': 'oaiapp_other'}
        store = MemoryStore({'active': 'oaiapp_saved', 'host_id': 'stable-host', 'accounts': [first, second]})
        with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(500, json={'detail': 'secret-body'}))) as http:
            self.assertFalse(logout(store, http))
        self.assertEqual(store.state['host_id'], 'stable-host')
        self.assertNotIn('refresh_token', first)
        self.assertEqual(second['refresh_token'], 'refresh-synthetic')
        self.assertEqual(first['client_id'], 'oaiapp_saved')


def sse_event(kind, response=None, **fields):
    value = {'type': kind, 'sequence_number': 0, **fields}
    if response is not None:
        value['response'] = response
    return ('event: ' + kind + '\ndata: ' + json.dumps(value) + '\n\n').encode()


def completed_response(message):
    return {'id': 'offline-response', 'model': 'offline-returned-model', 'status': 'completed',
            'object': 'response', 'created_at': 0, 'error': None,
            'output': [{'type': 'message', 'id': 'offline-message', 'role': 'assistant', 'status': 'completed',
                        'content': [{'type': 'output_text', 'text': message, 'annotations': []}]}],
            'usage': {'input_tokens': 120, 'output_tokens': 40, 'total_tokens': 160,
                      'input_tokens_details': {'cached_tokens': 0}, 'output_tokens_details': {'reasoning_tokens': 12}}}


@unittest.skipUnless(openai is not None, 'richiede extra openai/chatgpt')
class SubscriptionStreamingTests(unittest.TestCase):
    def client(self, replies, settings=None):
        from hidden_lab.chatgpt_client import ChatGPTClient
        answers = iter(replies)
        seen = []
        def handler(request):
            seen.append(request)
            self.assertEqual(request.url.host, 'api.openai.com')
            self.assertEqual(request.headers['authorization'], 'Bearer synthetic-oauth')
            self.assertNotIn('OpenAI-Organization', request.headers)
            self.assertNotIn('OpenAI-Project', request.headers)
            response = next(answers)
            if isinstance(response, Exception):
                raise response
            return response
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'unused-api-key', 'OPENAI_ORG_ID': 'unused-org',
                                    'OPENAI_PROJECT_ID': 'unused-project', 'OPENAI_BASE_URL': 'https://invalid.example'}):
            client = ChatGPTClient(settings or AgentSettings('chosen-model', timeout=7),
                                   transport=httpx.MockTransport(handler), token_supplier=lambda: 'synthetic-oauth')
        self.addCleanup(client.close)
        return client, seen

    def request(self):
        with tempfile.TemporaryDirectory() as directory:
            return build_request(Session(Path(directory) / 's', config()).events, AgentSettings('chosen-model'), 'choose_next', 8, 8)

    def stream(self, message):
        return httpx.Response(200, headers={'Content-Type': 'text/event-stream'},
                              content=sse_event('response.completed', completed_response(message)))

    def delta_stream(self, message, *, snapshot=False):
        terminal = completed_response(message if snapshot else '')
        if not snapshot:
            terminal['output'] = []
        fields = {'item_id': 'offline-message', 'output_index': 0, 'content_index': 0}
        events = (sse_event('response.output_text.delta', delta=message[:17], **fields)
                  + sse_event('response.output_text.delta', delta=message[17:], **fields)
                  + sse_event('response.output_text.done', text=message, **fields)
                  + sse_event('response.completed', terminal))
        return httpx.Response(200, headers={'Content-Type': 'text/event-stream'}, content=events)

    def test_real_sdk_stream_and_native_usage_no_key_fallback(self):
        text = json.dumps({'message': conclusion()})
        client, seen = self.client([self.stream(text)])
        reply = client.complete(self.request())
        self.assertEqual(reply.text, text)
        self.assertEqual(reply.metadata['usage']['total_tokens'], 160)
        self.assertEqual(reply.metadata['returned_model'], 'offline-returned-model')
        body = json.loads(seen[0].content)
        self.assertEqual(seen[0].url.path, '/v1/responses')
        self.assertTrue(body['stream'])
        self.assertNotIn('max_output_tokens', body)
        self.assertNotIn('synthetic-oauth', json.dumps(body))
        self.assertEqual(len(seen), 1)

    def test_text_deltas_survive_completion_without_text_snapshot(self):
        text = json.dumps({'message': conclusion()})
        client, seen = self.client([self.delta_stream(text)])
        reply = client.complete(self.request())
        self.assertEqual(reply.text, text)
        self.assertEqual(reply.metadata['usage']['total_tokens'], 160)
        self.assertEqual(len(seen), 1)

    def test_snapshot_and_done_do_not_duplicate_deltas(self):
        text = json.dumps({'message': conclusion()})
        client, _ = self.client([self.delta_stream(text, snapshot=True)])
        reply = client.complete(self.request())
        self.assertEqual(reply.text, text)
        self.assertEqual(reply.metadata['provider_details']['text_delta_events'], 2)
        self.assertEqual(reply.metadata['provider_details']['text_source'], 'stream')

    def test_finalized_parts_are_ordered_and_done_without_deltas_is_supported(self):
        terminal = completed_response('')
        terminal['output'] = []
        events = (sse_event('response.output_text.done', text='}', item_id='offline', output_index=0, content_index=1)
                  + sse_event('response.output_text.done', text='{', item_id='offline', output_index=0, content_index=0)
                  + sse_event('response.completed', terminal))
        client, _ = self.client([httpx.Response(200, headers={'Content-Type': 'text/event-stream'}, content=events)])
        self.assertEqual(client.complete(self.request()).text, '{}')

    def test_partial_text_never_succeeds_without_completion_or_after_failure(self):
        prefix = sse_event('response.output_text.delta', delta='{}', item_id='offline', output_index=0, content_index=0)
        for suffix, expected in ((b'data: [DONE]\n\n', 'connection'),
                                 (sse_event('response.failed', {'status': 'failed', 'error': {'code': 'server_error', 'message': 'private'}}), 'provider_error')):
            client, seen = self.client([httpx.Response(200, headers={'Content-Type': 'text/event-stream'}, content=prefix + suffix)])
            with self.assertRaises(ProviderError) as error:
                client.complete(self.request())
            self.assertEqual(error.exception.code, expected)
            self.assertEqual(len(seen), 1)

    def test_conflicting_or_oversized_stream_text_is_rejected(self):
        fields = {'item_id': 'offline', 'output_index': 0, 'content_index': 0}
        prefix = sse_event('response.output_text.delta', delta='{}', **fields)
        for events in (prefix + sse_event('response.completed', completed_response('[]')),
                       prefix + sse_event('response.output_text.done', text='[]', **fields),
                       prefix + sse_event('response.output_text.delta', delta='x' * 65535, **fields)):
            client, _ = self.client([httpx.Response(200, headers={'Content-Type': 'text/event-stream'}, content=events)])
            with self.assertRaises(ProviderError) as error:
                client.complete(self.request())
            self.assertEqual(error.exception.code, 'request_rejected')

    def test_stream_refusals_and_tools_cannot_hide_in_empty_completion(self):
        terminal = completed_response('')
        terminal['output'] = []
        fields = {'item_id': 'offline', 'output_index': 0, 'content_index': 0}
        events = sse_event('response.refusal.delta', delta='private', **fields) + sse_event('response.completed', terminal)
        client, _ = self.client([httpx.Response(200, headers={'Content-Type': 'text/event-stream'}, content=events)])
        self.assertEqual(client.complete(self.request()).issue, 'refusal')
        events = (sse_event('response.output_item.added', output_index=0,
                           item={'type': 'function_call', 'id': 'offline', 'call_id': 'offline', 'name': 'read_file', 'arguments': '{}'})
                  + sse_event('response.completed', terminal))
        client, _ = self.client([httpx.Response(200, headers={'Content-Type': 'text/event-stream'}, content=events)])
        with self.assertRaises(ProviderError) as error:
            client.complete(self.request())
        self.assertEqual(error.exception.code, 'request_rejected')

    def test_safe_diagnostics_distinguish_empty_fenced_and_invalid_text(self):
        for value, syntax in (('', 'empty'), ('```json\n{}\n```', 'markdown_fence'),
                              ('private-synthetic-marker', 'invalid'), ('NaN', 'invalid'),
                              ('{"duplicate": 1, "duplicate": 2}', 'invalid'), ('{}', 'valid')):
            with self.subTest(syntax=syntax):
                client, _ = self.client([self.stream(value)])
                reply = client.complete(self.request())
                self.assertEqual(reply.metadata['provider_details']['json_syntax'], syntax)
                self.assertEqual(reply.metadata['provider_details']['response_text_bytes'], len(value.encode()))
                self.assertNotIn('private-synthetic-marker', json.dumps(reply.metadata))

    def test_stream_failure_incomplete_eof_and_http_error_never_retry(self):
        for response, expected in (
            (httpx.Response(503, json={'detail': 'synthetic-secret'}), 'service_unavailable'),
            (httpx.Response(429, json={'error': {'code': 'subscription_sharing_usage_limit_exceeded', 'message': 'synthetic-secret'}}), 'rate_limit'),
            (httpx.Response(200, headers={'Content-Type': 'text/event-stream'}, content=b'data: [DONE]\n\n'), 'connection'),
            (httpx.Response(200, headers={'Content-Type': 'text/event-stream'}, content=sse_event('response.failed',
                {'id': 'failed', 'status': 'failed', 'error': {'code': 'subscription_sharing_usage_limit_exceeded', 'message': 'synthetic-secret'}})), 'rate_limit'),
            (httpx.ReadTimeout('synthetic-secret'), 'timeout'),
        ):
            with self.subTest(expected=expected):
                client, seen = self.client([response])
                with self.assertRaises(ProviderError) as error:
                    client.complete(self.request())
                self.assertEqual(error.exception.code, expected)
                self.assertNotIn('synthetic-secret', str(error.exception))
                self.assertEqual(len(seen), 1)
        response = completed_response('partial')
        response['status'] = 'incomplete'
        client, seen = self.client([httpx.Response(200, headers={'Content-Type': 'text/event-stream'},
                                    content=sse_event('response.incomplete', response))])
        self.assertEqual(client.complete(self.request()).issue, 'incomplete_response')
        self.assertEqual(len(seen), 1)

    def test_complete_operator_cycle_modified_prediction_and_private_boundary(self):
        from hidden_lab.fake_client import demo_replies
        from hidden_lab.investigation import Investigation
        from hidden_lab.terminal import Terminal
        messages = demo_replies()
        messages[1]['experiment']['observation_interval'] = 0.5
        messages[3]['experiment']['observation_interval'] = 0.5
        messages[3]['experiment']['duration'] = 0.5
        messages[4]['points'] = messages[4]['points'][::2]
        client, seen = self.client([self.delta_stream(json.dumps({'message': m})) for m in messages])
        inputs = iter(['avvia', 'Breve va bene.', 'a', 'Prova.', 'e', 'esegui',
                       'm', '', '', '', '', '1', '', 'conferma', 'Allungo.', 'v', 'esegui'])
        with tempfile.TemporaryDirectory() as directory:
            session = Session(Path(directory) / 's', config('constant', 7.654321))
            runner = Investigation(session, client, AgentSettings('chosen-model', max_points=3),
                                   Terminal(lambda _: next(inputs), lambda _: None))
            self.assertTrue(runner.run())
            self.assertEqual((runner.calls, runner.turns, session.executed_count), (6, 6, 2))
            context = json.loads(json.loads(seen[4].content)['input'][0]['content'])['next_action']
            self.assertEqual(context['approved_experiment']['duration'], 1)
            self.assertEqual(context['prediction_times'], [0, 0.5, 1])
            kinds = [event['message']['type'] for event in session.events]
            self.assertLess(kinds.index('prediction'), kinds.index('verification'))
            for request in seen:
                for forbidden in ('synthetic-oauth', 'unused-api-key', '7.654321', '"seed"', 'README'):
                    self.assertNotIn(forbidden, request.content.decode())
            for path in session.directory.rglob('*.jsonl'):
                self.assertNotIn('synthetic-oauth', path.read_text(encoding='utf-8'))

    def test_rejection_invalid_correction_and_failure_after_observation(self):
        from hidden_lab.fake_client import demo_replies
        from hidden_lab.investigation import Investigation
        from hidden_lab.terminal import Terminal
        request = demo_replies()[1]
        client, seen = self.client([self.stream('malformed-secret'), self.stream(json.dumps({'message': request})),
                                  self.stream(json.dumps({'message': conclusion()}))])
        inputs = iter(['avvia', 'r', 'Rifiuto.'])
        with tempfile.TemporaryDirectory() as directory:
            session = Session(Path(directory) / 's', config())
            runner = Investigation(session, client, AgentSettings('chosen-model'), Terminal(lambda _: next(inputs), lambda _: None))
            self.assertTrue(runner.run())
            self.assertEqual((runner.calls, session.executed_count), (3, 0))
            self.assertNotIn('malformed-secret', seen[1].content.decode())
            history = json.loads(json.loads(seen[2].content)['input'][0]['content'])['history']
            self.assertEqual(history[-1]['message']['action'], 'reject')
        client, seen = self.client([self.stream(json.dumps({'message': request})), httpx.Response(500, json={'detail': 'secret-body'})])
        inputs = iter(['avvia', 'a', 'Prova.', 'e', 'esegui'])
        with tempfile.TemporaryDirectory() as directory:
            session = Session(Path(directory) / 's', config())
            output = []
            runner = Investigation(session, client, AgentSettings('chosen-model'), Terminal(lambda _: next(inputs), output.append))
            self.assertFalse(runner.run())
            self.assertEqual((runner.calls, session.executed_count), (2, 1))
            self.assertEqual(len(seen), 2)
            audit = [json.loads(line) for line in (session.directory / 'private/model_calls.jsonl').read_text().splitlines()]
            self.assertEqual(audit[-1]['http_status'], 500)
            self.assertNotIn('secret-body', '\n'.join(output))

    def test_models_catalog_is_not_an_inference_or_default_selection(self):
        client, seen = self.client([httpx.Response(200, json={'models': [
                {'slug': 'allowed', 'display_name': 'Allowed', 'visibility': 'list'},
                {'slug': 'hidden', 'display_name': 'Hidden', 'visibility': 'hide'}]})])
        self.assertEqual(client.models(), [{'slug': 'allowed', 'display_name': 'Allowed'}])
        self.assertEqual((seen[0].method, seen[0].url.path), ('GET', '/v1/models'))

    def test_local_output_limit_refusal_and_tool_calls_do_not_become_messages(self):
        too_large = completed_response('x' * 65537)
        tool = completed_response('{}')
        tool['output'] = [{'type': 'function_call', 'id': 'offline', 'call_id': 'offline', 'name': 'read_file', 'arguments': '{}'}]
        for response in (too_large, tool):
            client, seen = self.client([httpx.Response(200, headers={'Content-Type': 'text/event-stream'},
                                         content=sse_event('response.completed', response))])
            with self.assertRaises(ProviderError) as error:
                client.complete(self.request())
            self.assertEqual(error.exception.code, 'request_rejected')
            self.assertEqual(len(seen), 1)
        refusal = completed_response('{}')
        refusal['output'][0]['content'] = [{'type': 'refusal', 'refusal': 'Declined.'}]
        client, _ = self.client([httpx.Response(200, headers={'Content-Type': 'text/event-stream'}, content=sse_event('response.completed', refusal))])
        self.assertEqual(client.complete(self.request()).issue, 'refusal')


@unittest.skipUnless(openai is not None, 'richiede extra chatgpt')
class SubscriptionPilotTests(unittest.TestCase):
    def test_blank_confirmation_and_noninteractive_inputs_never_call_client(self):
        from hidden_lab.chatgpt_cli import run_pilot
        from hidden_lab.protocol import ValidationError
        from types import SimpleNamespace
        with patch('hidden_lab.chatgpt_client.ChatGPTClient') as client, \
                patch('sys.stdin.isatty', return_value=False):
            with self.assertRaises(ValidationError):
                run_pilot(SimpleNamespace(model=None))
            client.assert_not_called()
        with patch('hidden_lab.chatgpt_client.ChatGPTClient') as client, patch('sys.stdin.isatty', return_value=True), \
                patch('builtins.input', return_value=''), patch('builtins.print'):
            self.assertEqual(run_pilot(SimpleNamespace(model=None)), 2)
            client.assert_not_called()

    def test_pilot_explicit_model_and_real_forge_with_simulated_investigation(self):
        from hidden_lab.chatgpt_cli import run_pilot
        from hidden_lab.cli import main as lab_main
        from hidden_lab.fake_client import SimulatedClient, demo_replies
        from hidden_lab.terminal import Terminal
        from types import SimpleNamespace
        replies = demo_replies()
        for index in (1, 3):
            replies[index]['experiment']['observation_interval'] = 0.5
        replies[4]['points'] = replies[4]['points'][::2]
        client = SimulatedClient(replies)
        commands = []
        def run(command):
            commands.append(command)
            return lab_main(command)
        catalog = SimpleNamespace(models=lambda: [{'slug': 'offline-selected', 'display_name': 'Offline'}], close=lambda: None)
        inputs = iter(['piano', 'avvia', 'Breve.', 'a', 'Prova.', 'e', 'esegui', 'a', 'Verifica.', 'v', 'esegui'])
        previous = Path.cwd()
        with tempfile.TemporaryDirectory() as directory:
            try:
                os.chdir(directory)
                with patch('sys.stdin.isatty', return_value=True), patch('builtins.input', side_effect=lambda _: next(inputs)), \
                        patch('builtins.print'), patch('hidden_lab.chatgpt_client.ChatGPTClient', return_value=catalog), \
                        patch('hidden_lab.provider_factory.create_real_client', return_value=client), \
                        patch('hidden_lab.terminal.Terminal', side_effect=lambda: Terminal(lambda _: next(inputs), lambda _: None)), \
                        patch('hidden_lab.cli.main', side_effect=run):
                    self.assertEqual(run_pilot(SimpleNamespace(model='offline-selected')), 0)
                self.assertEqual([cmd[:2] for cmd in commands[:2]], [['forge', 'generate'], ['forge', 'check']])
                self.assertIn('chatgpt', commands[-1])
                self.assertIn('offline-selected', commands[-1])
                self.assertEqual(len(client.payloads), 6)
                events = next(Path('sessions').glob('*/public/events.jsonl')).read_text(encoding='utf-8')
                self.assertEqual(events.count('"type": "observation"'), 2)
                self.assertIn('"type": "conclusion"', events)
                for payload in client.payloads:
                    self.assertNotIn('"seed"', json.dumps(payload))
                    self.assertNotIn('"world"', json.dumps(payload))
            finally:
                os.chdir(previous)


if __name__ == '__main__':
    unittest.main()
