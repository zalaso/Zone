"""Explicit local account operations. Login/models never generate model responses."""
import json
from pathlib import Path
import secrets
import sys

from .chatgpt_auth import CredentialStore, DIRECT_SCOPE, active_account, auth_http, login, logout
from .protocol import ValidationError


def add_parser(commands):
    root = commands.add_parser('chatgpt', help='Accesso ufficiale al piano ChatGPT, senza API key')
    sub = root.add_subparsers(dest='chatgpt_command', required=True)
    start = sub.add_parser('login', help='Continue with ChatGPT nel browser; nessuna inferenza')
    start.add_argument('--new-account', action='store_true', help='Aggiungi un account/workspace separato')
    sub.add_parser('status', help='Account salvati e permesso del piano; offline, senza token')
    select = sub.add_parser('select', help='Scegli una registrazione già verificata')
    select.add_argument('index', type=int, help='Numero mostrato da status, a partire da 1')
    sub.add_parser('models', help='Catalogo attuale dell’account: rete, zero inferenze')
    sub.add_parser('logout', help='Revoca la sessione e cancella localmente i token dell’account attivo')
    transfer = sub.add_parser('transfer-vps', help='Sposta la registrazione personale al VPS via SSH; zero inferenze')
    transfer.add_argument('--confirm-personal-vps-transfer', action='store_true',
                          help='Consenso esplicito a spostare i token; il VPS gestirà i rinnovi')
    transfer.add_argument('--ssh-host', help='Destinazione SSH del tuo server; mai implicita')
    transfer.add_argument('--container', help='Nome del tuo container Zone; mai implicito')
    sub.add_parser('vm-import', help='Ricevitore privato via SSH; nessun endpoint web')
    pilot = sub.add_parser('pilot', help='Un mondo Forge nuovo, operatore umano, piano ChatGPT')
    pilot.add_argument('--model', help='Slug esplicito del catalogo; altrimenti scelta numerata')


def run_command(args):
    store = CredentialStore()
    command = args.chatgpt_command
    if command == 'transfer-vps':
        if not args.confirm_personal_vps_transfer:
            raise ValidationError('Occorre --confirm-personal-vps-transfer: sposta i token OAuth personali al VPS.')
        from .chatgpt_vm import transfer_to_vps
        print(json.dumps(transfer_to_vps(store, ssh_host=args.ssh_host, container=args.container)))
        return 0
    if command == 'vm-import':
        from .chatgpt_vm import receive_vm_registration
        print(json.dumps(receive_vm_registration()))
        return 0
    if command == 'login':
        if not sys.stdin.isatty():
            raise ValidationError('Esegui chatgpt login da un terminale interattivo.')
        return 0 if login(store, new_account=args.new_account) else 2
    if command == 'pilot':
        return run_pilot(args)
    if command == 'models':
        from .chatgpt_client import ChatGPTClient
        from .provider_base import AgentSettings, ProviderError
        # Model is irrelevant to GET /models; no model is selected or generated here.
        client = ChatGPTClient(AgentSettings('catalog-only', timeout=30))
        try:
            for model in client.models():
                print(json.dumps(model, ensure_ascii=False))
            print('Catalogo dell’account; l’accesso al modello scelto richiede ancora una richiesta riuscita.')
            return 0
        except ProviderError as exc:
            print(f'Catalogo non disponibile ({exc.code}, HTTP {exc.http_status}); nessuna inferenza.')
            return 2
        finally:
            client.close()
    with store.lock():
        state = store.load()
        if command == 'status':
            if not state['accounts']:
                print('Nessun account Zone collegato. Esegui chatgpt login.')
            for index, account in enumerate(state['accounts'], 1):
                print(json.dumps({'index': index, 'label': account['label'], 'email': account.get('email'),
                                  'active': account['client_id'] == state['active'],
                                  'plan_permission': DIRECT_SCOPE in account.get('scopes', [])}, ensure_ascii=False))
            return 0
        if command == 'select':
            if not 1 <= args.index <= len(state['accounts']):
                raise ValidationError('Numero account fuori dai limiti; consulta chatgpt status.')
            state['active'] = state['accounts'][args.index - 1]['client_id']
            store.save(state)
            print('Account selezionato; nessuna inferenza.')
            return 0
        if command == 'logout':
            active_account(state)
            with auth_http() as http:
                confirmed = logout(store, http)
            print('Token locali rimossi; registrazione conservata per un nuovo login.')
            if not confirmed:
                print('Revoca remota non confermata. Disconnetti Zone nelle impostazioni ChatGPT → Apps/Usage.')
            return 0 if confirmed else 2
    raise ValidationError('Comando ChatGPT sconosciuto.')


