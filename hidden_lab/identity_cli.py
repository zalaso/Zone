"""Local, trusted administrative bootstrap; never an HTTP registration endpoint."""

from pathlib import Path

from .protocol import ValidationError


def add_parser(commands):
    parser = commands.add_parser('identity', help='Account invitati: bootstrap e recupero locale')
    sub = parser.add_subparsers(dest='identity_command', required=True)
    for name in ('init', 'recover-admin'):
        child = sub.add_parser(name, help='Mostra una nuova chiave una sola volta nel terminale fidato')
        child.add_argument('--db', type=Path, required=True)
        child.add_argument('--handle', required=True)
        child.add_argument('--ttl-seconds', type=int, default=2592000)


def run_command(args):
    from .backend_store import SQLiteRepository
    from .identity_store import IdentityStore
    if args.identity_command == 'recover-admin' and not args.db.is_file():
        raise ValidationError('Il recupero richiede un database esistente.')
    store = IdentityStore(SQLiteRepository(args.db))
    if args.identity_command == 'init':
        account = store.create(args.handle, 'admin', ttl=args.ttl_seconds, bootstrap=True)
    else:
        account = store.recover_admin(args.handle, args.ttl_seconds)
    print('Account:', account['handle'], '| ID:', account['account_id'])
    print('Chiave di accesso (mostrata solo ora; conservala in modo sicuro):')
    print(account['login_key'])
    print('Il database è ora riservato alla modalità --auth-mode accounts.')
    return 0
