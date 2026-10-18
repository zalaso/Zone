"""Personal web plan: synthetic model/OAuth only, never an external inference."""
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from hidden_lab.chatgpt_auth import AuthError, CredentialStore, DIRECT_SCOPE, access_token
from hidden_lab.chatgpt_client import chatgpt_payload
from hidden_lab.chatgpt_vm import import_registration, transfer_to_vps, import_command
from hidden_lab.provider_base import AgentSettings, ModelReply, ProviderError
from hidden_lab.web_agent import OfflineLabClient, safe_generation
from hidden_lab.world_forge import generate_world

if importlib.util.find_spec('fastapi'):
    from fastapi.testclient import TestClient
    from hidden_lab.backend import RateLimiter, create_app
    from hidden_lab.backend_store import SQLiteRepository
    from hidden_lab.identity_store import IdentityStore


class SyntheticPlan(OfflineLabClient):
    """Policy is offline; provider label tests the personal-plan access boundary."""
    provider = 'chatgpt'
    generation_settings = {'authentication': 'chatgpt_plan_oauth', 'stream': True, 'store': False,
                           'tools': [], 'max_output_tokens': None, 'max_output_tokens_supported': False,
                           'local_response_limit_bytes': 65536, 'text_extraction_version': 2}

    def __init__(self):
        self.requests = []
        self.replies = []

    def complete(self, request):
        self.requests.append(request)
        if self.replies:
            reply = self.replies.pop(0)
            if isinstance(reply, Exception):
                raise reply
            return reply
        return super().complete(request)


