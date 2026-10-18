"""Loopback preview with self registration, an offline world and one Arena challenge.

Does not read provider credentials or configure a shared model. Personal AI calls
require the user's separate connection and explicit step, as in the real workspace.
"""

import argparse
import os
from pathlib import Path
import secrets

from fastapi.testclient import TestClient

from hidden_lab.backend import create_app
from hidden_lab.backend_store import SQLiteRepository
from hidden_lab.identity_store import IdentityStore
from hidden_lab.world_forge import generate_world


def prepare(out, port, *, connection_key=None):
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=True, mode=0o700)
    repo = SQLiteRepository(out / 'workspace.db')
    with repo._connect() as db:
        count = db.execute('SELECT COUNT(*) FROM worlds').fetchone()[0]
    if not count:
        repo.register_world(generate_world(secrets.randbits(128), 1, 2))
    with repo._connect() as db:
        any_accounts = db.execute('SELECT 1 FROM accounts').fetchone()
    admin = None
    if not any_accounts:
        admin = IdentityStore(repo).create('preview_admin', 'admin', bootstrap=True)
    app = create_app(repository=repo, auth_mode='accounts', public_origin=f'http://127.0.0.1:{port}',
        secure_cookies=False, public_workspace=True, open_registration=True,
        connection_key=connection_key,
        static_dir=Path(__file__).resolve().parents[1] / 'frontend' / 'dist')
    with repo._connect() as db:
        existing = db.execute('SELECT 1 FROM arena_challenges').fetchone()
    if not existing and admin:
        with TestClient(app, base_url=f'http://127.0.0.1:{port}') as http:
            result = http.post('/v1/arena/challenges', headers={'Authorization': 'Bearer ' + admin['login_key'],
                'X-Zone-Arena-Version': '1', 'Idempotency-Key': 'preview-initial-challenge'},
                json={'name': 'Prima challenge · offline', 'world_id': repo.list_worlds()[0]['world_id']})
            if result.status_code != 201:
                raise RuntimeError('Preparazione challenge non riuscita.')
        # This bootstrap identity is not an interactive preview user.
        with repo._connect() as db:
            db.execute('UPDATE accounts SET enabled=0 WHERE id=?', (admin['account_id'],))
    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--port', type=int, default=8767)
    parser.add_argument('--enable-personal-api', action='store_true', help='Legge ZONE_CONNECTION_KEY per abilitare API personali, senza inferenze automatiche')
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error('Porta non valida.')
    import uvicorn
    connection_key = os.environ.get('ZONE_CONNECTION_KEY') if args.enable_personal_api else None
    if args.enable_personal_api and not connection_key:
        parser.error('Imposta ZONE_CONNECTION_KEY in questo terminale, senza inserirla nel codice.')
    app = prepare(args.out, args.port, connection_key=connection_key)
    print(f'Anteprima: http://127.0.0.1:{args.port} · crea un account dal browser.')
    print('API personali abilitate.' if connection_key else 'API sul server disabilitate.')
    print('Connettori personali opzionali. Nessuna inferenza automatica.')
    uvicorn.run(app, host='127.0.0.1', port=args.port, access_log=False, proxy_headers=False)


if __name__ == '__main__':
    main()
