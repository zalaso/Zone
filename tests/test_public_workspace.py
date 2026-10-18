"""Public workspace boundaries with synthetic credentials and injected models only."""

import base64
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
import importlib.util
import json
from pathlib import Path
import tempfile
import time
import unittest

if importlib.util.find_spec('fastapi'):
    from fastapi.testclient import TestClient
    from hidden_lab.backend import RateLimiter, create_app
    from hidden_lab.backend_store import SQLiteRepository
    from hidden_lab.connector_cli import process_job, validate_origin
    from hidden_lab.identity_store import IdentityStore
    from hidden_lab.protocol import ValidationError
    from hidden_lab.provider_base import ModelReply, ProviderError
    from hidden_lab.web_agent import OfflineLabClient
    from hidden_lab.world_forge import generate_world


@unittest.skipUnless(importlib.util.find_spec('fastapi') and importlib.util.find_spec('cryptography'), 'Extra workspace')
class PublicWorkspaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.world = generate_world(568043, 1, 1)
        cls.origin = 'https://workspace.test'

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = SQLiteRepository(Path(self.temp.name) / 'workspace.db', [self.world])
        self.identity = IdentityStore(self.repo)
        self.admin = self.identity.create('admin', 'admin', bootstrap=True)
        self.requests, self.keys = [], []
        outer = self

        class Simulated(OfflineLabClient):
            def complete(self, request):
                outer.requests.append(request)
                if outer.failure:
                    raise ProviderError('server_error')
                if outer.malformed:
                    outer.malformed = False
                    return ModelReply('not JSON', {})
                return super().complete(request)

            def close(self):
                pass

        def factory(provider, settings, *, api_key):
            self.keys.append((provider, api_key))
            return Simulated()

        self.failure, self.malformed = False, False
        self.app = create_app(repository=self.repo, auth_mode='accounts', public_origin=self.origin,
            public_workspace=True, open_registration=True, connection_key=base64.urlsafe_b64encode(b'v' * 32),
            connection_factory=factory, rate_limiter=RateLimiter(read=10000, write=10000, run=10000))
        self.alice = self.client()
        self.alice_data = self.register(self.alice, 'alice')
        self.bob = self.client()
        self.bob_data = self.register(self.bob, 'bob')
        self.counter = 0

    def client(self):
        client = TestClient(self.app, base_url=self.origin)
        self.addCleanup(client.close)
        return client

    def register(self, client, handle):
        result = client.post('/v1/auth/register', headers={'Origin': self.origin},
                             json={'handle': handle, 'password': 'synthetic-password-123'})
        self.assertEqual(result.status_code, 200, result.text)
        self.assertIn('HttpOnly', result.headers['set-cookie'])
        self.assertIn('Secure', result.headers['set-cookie'])
        return result.json()

    def post(self, path, body, *, client=None, data=None, expected=200, key=None):
        self.counter += 1
        result = (client or self.alice).post('/v1' + path, json=body, headers={
            'Origin': self.origin, 'X-Zone-CSRF': (data or self.alice_data)['csrf'],
            'Idempotency-Key': key or f'workspace-test-{self.counter:06d}'})
        self.assertEqual(result.status_code, expected, result.text)
        return result.json()

    def connection(self, provider='openai', model='synthetic-model', transport='api'):
        return self.post('/my/connections', {'label': 'Test personale', 'provider': provider, 'model': model,
            'transport': transport, **({'api_key': 'synthetic-api-key-alice'} if transport == 'api' else {})}, expected=201)

    def session(self):
        return self.post('/sessions', {'world_id': self.world['world_id'], 'mode': 'watch_agent'}, expected=201)

    def step(self, state):
        return self.post(f"/sessions/{state['session_id']}/agent/step", {'expected_version': state['version']})

    def message(self, state, message):
        return self.post(f"/sessions/{state['session_id']}/messages", {'expected_version': state['version'], 'message': message})

    def propose(self, state):
        while state['status'] == 'discovering':
            state = self.step(state)
        self.assertEqual(state['status'], 'awaiting_decision')
        return state

    def test_registration_recovery_csrf_and_no_secret_in_database(self):
        connector = self.connection('ollama', 'synthetic-local', 'connector')
        self.assertNotIn('login_key', self.alice_data)
        self.assertEqual(self.alice_data['account']['role'], 'member')
        with self.repo._connect() as db:
            serialized = json.dumps(list(db.iterdump()))
        self.assertNotIn('synthetic-password-123', serialized)
        self.assertNotIn(self.alice_data['recovery_code'], serialized)
        self.assertEqual(self.alice.post('/v1/my/connections/select', json={'connection_id': None}).status_code, 403)
        replacement = self.alice.post('/v1/auth/recover', headers={'Origin': self.origin}, json={
            'handle': 'alice', 'recovery_code': self.alice_data['recovery_code'], 'password': 'replacement-password-123'})
        self.assertEqual(replacement.status_code, 200)
        self.assertEqual(self.alice.get('/v1/auth/me').status_code, 401)
        self.assertEqual(self.client().post('/v1/connector/poll', json={},
            headers={'X-Zone-Connector': connector['connector_key']}).status_code, 401)
        replay = self.alice.post('/v1/auth/recover', headers={'Origin': self.origin}, json={
            'handle': 'alice', 'recovery_code': self.alice_data['recovery_code'], 'password': 'replacement-password-123'})
        self.assertEqual(replay.status_code, 401)
        login = self.alice.post('/v1/auth/password', headers={'Origin': self.origin},
                                json={'handle': 'alice', 'password': 'replacement-password-123'})
        self.assertEqual(login.status_code, 200)
        self.assertEqual(self.alice.post('/v1/auth/register', headers={'Origin': self.origin}, json={
            'handle': 'evil', 'password': 'synthetic-password-123', 'role': 'admin'}).status_code, 422)

    def test_api_ownership_encryption_pinning_and_revocation(self):
        cid = self.connection()['id']
        state = self.session()
        self.post('/my/connections/select', {'connection_id': cid}, client=self.bob, data=self.bob_data, expected=404)
        self.post('/my/connections/select', {'connection_id': {}}, expected=422)
        self.post('/my/connections', {'label': 'bad', 'provider': 'openai', 'model': 'test', 'transport': 'api',
            'api_key': 'synthetic-api-key', 'base_url': 'http://127.0.0.1'}, expected=422)
        self.assertEqual(self.requests, [])
        with self.repo._connect() as db:
            stored = db.execute('SELECT secret FROM ai_connections WHERE id=?', (cid,)).fetchone()[0]
        self.assertNotIn(b'synthetic-api-key-alice', stored)
        self.assertNotIn('synthetic-api-key-alice', self.alice.get('/v1/my/connections').text)
        self.connection(model='different-model')
        state = self.propose(state)
        self.assertEqual(self.requests[0].model, 'synthetic-model')
        self.assertEqual(self.keys, [('openai', 'synthetic-api-key-alice')] * 2)
        self.assertEqual(self.bob.get('/v1/sessions/' + state['session_id']).status_code, 404)
        self.alice.delete('/v1/my/connections/' + cid, headers={'Origin': self.origin, 'X-Zone-CSRF': self.alice_data['csrf']})
        state = self.message(state, {'type': 'operator_decision', 'request_id': state['pending_request_id'], 'action': 'reject', 'reason': 'Rifiuto operativo.'})
        self.post(f"/sessions/{state['session_id']}/agent/step", {'expected_version': state['version']}, expected=409)
        self.assertEqual(len(self.requests), 2)

    def test_full_cycle_with_simulated_api_no_private_truth(self):
        self.connection()
        state = self.propose(self.session())
        state = self.message(state, {'type': 'operator_decision', 'request_id': state['pending_request_id'], 'action': 'approve', 'reason': 'Prova offline.'})
        state = self.message(state, {'type': 'execution_mode', 'request_id': state['pending_request_id'], 'mode': 'exploration'})
        path = f"/sessions/{state['session_id']}/run"
        state = self.post(path, {'expected_version': state['version'], 'request_id': state['pending_request_id']})
        self.assertEqual(state['executed_experiments'], 1)
        for _ in range(5):
            if state['status'] == 'scored':
                break
            state = self.step(state)
        self.assertEqual(state['status'], 'scored')
        self.assertEqual(state['executed_experiments'], 1)
        wire = json.dumps([asdict(r) for r in self.requests])
        for private in ('synthetic-api-key-alice', self.alice_data['recovery_code'], self.alice_data['account']['account_id'],
                        '"config":', '"private_truth":', 'record_json', 'README'):
            self.assertNotIn(private, wire)
        self.assertNotIn(json.dumps(self.world['config']['seed']), wire)

    def test_invalid_and_network_errors_count_calls_without_launches(self):
        self.connection()
        self.malformed = True
        state = self.step(self.session())
        self.assertEqual(state['agent']['invalid_responses'], 1)
        self.assertEqual(state['agent']['calls'], 2)
        state = self.propose(state)
        state = self.message(state, {'type': 'operator_decision', 'request_id': state['pending_request_id'], 'action': 'reject', 'reason': 'Rifiuto.'})
        self.failure = True
        self.post(f"/sessions/{state['session_id']}/agent/step", {'expected_version': state['version']}, expected=503)
        result = self.alice.get('/v1/sessions/' + state['session_id']).json()
        self.assertEqual(result['executed_experiments'], 0)
        self.assertEqual(result['agent']['calls'], 4)

    def test_connector_scope_single_claim_and_public_wire(self):
        conn = self.connection('chatgpt', 'synthetic-local', 'connector')
        worker = self.client()
        headers = {'X-Zone-Connector': conn['connector_key']}
        self.assertEqual(worker.get('/v1/my/sessions', headers=headers).status_code, 401)
        self.assertEqual(worker.post('/v1/connector/poll', headers=headers, json={}).json(), {'job': None})
        state = self.session()
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(self.step, state)
            job = None
            for _ in range(60):
                job = worker.post('/v1/connector/poll', headers=headers, json={}).json()['job']
                if job:
                    break
                time.sleep(.05)
            self.assertIsNotNone(job)
            self.assertEqual(worker.post('/v1/connector/poll', headers=headers, json={}).json(), {'job': None})
            wire = json.dumps(job)
            for secret in (conn['connector_key'], self.alice_data['account']['account_id'], 'private_truth', 'law_ast'):
                self.assertNotIn(secret, wire)
            body = process_job(job, 'synthetic-local', OfflineLabClient())
            self.assertEqual(worker.post('/v1/connector/jobs/' + job['id'], headers=headers,
                json={'lease': job['lease'], 'error': {}}).status_code, 422)
            self.assertEqual(worker.post('/v1/connector/jobs/' + job['id'], headers=headers, json={**body, 'lease': 'wrong'}).status_code, 409)
            self.assertEqual(worker.post('/v1/connector/jobs/' + job['id'], headers=headers, json=body).status_code, 200)
            self.assertEqual(future.result()['status'], 'discovering')
        self.assertEqual(worker.post('/v1/connector/jobs/' + job['id'], headers=headers, json=body).status_code, 409)
        self.assertEqual(self.requests, [])
        with self.repo._connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM connector_jobs').fetchone()[0], 0)

    def test_world_capacity_is_atomic_and_origin_is_strict(self):
        owner = self.alice_data['account']['account_id']
        first = generate_world(5001, 1, 1)
        self.repo.register_world(first, owner=owner, limit=1)
        second = generate_world(5002, 1, 1)
        with self.assertRaises(ValidationError):
            self.repo.register_world(second, owner=owner, limit=1)
        with self.repo._connect() as db:
            self.assertIsNone(db.execute('SELECT 1 FROM worlds WHERE id=?', (second['world_id'],)).fetchone())
        for bad in ('http://example.com', 'https://user:secret@example.com', 'https://example.com/path'):
            with self.assertRaises(ValidationError):
                validate_origin(bad)
        self.assertEqual(validate_origin('http://127.0.0.1:8765', True), 'http://127.0.0.1:8765')

    def test_modified_parameters_precede_prediction_and_network_failure_keeps_launch(self):
        self.connection()
        state = self.propose(self.session())
        experiment = {'initial_position': {'x': 2, 'y': 3}, 'initial_velocity': {'x': 1, 'y': 0},
                      'duration': .4, 'observation_interval': .2}
        state = self.message(state, {'type': 'operator_decision', 'request_id': state['pending_request_id'],
            'action': 'modify', 'reason': 'Parametri modificati.', 'modified_experiment': experiment})
        state = self.message(state, {'type': 'execution_mode', 'request_id': state['pending_request_id'], 'mode': 'verification'})
        state = self.step(state)
        self.assertEqual(self.requests[-1].context['approved_experiment'], experiment)
        self.assertEqual(self.requests[-1].context['prediction_times'], [0, .2, .4])
        state = self.post(f"/sessions/{state['session_id']}/run", {'expected_version': state['version'], 'request_id': state['pending_request_id']})
        self.failure = True
        self.post(f"/sessions/{state['session_id']}/agent/step", {'expected_version': state['version']}, expected=503)
        current = self.alice.get('/v1/sessions/' + state['session_id']).json()
        self.assertEqual(current['executed_experiments'], 1)
        self.assertEqual(current['version'], state['version'])
        events = self.alice.get(f"/v1/sessions/{state['session_id']}/events").json()['events']
        self.assertEqual(sum(e['message']['type'] == 'execution_started' for e in events), 1)

    def test_disabled_registration_missing_vault_and_account_call_quota(self):
        class HostClient(OfflineLabClient):
            provider = 'openai'

            def complete(self, request):
                raise AssertionError('A public user must never consume the host model.')

        closed = TestClient(create_app(repository=self.repo, auth_mode='accounts', public_origin=self.origin,
                                      public_workspace=True, agent_client=HostClient()), base_url=self.origin)
        self.addCleanup(closed.close)
        result = closed.post('/v1/auth/register', headers={'Origin': self.origin}, json={
            'handle': 'closed', 'password': 'synthetic-password-123'})
        self.assertEqual(result.status_code, 403)
        result = closed.post('/v1/my/connections', headers={'Authorization': 'Bearer ' + self.admin['login_key']},
            json={'label': 'Test', 'provider': 'openai', 'model': 'test', 'transport': 'api', 'api_key': 'synthetic-api-key'})
        self.assertEqual(result.status_code, 503)
        state = closed.post('/v1/sessions', headers={'Authorization': 'Bearer ' + self.admin['login_key']},
            json={'world_id': self.world['world_id'], 'mode': 'watch_agent'}).json()
        self.assertFalse(state['agent']['real_model'])
        result = closed.post(f"/v1/sessions/{state['session_id']}/agent/step",
            headers={'Authorization': 'Bearer ' + self.admin['login_key']}, json={'expected_version': state['version']})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()['agent']['provider'], 'offline_baseline')
        self.connection()
        state = self.session()
        with self.repo._connect() as db:
            db.execute("UPDATE accounts SET quotas_json=json_set(quotas_json,'$.model_calls',0) WHERE id=?",
                       (self.alice_data['account']['account_id'],))
        self.post(f"/sessions/{state['session_id']}/agent/step", {'expected_version': state['version']}, expected=429)
        self.assertEqual(self.requests, [])
        with self.repo._connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM agent_calls WHERE session_id=?', (state['session_id'],)).fetchone()[0], 0)

    def test_personal_arena_cycle_ownership_and_operator_boundary(self):
        challenge = self.client().post('/v1/arena/challenges', headers={
            'Authorization': 'Bearer ' + self.admin['login_key'], 'X-Zone-Arena-Version': '1', 'Idempotency-Key': 'workspace-challenge'},
            json={'name': 'Challenge', 'world_id': self.world['world_id']})
        self.assertEqual(challenge.status_code, 201, challenge.text)
        self.assertEqual(self.alice.get('/v1/my/arena/leaderboards/' + challenge.json()['challenge_id']).status_code, 403)
        agent = self.post('/my/arena/agents', {'name': 'Baseline'}, expected=201)
        state = self.post('/my/arena/trials', {'agent_id': agent['agent_id'], 'challenge_id': challenge.json()['challenge_id']}, expected=201)
        path = '/my/arena/trials/' + state['session_id']
        self.assertEqual(self.bob.get('/v1' + path).status_code, 404)
        for _ in range(12):
            if state['status'] == 'scored':
                break
            phase = state['status']
            body = {'expected_version': state['version']}
            kind = 'step'
            if phase == 'awaiting_decision':
                kind = 'messages'; body['message'] = {'type': 'operator_decision', 'request_id': state['pending_request_id'], 'action': 'approve', 'reason': 'Decisione.'}
            elif phase == 'awaiting_mode':
                kind = 'messages'; body['message'] = {'type': 'execution_mode', 'request_id': state['pending_request_id'], 'mode': 'exploration'}
            elif phase == 'ready_to_run':
                kind = 'run'; body['request_id'] = state['pending_request_id']
            state = self.post(path + '/' + kind, body)
        self.assertEqual(state['status'], 'scored')
        self.assertEqual(state['executed_experiments'], 1)
        self.post(path + '/messages', {'expected_version': state['version'], 'message': {'type': 'conclusion'}}, expected=422)
        self.assertEqual(self.bob.get('/v1/my/arena').json()['trials'], [])


if __name__ == '__main__':
    unittest.main()
