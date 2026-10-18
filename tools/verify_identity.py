"""Repeatable in-process multiuser pilot. No network, real model or user credentials."""

import argparse
import json
from pathlib import Path

from fastapi.testclient import TestClient

from hidden_lab.backend import RateLimiter, create_app
from hidden_lab.backend_store import SQLiteRepository
from hidden_lab.identity_store import DEFAULT_QUOTAS, IdentityStore
from hidden_lab.migrations import EXPECTED_TABLES, SCHEMA_VERSION
from hidden_lab.operations import backup_database, restore_database
from hidden_lab.world_forge import generate_world


def verify(out):
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False, mode=0o700)
    repo = SQLiteRepository(out / 'identity.db', [generate_world(130013, 1, 2)])
    identity = IdentityStore(repo)
    quotas = {**DEFAULT_QUOTAS, 'read': 1000, 'write': 1000}
    admin = identity.create('admin', 'admin', quotas, bootstrap=True)
    member = identity.create('alice', quotas=quotas, actor=admin['account_id'])
    other = identity.create('bob', actor=admin['account_id'])
    operator = identity.create('operator', 'operator', quotas, actor=admin['account_id'])
    def headers(account):
        return {'Authorization': 'Bearer ' + account['login_key']}
    app = create_app(repository=repo, auth_mode='accounts', public_origin='https://zone.test',
                     rate_limiter=RateLimiter(read=10000, write=10000, run=10000))
    with TestClient(app, base_url='https://zone.test') as client:
        world_id = client.get('/v1/worlds', headers=headers(member)).json()['worlds'][0]['world_id']
        reply = client.post('/v1/sessions', headers=headers(member), json={'world_id': world_id, 'mode': 'watch_agent'})
        assert reply.status_code == 201, reply.text
        state, steps = reply.json(), 0
        sid = state['session_id']
        while state['status'] != 'scored':
            steps += 1
            assert steps <= 35, 'Offline demo exceeded turn bound'
            body = {'expected_version': state['version']}
            phase = state['status']
            account = member
            if phase in ('discovering', 'awaiting_prediction', 'awaiting_submission'):
                action = 'agent/step'
            elif phase == 'awaiting_decision':
                account, action = operator, 'messages'
                body['message'] = {'type': 'operator_decision', 'request_id': state['pending_request_id'],
                                   'action': 'approve', 'reason': 'Operatore simulato offline.'}
            elif phase == 'awaiting_mode':
                account, action = operator, 'messages'
                body['message'] = {'type': 'execution_mode', 'request_id': state['pending_request_id'], 'mode': 'exploration'}
            elif phase == 'ready_to_run':
                account, action = operator, 'run'
                body['request_id'] = state['pending_request_id']
            else:
                raise AssertionError('Unexpected offline phase: ' + phase)
            reply = client.post(f'/v1/sessions/{sid}/{action}', headers=headers(account), json=body)
            assert reply.status_code == 200, reply.text
            state = reply.json()
        assert client.get('/v1/sessions/' + sid).status_code == 401
        assert client.get('/v1/sessions/' + sid, headers=headers(other)).status_code == 404
        assert client.get('/v1/admin/accounts', headers=headers(member)).status_code == 403
        old_key = other['login_key']
        other = identity.rotate(admin['account_id'], other['account_id'], 3600)
        assert client.get('/v1/auth/me', headers={'Authorization': 'Bearer ' + old_key}).status_code == 401
        identity.update(admin['account_id'], other['account_id'], {'role': 'member', 'enabled': False, 'quotas': other['quotas']})
        assert client.get('/v1/auth/me', headers=headers(other)).status_code == 401
    backup_database(repo.path, out / 'backup.db')
    restore_database(out / 'backup.db', out / 'restored.db')
    restored = SQLiteRepository(out / 'restored.db')
    with repo._connect() as old, restored._connect() as new:
        for table in EXPECTED_TABLES:
            assert old.execute('SELECT * FROM "' + table + '"').fetchall() == new.execute('SELECT * FROM "' + table + '"').fetchall(), table
    usage = IdentityStore(restored).authenticate(member['login_key'])['usage']
    report = {'notice': 'Baseline affine e operatore simulati; seed noto; zero chiamate API reali.',
              'status': state['status'], 'accounts': 4, 'experiments': state['executed_experiments'],
              'account_usage': usage, 'isolation_verified': True, 'rotation_revocation_verified': True,
              'restore_all_tables_equal': True, 'schema_version': SCHEMA_VERSION}
    (out / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True, help='New private directory; never overwrite')
    print(json.dumps(verify(parser.parse_args().out), ensure_ascii=False, indent=2))