@unittest.skipUnless(importlib.util.find_spec('fastapi'), 'Installare extra backend')
class PersonalWebPlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.world = generate_world(125987, 1, 2)

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.repo = SQLiteRepository(Path(temp.name) / 'web.db', [self.world])
        store = IdentityStore(self.repo)
        self.owner = store.create('owner', 'admin', bootstrap=True)
        self.member = store.create('guest', 'member', actor=self.owner['account_id'])
        self.staff = store.create('staff', 'admin', actor=self.owner['account_id'])
        self.model = SyntheticPlan()
        self.settings = AgentSettings('explicit-synthetic-model', max_calls=20, max_points=3)
        self.client = self.app()

    def app(self, **kwargs):
        app = create_app(repository=self.repo, auth_mode='accounts', public_origin='https://zone.test',
            agent_client=self.model, agent_settings=self.settings,
            rate_limiter=RateLimiter(read=10000, write=10000, run=10000),
            **{'agent_owner': self.owner['account_id'], **kwargs})
        client = TestClient(app, base_url='https://zone.test')
        self.addCleanup(client.close)
        return client

    def headers(self, account=None):
        return {'Authorization': 'Bearer ' + (account or self.owner)['login_key']}

    def state(self, sid, account=None):
        reply = self.client.get('/v1/sessions/' + sid, headers=self.headers(account))
        self.assertEqual(reply.status_code, 200, reply.text)
        return reply.json()

    def create(self, account=None):
        reply = self.client.post('/v1/sessions', headers=self.headers(account),
            json={'world_id': self.world['world_id'], 'mode': 'watch_agent'})
        self.assertEqual(reply.status_code, 201, reply.text)
        return reply.json()['session_id']

    def step(self, sid, account=None):
        return self.client.post('/v1/sessions/' + sid + '/agent/step', headers=self.headers(account),
            json={'expected_version': self.state(sid)['version']})

    def advance(self, sid, account=None):
        reply = self.step(sid, account)
        self.assertEqual(reply.status_code, 200, reply.text)
        return reply.json()

    def message(self, sid, message):
        reply = self.client.post('/v1/sessions/' + sid + '/messages', headers=self.headers(),
            json={'expected_version': self.state(sid)['version'], 'message': message})
        self.assertEqual(reply.status_code, 200, reply.text)

    def run_experiment(self, sid):
        state = self.state(sid)
        reply = self.client.post('/v1/sessions/' + sid + '/run', headers=self.headers(),
            json={'expected_version': state['version'], 'request_id': state['pending_request_id']})
        self.assertEqual(reply.status_code, 200, reply.text)

    def test_owner_routing_and_staff_cannot_consume_another_persons_plan(self):
        for account, expected in ((self.owner, 'chatgpt'), (self.member, 'offline_baseline'), (self.staff, 'offline_baseline')):
            modes = self.client.get('/v1/modes', headers=self.headers(account)).json()
            self.assertEqual(modes['agent']['provider'], expected)
            sid = self.create(account)
            self.assertEqual(self.advance(sid, account)['agent']['provider'], expected)
        sid = self.create()
        before = len(self.model.requests)
        self.assertEqual(self.step(sid, self.staff).status_code, 403)
        self.assertEqual(self.step(sid, self.member).status_code, 404)
        self.assertEqual(len(self.model.requests), before)
        self.assertEqual(self.state(sid)['agent']['calls'], 0)
        self.assertEqual(self.advance(sid)['agent']['calls'], 1)

    def test_only_own_sessions_can_consume_plan_even_with_staff_supervision(self):
        sid = self.create(self.member)
        # Represent a historic/incorrectly imported real profile owned by another account.
        with self.repo._connect() as db:
            db.execute('UPDATE session_profiles SET profile_json=? WHERE session_id=?',
                (json.dumps({'mode': 'watch_agent', 'managed_agent': True,
                    'agent': self.client.get('/v1/modes', headers=self.headers()).json()['agent']}), sid))
        self.assertEqual(self.step(sid).status_code, 403)
        self.assertEqual(self.model.requests, [])

    def test_full_cycle_rejection_modify_prediction_correction_network_and_conclusion(self):
        self.model.replies = [ModelReply('malformed', {})]
        sid = self.create()
        self.advance(sid)  # correction -> initial hypothesis
        self.assertEqual(self.state(sid)['agent']['invalid_responses'], 1)
        self.advance(sid)
        rid = self.state(sid)['pending_request_id']
        self.message(sid, {'type': 'operator_decision', 'request_id': rid, 'action': 'reject', 'reason': 'Altro lancio.'})
        self.advance(sid)
        rid = self.state(sid)['pending_request_id']
        experiment = copy.deepcopy(self.repo.read_session(sid)['events'][-1]['message']['experiment'])
        experiment['initial_velocity']['x'] = 8
        experiment['duration'] = .25
        self.message(sid, {'type': 'operator_decision', 'request_id': rid, 'action': 'modify',
            'reason': 'Verifica breve.', 'modified_experiment': experiment})
        self.message(sid, {'type': 'execution_mode', 'request_id': rid, 'mode': 'verification'})
        self.advance(sid)
        self.assertEqual(self.model.requests[-1].context['approved_experiment'], experiment)
        self.assertEqual(self.state(sid)['executed_experiments'], 0)
        self.run_experiment(sid)
        self.model.replies = [ProviderError('server_error')]
        calls = len(self.model.requests)
        self.assertEqual(self.step(sid).status_code, 503)
        self.assertEqual(len(self.model.requests), calls + 1)
        self.assertEqual(self.state(sid)['executed_experiments'], 1)
        for _ in range(20):
            state = self.state(sid)
            if state['status'] == 'scored':
                break
            if state['status'] == 'awaiting_decision':
                self.message(sid, {'type': 'operator_decision', 'request_id': state['pending_request_id'], 'action': 'approve', 'reason': 'Misura.'})
            elif state['status'] == 'awaiting_mode':
                self.message(sid, {'type': 'execution_mode', 'request_id': state['pending_request_id'], 'mode': 'exploration'})
            elif state['status'] == 'ready_to_run':
                self.run_experiment(sid)
            else:
                self.advance(sid)
        self.assertEqual(self.state(sid)['status'], 'scored')
        self.assertEqual(self.state(sid)['executed_experiments'], 2)
        events = self.repo.read_session(sid)['events']
        kinds = [e['message']['type'] for e in events]
        self.assertLess(kinds.index('prediction'), kinds.index('execution_started'))
        for kind in ('hypothesis', 'observation', 'verification', 'conclusion', 'scientific_submission'):
            self.assertIn(kind, kinds)
        # Inject private metadata at every public event boundary; projection must drop it.
        poisoned = copy.deepcopy(events)
        for e in poisoned:
            e['message']['private'] = {'truth': 'PRIVATE_TRUTH_SENTINEL'}
        from hidden_lab.backend_state import LabState
        from hidden_lab.web_agent import build_web_request
        # First request is also checked at the actual provider payload boundary.
        for request in self.model.requests:
            body = json.dumps(chatgpt_payload(request))
            for secret in (self.owner['login_key'], self.owner['account_id'], 'PRIVATE_TRUTH_SENTINEL', '"seed"', '"config"'):
                self.assertNotIn(secret, body)
        # Use an open history (before conclusion) to test adversarial projection explicitly.
        partial = poisoned[:kinds.index('conclusion')]
        request = build_web_request(partial, self.settings, LabState(partial, 2), 5, 5)
        self.assertNotIn('PRIVATE_TRUTH_SENTINEL', json.dumps(chatgpt_payload(request)))
        audit = self.client.get('/v1/sessions/' + sid + '/agent/audit', headers=self.headers()).json()
        self.assertEqual(audit['calls'][0]['outcome'], 'invalid')
        self.assertNotIn(self.owner['login_key'], json.dumps(audit))
        self.assertEqual(safe_generation(self.model)['max_output_tokens_supported'], False)

    def test_historical_offline_limits_and_restart_do_not_change_or_use_plan(self):
        from hidden_lab.web_agent import safe_generation
        sid = self.create(self.member)
        old = AgentSettings('offline-affine-v1', max_points=9, max_calls=8)
        profile = {'mode': 'watch_agent', 'managed_agent': True, 'agent': {
            'provider': 'offline_baseline', 'model': old.model, 'real_model': False,
            'settings': old.to_dict(), 'generation_settings': safe_generation(OfflineLabClient())}}
        with self.repo._connect() as db:
            db.execute('UPDATE session_profiles SET profile_json=? WHERE session_id=?', (json.dumps(profile), sid))
        self.client = self.app()
        state = self.advance(sid, self.member)
        self.assertEqual(state['agent']['settings']['max_points'], 9)
        self.assertEqual(self.model.requests, [])

    @unittest.skipUnless(importlib.util.find_spec('openai'), 'Installare extra chatgpt')
    def test_actual_sdk_stream_on_web_route_with_mock_http_and_native_usage(self):
        import httpx
        from hidden_lab.chatgpt_client import ChatGPTClient
        from test_chatgpt import sse_event, completed_response
        seen = []
        def handler(request):
            body = json.loads(request.content)
            seen.append(body)
            public = json.loads(body['input'][0]['content'])
            if public['next_action']['phase'] == 'submission':
                probes = next(e['message']['probes'] for e in public['history'] if e['message']['type'] == 'probe_challenge')
                message = {'type': 'scientific_submission', 'predictions': [
                    {'probe_id': p['probe_id'], 'ax': 0, 'ay': 0} for p in probes]}
            else:
                message = {'type': 'conclusion', 'final_hypothesis_id': None, 'summary': 'Informazioni insufficienti.',
                    'evidence': [], 'limits': ['Nessuna misura.'], 'alternatives': ['Leggi diverse compatibili.']}
            return httpx.Response(200, headers={'Content-Type': 'text/event-stream'},
                content=sse_event('response.completed', completed_response(json.dumps({'message': message}))))
        self.model = ChatGPTClient(self.settings, transport=httpx.MockTransport(handler),
                                  token_supplier=lambda: 'SYNTHETIC_OAUTH_ONLY')
        self.addCleanup(self.model.close)
        self.client = self.app()
        sid = self.create()
        self.advance(sid)
        self.assertEqual(self.advance(sid)['status'], 'scored')
        calls = self.repo.read_session(sid)['calls']
        self.assertEqual(len(seen), 2)
        self.assertEqual(calls[0]['usage']['total_tokens'], 160)
        self.assertEqual(calls[0]['generation_settings']['authentication'], 'chatgpt_plan_oauth')
        for body in seen:
            self.assertTrue(body['stream'])
            self.assertFalse(body['store'])
            self.assertEqual(body['tools'], [])
            self.assertNotIn('max_output_tokens', body)
            for secret in ('SYNTHETIC_OAUTH_ONLY', self.owner['login_key'], self.owner['account_id'], '"seed"', '"config"'):
                self.assertNotIn(secret, json.dumps(body))

    def test_missing_unknown_disabled_owner_fails_closed(self):
        for invalid in (None, 'bad', '0' * 32):
            with self.assertRaises(ValueError):
                self.app(agent_owner=invalid)
        with self.repo._connect() as db:
            db.execute('UPDATE accounts SET enabled=0 WHERE id=?', (self.owner['account_id'],))
        with self.assertRaises(ValueError):
            self.app()


class VMTransferTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.local = CredentialStore(Path(temp.name) / 'local')
        self.remote = CredentialStore(Path(temp.name) / 'vm')
        self.account = {'client_id': 'synthetic-client', 'subject': 'synthetic-subject',
            'access_token': 'ACCESS_SENTINEL', 'refresh_token': 'REFRESH_SENTINEL', 'id_token': 'ID_SENTINEL',
            'scopes': [DIRECT_SCOPE], 'expires_at': 4000000000, 'label': 'Synthetic'}
        with self.local.lock():
            state = self.local.load()
            self.local_host = state['host_id']
            state.update(active=self.account['client_id'], accounts=[copy.deepcopy(self.account),
                {'client_id': 'other', 'access_token': 'unrelated-account'}])
            self.local.save(state)
        with self.remote.lock():
            self.remote_host = self.remote.load()['host_id']
            state = self.remote.load()
            # load on a new store generates a host: persist exactly the chosen host.
            state['host_id'] = self.remote_host
            self.remote.save(state)

    def runner(self, command, **kwargs):
        self.assertEqual(command, import_command('synthetic-host', 'synthetic-container'))
        self.assertTrue(kwargs['capture_output'])
        self.assertNotIn('SENTINEL', ' '.join(command))
        value = json.loads(kwargs['input'])
        self.assertNotIn('host_id', value)
        self.assertNotIn('unrelated-account', kwargs['input'])
        return SimpleNamespace(returncode=0, stdout=json.dumps(import_registration(self.remote, kwargs['input'])))

    def test_transfer_preserves_vm_host_moves_selected_tokens_and_has_no_inference(self):
        result = transfer_to_vps(self.local, ssh_host='synthetic-host', container='synthetic-container', runner=self.runner)
        self.assertEqual(result, {'transferred': True, 'local_tokens_removed': True, 'inferences': 0})
        with self.remote.lock():
            state = self.remote.load()
            self.assertEqual(state['host_id'], self.remote_host)
            self.assertNotEqual(state['host_id'], self.local_host)
            self.assertEqual(state['accounts'], [self.account])
        with self.local.lock():
            state = self.local.load()
            for key in ('access_token', 'refresh_token', 'id_token'):
                self.assertNotIn(key, state['accounts'][0])
            self.assertEqual(state['accounts'][1]['access_token'], 'unrelated-account')

    def test_transfer_requires_explicit_safe_destination_and_binds_pending_retry(self):
        def forbidden(*args, **kwargs):
            self.fail('No SSH call is allowed for an invalid or changed destination')
        for host, container in ((None, None), ('-option', 'zone'), ('host;command', 'zone'), ('host', 'zone;command')):
            with self.assertRaises(AuthError):
                transfer_to_vps(self.local, ssh_host=host, container=container, runner=forbidden)
        def lost(*args, **kwargs):
            raise TimeoutError('synthetic failure')
        with self.assertRaises(AuthError):
            transfer_to_vps(self.local, ssh_host='synthetic-host', container='synthetic-container', runner=lost)
        with self.assertRaises(AuthError) as error:
            transfer_to_vps(self.local, ssh_host='other-host', container='synthetic-container', runner=forbidden)
        self.assertNotIn('SENTINEL', str(error.exception))

    def test_lost_ack_blocks_local_inference_retry_does_not_overwrite_rotated_tokens(self):
        def lost(command, **kwargs):
            self.runner(command, **kwargs)
            raise TimeoutError('REFRESH_SENTINEL')
        with self.assertRaises(AuthError) as raised:
            transfer_to_vps(self.local, ssh_host='synthetic-host', container='synthetic-container', runner=lost)
        self.assertNotIn('SENTINEL', str(raised.exception))
        with self.local.lock():
            with self.assertRaises(AuthError):
                access_token(self.local, None)
        with self.remote.lock():
            state = self.remote.load()
            state['accounts'][0]['refresh_token'] = 'rotated-on-vm'
            self.remote.save(state)
        transfer_to_vps(self.local, ssh_host='synthetic-host', container='synthetic-container', runner=self.runner)
        with self.remote.lock():
            self.assertEqual(self.remote.load()['accounts'][0]['refresh_token'], 'rotated-on-vm')

    def test_invalid_or_conflicting_transfer_never_replaces_credentials(self):
        raw = json.dumps({'transfer_id': '11111111-1111-4111-8111-111111111111', 'account': self.account})
        import_registration(self.remote, raw)
        for invalid in ('x', '{}', 'x' * 256001, raw.replace('11111111-', '22222222-')):
            with self.assertRaises(AuthError) as raised:
                import_registration(self.remote, invalid)
            self.assertNotIn('SENTINEL', str(raised.exception))
        with self.remote.lock():
            self.assertEqual(self.remote.load()['accounts'], [self.account])

    def test_explicit_cli_consent_and_server_flags_before_client_construction(self):
        from hidden_lab import chatgpt_cli, server_cli
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest='command')
        chatgpt_cli.add_parser(sub)
        server_cli.add_parser(sub)
        with patch('hidden_lab.chatgpt_vm.transfer_to_vps') as transfer:
            with self.assertRaises(ValueError):
                chatgpt_cli.run_command(parser.parse_args(['chatgpt', 'transfer-vps']))
            transfer.assert_not_called()
        with patch('hidden_lab.provider_factory.create_real_client') as factory:
            for extra in (['--agent-provider', 'chatgpt'], ['--agent-owner', '0'*32],
                          ['--chatgpt-credentials-dir', 'unused']):
                args = parser.parse_args(['serve', '--db', 'unused', '--auth-mode', 'accounts', *extra])
                with self.assertRaises(ValueError):
                    server_cli.run_command(args)
            factory.assert_not_called()


class ClientConcurrencyTests(unittest.TestCase):
    def test_concurrent_web_calls_do_not_refresh_or_generate_twice(self):
        from threading import Event, Thread
        from hidden_lab.chatgpt_client import ChatGPTClient
        from threading import Lock
        client = ChatGPTClient.__new__(ChatGPTClient)
        client._inference_lock = Lock()
        entered, release = Event(), Event()
        def slow(_request):
            entered.set()
            release.wait(3)
        client._complete = slow
        thread = Thread(target=client.complete, args=(None,))
        thread.start()
        self.assertTrue(entered.wait(2))
        try:
            with self.assertRaises(ProviderError) as raised:
                client.complete(None)
            self.assertEqual(raised.exception.code, 'rate_limit')
        finally:
            release.set()
            thread.join(3)