def run_pilot(args):
    """No billing fallback, no automatic operator decisions, no theory from fixtures."""
    from .cli import main as lab_main
    from .chatgpt_client import ChatGPTClient
    from .provider_base import AgentSettings, ProviderError
    if not sys.stdin.isatty():
        raise ValidationError('Il pilot richiede un terminale interattivo, senza input da pipe o file.')
    print('Pilot ChatGPT: 8 chiamate, 8 turni validi, 2 correzioni, 3 esperimenti, 3 punti per esperimento.')
    print('Usa il piano autorizzato di Zone. Controlla ChatGPT Settings → Usage: quota disponibile e crediti extra disabilitati. Il programma non verifica la spesa.')
    print('Output: nessun tetto token supportato dalla preview; risposta locale limitata a 64 KiB. Nessun fallback API.')
    if input('Scrivi piano dopo questi controlli, oppure Invio per annullare: ').strip() != 'piano':
        print('Pilot annullato; nessuna inferenza.')
        return 2
    client = ChatGPTClient(AgentSettings('catalog-only', timeout=30))
    try:
        models = client.models()
    except ProviderError as exc:
        print(f'Catalogo non disponibile ({exc.code}); nessuna inferenza.')
        return 2
    finally:
        client.close()
    # Validate model identifiers before display or reuse; catalog is not entitlement proof.
    models = [row for row in models if _valid_model(row['slug'])]
    if not models:
        raise ValidationError('Nessun modello disponibile nel catalogo di questo account.')
    if args.model:
        if args.model not in [row['slug'] for row in models]:
            raise ValidationError('Modello non presente nel catalogo: consulta chatgpt models.')
        model = args.model
    else:
        for index, row in enumerate(models, 1):
            print(f"{index}. {row['slug']}")
        while True:
            choice = input('Numero del modello (esci annulla): ').strip()
            if choice.lower() == 'esci':
                return 2
            if choice.isascii() and choice.isdecimal() and 1 <= int(choice) <= len(models):
                model = models[int(choice) - 1]['slug']
                break
            print('Scegli un numero presente; Invio non seleziona un modello.')
    tag = 'pilot12-chatgpt-' + secrets.token_hex(6)
    data = Path('benchmark_data') / tag
    private = str(data / 'private/world.json')
    manifest = str(data / 'public/manifest.json')
    config = str(data / 'private/config.json')
    for command in (
        ['forge', 'generate', '--level', '1', '--budget', '3', '--private', private,
         '--manifest', manifest, '--config-out', config],
        ['forge', 'check', '--private', private, '--manifest', manifest],
    ):
        result = lab_main(command)
        if result:
            return result
    session = str(Path('sessions') / tag)
    print(f'Sessione nuova: {session}; modello: {model}. Il pilot è separato dalle sessioni Gemini precedenti.')
    return lab_main(['investigate', '--provider', 'chatgpt', '--model', model,
                     '--config', config, '--session', session, '--max-calls', '8', '--max-turns', '8',
                     '--max-corrections', '2', '--timeout', '120', '--max-points', '3'])


def _valid_model(model):
    from .provider_base import AgentSettings
    try:
        AgentSettings(model)
        return True
    except ValidationError:
        return False
