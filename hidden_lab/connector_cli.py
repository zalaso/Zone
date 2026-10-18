"""Outbound-only companion: credentials stay on the user's computer.

The connector never chooses experiments and never executes one. It consumes only
jobs explicitly created by an authenticated owner's Avanza agente click.
"""

import getpass
import sys
import time
from urllib.parse import urlsplit

from .protocol import ValidationError
from .provider_base import AgentSettings, ProviderError
from .web_agent import safe_metadata


def add_parser(commands):
    parser = commands.add_parser('connector', help='Collega il sito alle tue AI senza esporre porte locali')
    parser.add_argument('--origin', required=True, help='Origine HTTPS del sito Zone')
    parser.add_argument('--provider', choices=('openai', 'anthropic', 'gemini', 'chatgpt', 'ollama'), required=True)
    parser.add_argument('--model', required=True, help='Stesso modello della connessione sul sito')
    parser.add_argument('--allow-inference', action='store_true', help='Consenti soltanto i passi richiesti dal tuo account sul sito')
    parser.add_argument('--login', action='store_true', help='Avvia esplicitamente Sign in with ChatGPT su questo computer')
    parser.add_argument('--local-http', action='store_true', help='Sviluppo: HTTP solo su 127.0.0.1')
    parser.add_argument('--max-jobs', type=int, default=20, help='Numero massimo di chiamate prima dell’arresto')


def validate_origin(origin, local_http=False):
    parsed = urlsplit(origin)
    if (parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment or not parsed.hostname
            or parsed.scheme != 'https' and not (local_http and parsed.scheme == 'http' and parsed.hostname == '127.0.0.1')):
        raise ValidationError('Origine HTTPS senza percorso; HTTP solo con --local-http su 127.0.0.1.')
    _ = parsed.port
    return origin


def process_job(job, model, client):
    """Exactly one model call. Replaying an HTTP reply never calls the model again."""
    from .connector_contract import restore_request
    request = restore_request(job['request'])
    if request.model != model or type(job.get('deadline')) not in (int, float) or job['deadline'] <= time.time():
        raise ValidationError('Modello diverso o passo scaduto; nessuna inferenza.')
    try:
        reply = client.complete(request)
        return {'lease': job['lease'], 'text': reply.text, 'metadata': safe_metadata(reply), 'issue': reply.issue}
    except ProviderError as exc:
        return {'lease': job['lease'], 'error': exc.code}


def run_command(args):
    if not args.allow_inference:
        raise ValidationError('Occorre --allow-inference; nessuna chiamata è autorizzata dal silenzio.')
    if not sys.stdin.isatty():
        raise ValidationError('Avvia il connettore in un terminale interattivo.')
    if not 1 <= args.max_jobs <= 100:
        raise ValidationError('max-jobs deve essere fra 1 e 100.')
    origin = validate_origin(args.origin, args.local_http)
    if args.login:
        if args.provider != 'chatgpt':
            raise ValidationError('--login è riservato a ChatGPT.')
        from .chatgpt_auth import CredentialStore, login
        if not login(CredentialStore()):
            return 2
    key = getpass.getpass('Chiave connettore mostrata dal sito (input nascosto): ').strip()
    if not key.startswith('zc_') or len(key) > 128:
        raise ValidationError('Chiave connettore non valida.')
    from .provider_factory import create_real_client
    import httpx
    settings = AgentSettings(args.model, timeout=100, max_calls=8, max_turns=8, max_corrections=1, max_points=3)
    client = create_real_client(args.provider, settings)
    count = 0
    try:
        with httpx.Client(base_url=origin, trust_env=False, follow_redirects=False, timeout=15,
                          headers={'X-Zone-Connector': key}) as http:
            print('Connettore attivo. Le chiamate partono dai tuoi clic su Avanza agente. Ctrl+C per fermare.')
            print('Nessuna porta locale pubblicata; nessun modello scaricato. Controlla quote e crediti del tuo provider.')
            while count < args.max_jobs:
                response = http.post('/v1/connector/poll', json={})
                if response.status_code != 200:
                    print(f'Connessione interrotta (HTTP {response.status_code}); nessun retry automatico.')
                    return 2
                job = response.json()['job']
                if job is None:
                    time.sleep(1)
                    continue
                count += 1
                print(f'Passo autorizzato {count}/{args.max_jobs}; attendo il modello…')
                body = process_job(job, args.model, client)
                response = http.post('/v1/connector/jobs/' + job['id'], json=body)
                if response.status_code != 200:
                    print('Risposta non confermata dal server. Non ripetere l’inferenza; controlla il registro sul sito.')
                    return 2
                print('Risposta consegnata; nessun esperimento eseguito dal connettore.')
    except httpx.HTTPError:
        print('Rete non disponibile; connettore arrestato senza retry o ripetizione di inferenze.')
        return 2
    finally:
        client.close()
    print('Limite di chiamate del connettore raggiunto.')
    return 0
