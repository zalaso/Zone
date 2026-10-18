"""Interactive pilot launcher. Billing status is confirmed by the human, not an API.

Run as ``python -m tools.free_gemini_pilot --model MODEL`` in a real terminal.
No downloads, credential files, automatic approvals, or provider fallbacks.
"""
import argparse
import getpass
import importlib.util
import json
import os
from pathlib import Path
import secrets
import sys
import time
import warnings

from hidden_lab.agent_contract import ModelRequest
from hidden_lab.cli import main as lab_main
from hidden_lab.protocol import ValidationError, decode
from hidden_lab.provider_base import AgentSettings, ProviderError
from hidden_lab.provider_factory import create_real_client


def run_diagnostic(data, model, output_mode="schema"):
    """One minimal generation, no Session, no world, no raw provider output saved."""
    settings = AgentSettings(model, max_calls=1, max_turns=1, max_corrections=0,
                             timeout=120, max_output_tokens=2500, max_points=3)
    request = ModelRequest(model, 'Rispondi esclusivamente con il JSON {"ok": true}.', [],
                           {'diagnostic': 'JSON connectivity only, no experiment'}, (),
                           {'type': 'object', 'properties': {'ok': {'type': 'boolean'}},
                            'required': ['ok'], 'additionalProperties': False}, 2500)
    client = create_real_client('gemini', settings, gemini_output_mode=output_mode)
    result = {'provider': client.provider, 'model': model, 'diagnostic_only': True,
              'experiments': 0, 'calls': 1, 'valid': False, 'error_code': None,
              'metadata': None, 'settings': settings.to_dict(), 'generation_settings': client.generation_settings}
    start = time.monotonic()
    print(f'Client diagnostica: {client.provider}; attendo una sola risposta, nessun esperimento.')
    try:
        try:
            reply = client.complete(request)
            result['metadata'] = reply.metadata
            if reply.issue:
                result['error_code'] = 'incomplete_response'
            else:
                try:
                    value = decode(reply.text)
                    result['valid'] = isinstance(value, dict) and set(value) == {'ok'} and value['ok'] is True
                except ValidationError:
                    pass
                if not result['valid']:
                    result['error_code'] = 'invalid_response'
        except ProviderError as exc:
            result['error_code'] = exc.code
        result['elapsed_seconds'] = round(time.monotonic() - start, 3)
        path = data / 'private/connectivity-result.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('x', encoding='utf-8') as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
        print(f"Diagnostica: {'JSON valido' if result['valid'] else result['error_code']}; "
              f"{result['elapsed_seconds']} s; una chiamata, zero esperimenti. Registro: {path}")
        return 0 if result['valid'] else 2
    finally:
        client.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Pilot Gemini con chiave nascosta e conferme umane")
    parser.add_argument('--model', required=True, help="ID con Free Tier e structured output, verificato in AI Studio")
    parser.add_argument('--diagnostic', action='store_true', help="Una sola richiesta JSON minima, senza mondo o esperimenti")
    parser.add_argument('--gemini-output-mode', choices=('schema', 'json'), default='schema',
                        help="schema vincolato (default), oppure JSON con contratto pubblico nel prompt")
    args = parser.parse_args(argv)
    if not sys.stdin.isatty():
        print('Apri un terminale interattivo: non sono ammessi input da file o pipe.')
        return 1
    try:
        AgentSettings(args.model)
        if importlib.util.find_spec('google.genai') is None:
            print("SDK Gemini assente: installa l'extra .[gemini] prima del pilot.")
            return 1
        print(f'Provider: Gemini Developer API; modello: {args.model}.')
        print(f'Modalità output Gemini: {args.gemini_output_mode}; validazione locale sempre obbligatoria.')
        if args.diagnostic:
            print('DIAGNOSTICA: 1 chiamata JSON minima, zero esperimenti, nessun retry; '
                  '120 s timeout e 2500 token output.')
        else:
            print('Limiti: 8 chiamate totali, 8 turni validi, 2 correzioni per passo, '
                  '120 s timeout, 2500 token output, 3 esperimenti e 3 punti per esperimento.')
        print('Controlla in AI Studio: progetto Free Tier senza fatturazione attiva, '
              'modello con quota gratuita disponibile. Il programma non verifica il billing.')
        if input('Scrivi free per confermare questi controlli, oppure Invio per annullare: ').strip() != 'free':
            print('Pilot annullato; nessuna chiamata al modello.')
            return 2
        tag = 'pilot12-gemini-' + secrets.token_hex(6)
        data = Path('benchmark_data') / tag
        data.mkdir(parents=True, exist_ok=False)
        world = str(data / 'private/world.json')
        manifest = str(data / 'public/manifest.json')
        config = str(data / 'private/config.json')
        session = str(Path('sessions') / tag)
        if not args.diagnostic:
            for command in (
                ['forge', 'generate', '--level', '1', '--budget', '3', '--private', world,
                 '--manifest', manifest, '--config-out', config],
                ['forge', 'check', '--private', world, '--manifest', manifest],
            ):
                result = lab_main(command)
                if result:
                    return result
            print(f'Sessione nuova: {session}.')
        print('Non incollare la chiave in chat o nei messaggi pubblici.')
        # getpass may fall back to echoed input: fail closed instead.
        with warnings.catch_warnings():
            warnings.simplefilter('error', getpass.GetPassWarning)
            key = getpass.getpass('Gemini API key (input nascosto): ').strip()
        if not key:
            print('Chiave vuota; nessuna chiamata al modello.')
            return 2
        previous = os.environ.get('GEMINI_API_KEY')
        try:
            os.environ['GEMINI_API_KEY'] = key
            del key
            if args.diagnostic:
                return run_diagnostic(data, args.model, args.gemini_output_mode)
            return lab_main(['investigate', '--provider', 'gemini', '--model', args.model,
                             '--gemini-output-mode', args.gemini_output_mode,
                             '--config', config, '--session', session,
                             '--max-calls', '8', '--max-turns', '8', '--max-corrections', '2',
                             '--timeout', '120', '--max-output-tokens', '2500', '--max-points', '3'])
        finally:
            if previous is None:
                os.environ.pop('GEMINI_API_KEY', None)
            else:
                os.environ['GEMINI_API_KEY'] = previous
    except ModuleNotFoundError:
        print("SDK Gemini assente: installa l'extra .[gemini] prima del pilot.")
        return 1
    except (KeyboardInterrupt, EOFError, getpass.GetPassWarning):
        print('\nPilot annullato o input nascosto indisponibile; nessun proseguimento automatico.')
        return 2
    except Exception:
        # Do not print arbitrary exception text: it could include a credential.
        print('Errore locale nel preparare il pilot; consulta docs/pilot-llm.md e i registri ridotti.')
        return 1


if __name__ == '__main__':
    sys.exit(main())
