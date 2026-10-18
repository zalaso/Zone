"""Account boundaries and durable resource budgets; all credentials/models synthetic."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

if importlib.util.find_spec('fastapi') is not None:
    from fastapi.testclient import TestClient
    from hidden_lab.agent_contract import openai_payload
    from hidden_lab.arena_client import ArenaClient
    from hidden_lab.backend import RateLimiter, create_app
    from hidden_lab.backend_store import ConflictError, SQLiteRepository
    from hidden_lab.identity_store import DEFAULT_QUOTAS, IDLE_TTL, SESSION_TTL, IdentityStore
    from hidden_lab.migrations import LEDGER_SQL, MIGRATIONS, check_database, checksum
    from hidden_lab.operations import backup_database, restore_database
    from hidden_lab.protocol import ValidationError
    from hidden_lab.provider_base import ProviderError
    from hidden_lab.web_agent import OfflineLabClient
    from hidden_lab.world_forge import generate_world


class SpyClient(OfflineLabClient if importlib.util.find_spec('fastapi') else object):
    def __init__(self):
        self.requests = []
        self.failure = False

    def complete(self, request):
        self.requests.append(request)
        if self.failure:
            raise ProviderError('server_error')
        return super().complete(request)


@unittest.skipUnless(importlib.util.find_spec('fastapi'), 'Installare extra backend')
class IdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.world = generate_world(432123, 1, 2)
        cls.origin = 'https://zone.test'

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / 'accounts.db'
        self.repo = SQLiteRepository(self.db, [self.world])
        self.now = 2000000000.0
        self.store = IdentityStore(self.repo, lambda: self.now)
        self.admin = self.store.create('admin', 'admin', bootstrap=True)
        self.alice = self.invite('alice')
        self.bob = self.invite('bob')
        self.operator = self.invite('operator', 'operator')
        self.model = SpyClient()
        self.client = self.restart()

    def invite(self, handle, role='member', **overrides):
        quotas = {**DEFAULT_QUOTAS, 'read': 10000, 'write': 1000, 'run': 1000, **overrides}
        return self.store.create(handle, role, quotas, actor=self.admin['account_id'])

    def restart(self, **options):
        app = create_app(repository=self.repo, auth_mode='accounts', public_origin=self.origin,
                         identity_clock=lambda: self.now, agent_client=self.model,
                         rate_limiter=RateLimiter(read=10000, write=10000, run=10000), **options)
        client = TestClient(app, base_url=self.origin)
        self.addCleanup(client.close)
        return client

    def headers(self, account=None):
        return {'Authorization': 'Bearer ' + (account or self.alice)['login_key']}

    def create(self, account=None, mode='scientist'):
        response = self.client.post('/v1/sessions', headers=self.headers(account),
                                    json={'world_id': self.world['world_id'], 'mode': mode})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def message(self, state, message, account=None):
        response = self.client.post('/v1/sessions/' + state['session_id'] + '/messages', headers=self.headers(account),
                                    json={'expected_version': state['version'], 'message': message})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def prepare(self, state, request_id='e1'):
        state = self.message(state, {'type': 'experiment_request', 'request_id': request_id, 'purpose': 'Osservare.',
            'experiment': {'initial_position': {'x': 0, 'y': 0}, 'initial_velocity': {'x': 1, 'y': 2},
                           'duration': .5, 'observation_interval': .25}})
        state = self.message(state, {'type': 'operator_decision', 'request_id': request_id, 'action': 'approve', 'reason': 'ok'})
        return self.message(state, {'type': 'execution_mode', 'request_id': request_id, 'mode': 'exploration'})

    def test_every_private_route_requires_account_and_legacy_tokens_do_not_bypass(self):
        state = self.create()
        for path in ('/worlds', '/modes', '/worlds/daily', '/my/sessions', '/admin/accounts',
                     '/integrity/manifests', '/sessions/' + state['session_id'],
                     '/sessions/' + state['session_id'] + '/events', '/arena/contract'):
            reply = self.client.get('/v1' + path, headers={'X-Zone-Token': state['agent_token']})
            self.assertEqual(reply.status_code, 401, path)
            self.assertEqual(reply.headers['cache-control'], 'no-store')
        self.assertEqual(self.client.get('/health/live').status_code, 200)
        self.assertEqual(self.client.get('/v1/auth/config').json(), {'mode': 'accounts'})
        self.assertEqual(self.client.get('/v1/worlds', headers={'Authorization': 'Bearer nope'}).status_code, 401)

    def test_ownership_covers_read_write_results_audit_and_matches(self):
        state = self.create()
        for suffix in ('', '/events', '/result', '/agent/audit'):
            self.assertEqual(self.client.get('/v1/sessions/' + state['session_id'] + suffix,
                headers=self.headers(self.bob)).status_code, 404)
        for suffix in ('/messages', '/run', '/stop', '/submission', '/agent/step'):
            self.assertEqual(self.client.post('/v1/sessions/' + state['session_id'] + suffix,
                headers=self.headers(self.bob), json={}).status_code, 404)
        paired = self.client.post('/v1/matches', headers=self.headers(), json={'world_id': self.world['world_id']})
        self.assertEqual(paired.status_code, 201, paired.text)
        match = paired.json()
        self.assertEqual(self.client.get('/v1/matches/' + match['match_id'], headers=self.headers(self.bob)).status_code, 404)
        self.assertEqual(self.client.get('/v1/matches/' + match['match_id'], headers=self.headers()).status_code, 200)
        for sid in (match['human_session_id'], match['agent_session_id']):
            self.assertEqual(self.client.get('/v1/sessions/' + sid, headers=self.headers(self.bob)).status_code, 404)
        mine = self.client.get('/v1/my/sessions', headers=self.headers()).json()['sessions']
        self.assertEqual(len(mine), 3)
        self.assertEqual(self.client.get('/v1/my/sessions', headers=self.headers(self.bob)).json()['sessions'], [])
        self.assertEqual(self.client.get('/v1/sessions/' + state['session_id'], headers=self.headers(self.operator)).status_code, 200)

    def test_roles_and_last_admin_cannot_be_escalated(self):
        for account in (self.alice, self.operator):
            for path in ('/v1/admin/accounts', '/v1/worlds/build', '/v1/sessions/' + self.create()['session_id'] + '/reveal'):
                self.assertEqual(self.client.post(path, headers=self.headers(account), json={}).status_code, 403)
        body = {'role': 'member', 'enabled': True, 'quotas': DEFAULT_QUOTAS}
        reply = self.client.post('/v1/admin/accounts/' + self.admin['account_id'], headers=self.headers(self.admin), json=body)
        self.assertEqual(reply.status_code, 422)
        self.assertEqual(self.client.post('/v1/admin/accounts', headers=self.headers(self.admin),
            json={'handle': 'new_member', 'role': 'member'}).status_code, 201)
        with self.assertRaises(ValidationError):
            self.store.create('another_admin', 'admin', bootstrap=True)

    def test_cookie_login_csrf_logout_and_no_secret_at_rest_or_in_audit(self):
        browser = self.restart()
        reply = browser.post('/v1/auth/login', headers={'Origin': self.origin}, json={'login_key': self.alice['login_key']})
        self.assertEqual(reply.status_code, 200, reply.text)
        cookie = reply.headers['set-cookie']
        for flag in ('HttpOnly', 'Secure', 'SameSite=strict', 'Path=/'):
            self.assertIn(flag, cookie)
        csrf = reply.json()['csrf']
        self.assertEqual(browser.get('/v1/auth/me').json()['account']['handle'], 'alice')
        for headers in ({}, {'Origin': 'https://evil.test', 'X-Zone-CSRF': csrf}, {'Origin': self.origin}):
            self.assertEqual(browser.post('/v1/sessions', headers=headers, json={'world_id': self.world['world_id']}).status_code, 403)
        headers = {'Origin': self.origin, 'X-Zone-CSRF': csrf}
        self.assertEqual(browser.post('/v1/sessions', headers=headers, json={'world_id': self.world['world_id']}).status_code, 201)
        self.assertEqual(browser.get('/v1/auth/me', headers=self.headers()).status_code, 401)
        self.assertEqual(browser.post('/v1/auth/logout', headers=headers, json={}).status_code, 200)
        self.assertEqual(browser.get('/v1/auth/me').status_code, 401)
        with self.repo._connect() as db:
            dump = '\n'.join(db.iterdump())
        for secret in (self.admin['login_key'], self.alice['login_key'], csrf):
            self.assertNotIn(secret, dump)
        audit = self.client.get('/v1/admin/audit', headers=self.headers(self.admin)).text
        self.assertNotIn(self.alice['login_key'], audit)

    def test_rotation_disable_expiry_and_local_recovery_revoke_sessions(self):
        browser = self.restart()
        browser.post('/v1/auth/login', headers={'Origin': self.origin}, json={'login_key': self.alice['login_key']})
        rotated = self.store.rotate(self.admin['account_id'], self.alice['account_id'], 60)
        self.assertEqual(browser.get('/v1/auth/me').status_code, 401)
        self.assertEqual(self.client.get('/v1/auth/me', headers=self.headers()).status_code, 401)
        self.assertEqual(self.client.get('/v1/auth/me', headers=self.headers(rotated)).status_code, 200)
        self.now += 60
        self.assertEqual(self.client.get('/v1/auth/me', headers=self.headers(rotated)).status_code, 401)
        body = {'role': 'member', 'enabled': False, 'quotas': DEFAULT_QUOTAS}
        self.store.update(self.admin['account_id'], self.bob['account_id'], body)
        self.assertEqual(self.client.get('/v1/auth/me', headers=self.headers(self.bob)).status_code, 401)
        replacement = self.store.recover_admin('admin')
        self.assertEqual(self.client.get('/v1/auth/me', headers=self.headers(self.admin)).status_code, 401)
        self.assertEqual(self.client.get('/v1/auth/me', headers=self.headers(replacement)).status_code, 200)
        with self.assertRaises(ValidationError):
            self.store.recover_admin('alice')

    def test_cookie_idle_absolute_expiry_and_login_rate_are_persistent(self):
        browser = self.restart()
        browser.post('/v1/auth/login', headers={'Origin': self.origin}, json={'login_key': self.alice['login_key']})
        self.now += IDLE_TTL
        self.assertEqual(browser.get('/v1/auth/me').status_code, 401)
        browser.cookies.clear()
        browser.post('/v1/auth/login', headers={'Origin': self.origin}, json={'login_key': self.alice['login_key']})
        self.now += SESSION_TTL
        with self.repo._connect() as db:
            db.execute('UPDATE account_sessions SET last_seen=?', (self.now,))
        self.assertEqual(browser.get('/v1/auth/me').status_code, 401)
        for _ in range(10):
            self.assertEqual(self.client.post('/v1/auth/login', headers={'Origin': self.origin}, json={'login_key': 'x' * 40}).status_code, 401)
        restarted = self.restart()
        self.assertEqual(restarted.post('/v1/auth/login', headers={'Origin': self.origin}, json={'login_key': self.bob['login_key']}).status_code, 429)

    def test_logout_remains_available_with_zero_write_quota(self):
        account = self.invite('read_only', write=0)
        browser = self.restart()
        login = browser.post('/v1/auth/login', headers={'Origin': self.origin}, json={'login_key': account['login_key']})
        csrf = login.json()['csrf']
        headers = {'Origin': self.origin, 'X-Zone-CSRF': csrf}
        self.assertEqual(browser.post('/v1/sessions', headers=headers, json={'world_id': self.world['world_id']}).status_code, 429)
        self.assertEqual(browser.post('/v1/auth/logout', headers=headers, json={}).status_code, 200)
        self.assertEqual(browser.get('/v1/auth/me').status_code, 401)

    def test_origin_host_and_configuration_fail_closed(self):
        self.assertEqual(self.client.get('/v1/worlds', headers={**self.headers(), 'Origin': 'https://evil.test'}).status_code, 403)
        self.assertEqual(self.client.get('/v1/worlds', headers={**self.headers(), 'Host': 'evil.test'}).status_code, 400)
        self.assertEqual(self.client.post('/v1/auth/login', json={'login_key': self.alice['login_key']}).status_code, 403)
        for origin, secure in (('http://public.test', False), ('https://zone.test/path', True), ('https://zone.test', False)):
            with self.assertRaises(ValueError):
                create_app(repository=self.repo, auth_mode='accounts', public_origin=origin, secure_cookies=secure)
        with self.assertRaises(ValueError):
            create_app(repository=self.repo, operator_token='legacy' * 8)
        with self.repo._connect() as db:
            db.execute('DROP TABLE account_rates')
        self.assertEqual(self.client.get('/health/ready').status_code, 503)

    def test_session_quota_atomic_parallel_and_match_creation_rolls_back(self):
        small = self.invite('small', sessions=1)
        def create_one(_):
            return self.client.post('/v1/sessions', headers=self.headers(small), json={'world_id': self.world['world_id']}).status_code
        with ThreadPoolExecutor(2) as pool:
            self.assertEqual(sorted(pool.map(create_one, range(2))), [201, 429])
        pair_owner = self.invite('pair_owner', sessions=1)
        reply = self.client.post('/v1/matches', headers=self.headers(pair_owner), json={'world_id': self.world['world_id']})
        self.assertEqual(reply.status_code, 429, reply.text)
        account = self.store.authenticate(pair_owner['login_key'])
        self.assertEqual(account['usage']['sessions'], 0)
        self.assertEqual(self.client.get('/v1/my/sessions', headers=self.headers(pair_owner)).json()['sessions'], [])

    def test_experiment_quota_reservation_and_no_duplicate_run(self):
        self.store.update(self.admin['account_id'], self.alice['account_id'],
            {'role': 'member', 'enabled': True, 'quotas': {**self.alice['quotas'], 'experiments': 1}})
        state = self.prepare(self.create())
        body = {'expected_version': state['version'], 'request_id': 'e1'}
        path = '/v1/sessions/' + state['session_id'] + '/run'
        first = self.client.post(path, headers=self.headers(self.operator), json=body)
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(self.client.post(path, headers=self.headers(), json=body).status_code, 409)
        state = self.prepare(first.json(), 'e2')
        with self.repo._connect() as db:
            before = db.execute('SELECT COUNT(*) FROM events').fetchone()[0]
        denied = self.client.post(path, headers=self.headers(), json={'expected_version': state['version'], 'request_id': 'e2'})
        self.assertEqual(denied.status_code, 429, denied.text)
        with self.repo._connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM events').fetchone()[0], before)
        self.assertEqual(self.store.authenticate(self.alice['login_key'])['usage']['experiments'], 1)
        self.assertEqual(self.store.authenticate(self.operator['login_key'])['usage']['experiments'], 0)

    def test_model_quota_charged_before_network_error_without_retry(self):
        self.model.failure = True
        self.store.update(self.admin['account_id'], self.alice['account_id'],
            {'role': 'member', 'enabled': True, 'quotas': {**self.alice['quotas'], 'model_calls': 1}})
        state = self.create(mode='watch_agent')
        path = '/v1/sessions/' + state['session_id'] + '/agent/step'
        body = {'expected_version': state['version']}
        self.assertEqual(self.client.post(path, headers=self.headers(), json=body).status_code, 503)
        self.assertEqual(self.client.post(path, headers=self.headers(), json=body).status_code, 429)
        self.assertEqual(len(self.model.requests), 1)
        self.assertEqual(self.store.authenticate(self.alice['login_key'])['usage']['experiments'], 0)
        self.assertEqual(len(self.repo.read_session(state['session_id'])['calls']), 1)

    def test_full_offline_managed_cycle_and_provider_payload_projection(self):
        state = self.create(mode='watch_agent')
        sid = state['session_id']
        for _ in range(35):
            phase = state['status']
            if phase == 'scored':
                break
            if phase in ('discovering', 'awaiting_submission', 'awaiting_prediction'):
                reply = self.client.post('/v1/sessions/' + sid + '/agent/step', headers=self.headers(),
                                          json={'expected_version': state['version']})
                self.assertEqual(reply.status_code, 200, reply.text)
                state = reply.json()
            elif phase == 'awaiting_decision':
                state = self.message(state, {'type': 'operator_decision', 'request_id': state['pending_request_id'], 'action': 'approve', 'reason': 'Operatore simulato.'})
            elif phase == 'awaiting_mode':
                state = self.message(state, {'type': 'execution_mode', 'request_id': state['pending_request_id'], 'mode': 'exploration'})
            elif phase == 'ready_to_run':
                reply = self.client.post('/v1/sessions/' + sid + '/run', headers=self.headers(),
                    json={'expected_version': state['version'], 'request_id': state['pending_request_id']})
                self.assertEqual(reply.status_code, 200, reply.text)
                state = reply.json()
            else:
                self.fail('Stato inatteso: ' + phase)
        self.assertEqual(state['status'], 'scored')
        self.assertEqual(state['executed_experiments'], 2)
        usage = self.store.authenticate(self.alice['login_key'])['usage']
        self.assertEqual(usage, {'sessions': 1, 'experiments': 2, 'model_calls': len(self.model.requests)})
        for request in self.model.requests:
            payload = json.dumps(openai_payload(request))
            for forbidden in ('key_hash', 'quotas', 'session_owners', 'account_id', 'probe_truth', 'secret_grid',
                              'generator_version', str(self.world['config']['seed']),
                              self.alice['login_key'], self.alice['account_id'], self.admin['login_key']):
                self.assertNotIn(forbidden, payload)
        self.assertEqual(self.client.get('/v1/sessions/' + sid + '/result', headers=self.headers(self.bob)).status_code, 404)

    def test_rate_limits_survive_restart_and_admin_quota_change(self):
        limited = self.invite('limited', read=1)
        self.assertEqual(self.client.get('/v1/worlds', headers=self.headers(limited)).status_code, 200)
        self.assertEqual(self.restart().get('/v1/worlds', headers=self.headers(limited)).status_code, 429)
        self.store.update(self.admin['account_id'], limited['account_id'],
            {'role': 'member', 'enabled': True, 'quotas': {**limited['quotas'], 'read': 2}})
        self.assertEqual(self.client.get('/v1/worlds', headers=self.headers(limited)).status_code, 200)
        self.assertEqual(self.client.get('/v1/worlds', headers=self.headers(limited)).status_code, 429)

    def test_historical_work_charges_acting_staff_without_inventing_ownership(self):
        from hidden_lab.identity_store import account_scope, charge_session
        with self.repo._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            with account_scope(self.operator):
                charge_session(db, 'historical-unowned', 'model_calls')
        self.assertEqual(self.store.authenticate(self.operator['login_key'])['usage']['model_calls'], 1)

    def test_arena_requires_bound_account_and_agent_credential(self):
        staff = ArenaClient(self.client, '', account_key=self.admin['login_key'])
        ch = staff.write('challenges', {'name': 'Test', 'world_id': self.world['world_id']}, 'new-challenge')
        issued = staff.write('agents', {'name': 'Baseline', 'model': 'offline-test', 'kind': 'offline_baseline'}, 'new-agent')
        agent = ArenaClient(self.client, issued['token'], account_key=self.alice['login_key'])
        denied = self.client.post('/v1/arena/sessions', headers={**agent.headers(), 'Idempotency-Key': 'before-bind'}, json={'challenge_id': ch['challenge_id']})
        self.assertEqual(denied.status_code, 401, denied.text)
        self.store.bind_agent(self.admin['account_id'], self.alice['account_id'], issued['agent_id'])
        state = agent.write('sessions', {'challenge_id': ch['challenge_id']}, 'new-trial')
        sid = state['session_id']
        self.assertEqual(self.store.authenticate(self.alice['login_key'])['usage']['sessions'], 1)
        other = ArenaClient(self.client, issued['token'], account_key=self.bob['login_key'])
        self.assertEqual(self.client.get('/v1/arena/sessions/' + sid, headers=other.headers()).status_code, 401)
        self.assertEqual(self.client.get('/v1/arena/sessions/' + sid, headers={'X-Zone-Token': issued['token'], 'X-Zone-Arena-Version': '1'}).status_code, 401)
        denied = self.client.post('/v1/arena/challenges', headers={**agent.headers(), 'Idempotency-Key': 'no-staff'}, json={})
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(self.client.get('/v1/sessions/' + sid, headers=self.headers()).status_code, 404)
        self.assertEqual(staff.read('sessions/' + sid)['session_id'], sid)
        with self.assertRaises(ConflictError):
            self.store.bind_agent(self.admin['account_id'], self.bob['account_id'], issued['agent_id'])

    def test_backup_restore_preserves_hashes_owners_revocations_and_rates(self):
        state = self.create()
        self.store.update(self.admin['account_id'], self.bob['account_id'],
            {'role': 'member', 'enabled': False, 'quotas': self.bob['quotas']})
        self.client.get('/v1/worlds', headers=self.headers())
        backup, restored = self.db.with_name('backup.db'), self.db.with_name('restored.db')
        backup_database(self.db, backup)
        restore_database(backup, restored)
        tables = ('accounts', 'session_owners', 'account_sessions', 'account_rates', 'account_audit')
        with self.repo._connect() as old, SQLiteRepository(restored)._connect() as new:
            for table in tables:
                self.assertEqual(old.execute('SELECT * FROM ' + table).fetchall(), new.execute('SELECT * FROM ' + table).fetchall())
        store = IdentityStore(SQLiteRepository(restored), lambda: self.now)
        self.assertEqual(store.authenticate(self.alice['login_key'])['usage']['sessions'], 1)
        from fastapi import HTTPException
        with self.assertRaises(HTTPException):
            store.authenticate(self.bob['login_key'])
        store.owns_session(self.alice, state['session_id'])

    def test_version_two_migration_preserves_legacy_session_then_explicit_adoption(self):
        old_path = self.db.with_name('v2.db')
        with closing(sqlite3.connect(old_path)) as db:
            db.execute(LEDGER_SQL)
            for v, name, sql in MIGRATIONS[:2]:
                db.executescript(sql)
                db.execute('INSERT INTO schema_migrations(version,name,checksum) VALUES(?,?,?)', (v, name, checksum(sql)))
                db.execute(f'PRAGMA user_version={v}')
            db.commit()
        self.assertEqual(check_database(old_path)['pending'], [v for v, _, _ in MIGRATIONS if v > 2])
        repo = SQLiteRepository(old_path, [self.world])
        local = TestClient(create_app(repository=repo, operator_token='legacy-token' * 5))
        self.addCleanup(local.close)
        state = local.post('/v1/sessions', headers={'X-Zone-Token': 'legacy-token' * 5}, json={'world_id': self.world['world_id']}).json()
        old_events = repo.read_session(state['session_id'])['events']
        store = IdentityStore(repo, lambda: self.now)
        admin = store.create('admin', 'admin', bootstrap=True)
        member = store.create('member', actor=admin['account_id'])
        self.assertEqual(local.get('/v1/sessions/' + state['session_id']).status_code, 503)
        client = TestClient(create_app(repository=repo, auth_mode='accounts', public_origin=self.origin, identity_clock=lambda: self.now), base_url=self.origin)
        self.addCleanup(client.close)
        self.assertEqual(client.get('/v1/sessions/' + state['session_id'], headers=self.headers(member)).status_code, 404)
        assigned = client.post('/v1/admin/sessions/' + state['session_id'] + '/assign', headers=self.headers(admin), json={'account_id': member['account_id']})
        self.assertEqual(assigned.status_code, 200, assigned.text)
        self.assertEqual(client.get('/v1/sessions/' + state['session_id'], headers=self.headers(member)).status_code, 200)
        self.assertEqual(repo.read_session(state['session_id'])['events'], old_events)
        damaged = self.db.with_name('incomplete-v2.db')
        with closing(sqlite3.connect(damaged)) as db:
            db.execute(LEDGER_SQL)
            for v, name, sql in MIGRATIONS[:2]:
                db.executescript(sql)
                db.execute('INSERT INTO schema_migrations(version,name,checksum) VALUES(?,?,?)', (v, name, checksum(sql)))
                db.execute(f'PRAGMA user_version={v}')
            db.execute('DROP TABLE daily_worlds')
            db.commit()
        with self.assertRaises(ValidationError):
            check_database(damaged)


if __name__ == '__main__':
    unittest.main()
