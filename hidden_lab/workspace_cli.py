"""Supported standalone workspace startup. No provider requests at startup."""
import json
import os
from pathlib import Path
import secrets
from urllib.parse import urlsplit


def add_parser(commands):
    parser = commands.add_parser('workspace', help='Avvia Zone completo, con account e mondo iniziale offline')
    parser.add_argument('--data', type=Path, help='Directory privata persistente (default ~/.zone)')
    parser.add_argument('--port', type=int, default=8767)
    parser.add_argument('--host', choices=('127.0.0.1', '0.0.0.0'), default='127.0.0.1')
    parser.add_argument('--container-local', action='store_true')
    parser.add_argument('--origin', help='Origine esatta del browser; HTTPS per utenti esterni')
    parser.add_argument('--web-dir', type=Path, help='Bundle compilato alternativo')
    parser.add_argument('--open-registration', action='store_true', help='Abilita registrazione anche su origine HTTPS esterna')
    parser.add_argument('--enable-personal-api', action='store_true', help='Abilita chiavi API personali cifrate; nessuna inferenza automatica')
    parser.add_argument('--max-accounts', type=int, default=1000)


def web_directory(explicit=None):
    from .protocol import ValidationError
    candidates = [Path(explicit)] if explicit else [Path(__file__).parent / 'web', Path(__file__).resolve().parents[1] / 'frontend' / 'dist']
    for path in candidates:
        if (path / 'index.html').is_file() and not path.is_symlink():
            return path.resolve()
    raise ValidationError('Interfaccia non compilata. Installa la wheel della release oppure esegui pnpm install e pnpm build nella cartella frontend.')


def private_file(path, value):
    # Fail closed on collisions: never follow a symlink or overwrite a credential.
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
        stream.write(value + '\n')
        stream.flush()
        os.fsync(stream.fileno())


def connection_key(data, enabled):
    if not enabled:
        return None
    if os.environ.get('ZONE_CONNECTION_KEY'):
        return os.environ['ZONE_CONNECTION_KEY']
    path = data / 'connection.key'
    if path.is_symlink():
        raise ValueError('Archivio della chiave non valido.')
    if not path.exists():
        private_file(path, secrets.token_urlsafe(32))
    return path.read_text(encoding='utf-8').strip()


def prepare(data, *, origin, static_dir, registration=True, personal_api=False, max_accounts=1000):
    from .backend import create_app
    from .backend_store import SQLiteRepository
    from .identity_store import IdentityStore
    from .world_forge import generate_world
    from .arena import rules_for
    data = Path(data).resolve()
    data.mkdir(parents=True, exist_ok=True, mode=0o700)
    repo = SQLiteRepository(data / 'workspace.db')
    with repo._connect() as db:
        has_accounts = db.execute('SELECT 1 FROM accounts').fetchone()
        has_sessions = db.execute('SELECT 1 FROM sessions').fetchone()
        has_worlds = db.execute('SELECT 1 FROM worlds').fetchone()
    if has_sessions and not has_accounts:
        raise ValueError('Database personale esistente: usa identity init e la procedura di migrazione documentata.')
    if not has_accounts:
        # The trusted host owner gets the administrative invite, never the first registrant.
        key_path = data / 'admin-key.txt'
        if key_path.exists() or key_path.is_symlink():
            raise ValueError('Chiave amministratore già presente senza account; conserva i file e usa identity recover-admin.')
        admin = IdentityStore(repo).create('zone_admin', 'admin', bootstrap=True)
        private_file(key_path, admin['login_key'])
    if not has_worlds:
        record = generate_world(secrets.randbits(128), 1, 3)
        repo.register_world(record)
        # Initial diagnostic challenge on the newly generated, unrevealed world.
        # No HTTP self-call, model, private prompt or test client involved.
        with repo._connect() as db:
            db.execute('INSERT INTO arena_challenges VALUES(?,?,?,?,0)',
                       (secrets.token_hex(16), record['world_id'], 'First challenge · local diagnostic',
                        json.dumps(rules_for(record, 30, 3))))
    return create_app(repository=repo, auth_mode='accounts', public_origin=origin,
        secure_cookies=urlsplit(origin).scheme == 'https', public_workspace=True,
        open_registration=registration, max_accounts=max_accounts,
        connection_key=connection_key(data, personal_api), static_dir=static_dir)


def run_command(args):
    if args.data is None:
        args.data = Path.home() / '.zone'
    if not 1024 <= args.port <= 65535 or not 1 <= args.max_accounts <= 100000:
        raise ValueError('Porta o capacità account non valida.')
    if args.host != '127.0.0.1' and not args.container_local:
        raise ValueError('Bind non loopback: serve --container-local dietro una pubblicazione locale o proxy fidato.')
    origin = args.origin or f'http://127.0.0.1:{args.port}'
    parsed = urlsplit(origin)
    if (parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password
            or parsed.path or parsed.query or parsed.fragment):
        raise ValueError('Origine esatta senza percorso, slash finale o credenziali richiesta.')
    _ = parsed.port
    local = parsed.hostname in ('127.0.0.1', 'localhost', '::1')
    if parsed.scheme != 'https' and not local:
        raise ValueError('Le origini esterne richiedono HTTPS.')
    static_dir = web_directory(args.web_dir)  # Validate before creating any database or key.
    app = prepare(args.data, origin=origin, static_dir=static_dir,
                  registration=local or args.open_registration, personal_api=args.enable_personal_api,
                  max_accounts=args.max_accounts)
    from .runtime_ops import configure_logging
    configure_logging()
    print(f'Zone: {origin}')
    print('Private data:', Path(args.data).resolve())
    print('Owner access: choose I have an invite; the key is in admin-key.txt. Keep it private.')
    print('No automatic inference. Connect your own AI or start without a model.')
    import uvicorn
    uvicorn.run(app, host=args.host, port=args.port, access_log=False, proxy_headers=False)
    return 0
