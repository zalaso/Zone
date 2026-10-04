"""Terminale dell'operatore: modalità manuale e indagine assistita da LLM."""

import argparse
import json
import os
from pathlib import Path
import sys

from .plotting import plot_trajectory
from .protocol import ValidationError, decode
from .session import Session
from .simulator import parse_config

HELP = """Sessione MANUALE: nessun agente LLM collegato.
agent <JSON>       richiesta, ipotesi o previsione
operator <JSON>    approvazione, modifica o rifiuto
agent @file.json   legge un messaggio JSON da file (anche per operator)
run <request_id>  esegue l'esperimento approvato
plot <request_id> salva il grafico usando solo il registro pubblico
status            mostra conteggio e richiesta in attesa
help              mostra questi comandi
quit              termina; il registro rimane su disco
"""


def display(events):
    for event in events:
        print(json.dumps(event, ensure_ascii=False, allow_nan=False))


def execute_line(session, line):
    """Un solo percorso di esecuzione per terminale e copione dimostrativo."""
    line = line.strip()
    if not line or line.startswith("#"):
        return True
    command, _, payload = line.partition(" ")
    before = len(session.events)
    try:
        if command == "quit":
            return False
        if command == "help":
            print(HELP)
        elif command in ("agent", "operator"):
            payload = payload.strip()
            if payload.startswith("@"):
                payload = Path(payload[1:]).read_text(encoding="utf-8-sig")
            session.submit(decode(payload), actor=command)
        elif command == "run":
            session.run(payload.strip())
        elif command == "plot":
            print(f"Grafico pubblico: {plot_trajectory(session.directory / 'public', payload.strip())}")
        elif command == "status":
            print(json.dumps({"executed_count": session.executed_count,
                              "remaining_budget": session.config.experiment_budget - session.executed_count,
                              "pending_request": session.pending}))
        else:
            raise ValidationError("Comando sconosciuto; usa help.")
    except ValidationError as exc:
        session.record_error(str(exc))
        display(session.events[before:])
        raise
    display(session.events[before:])
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description="Laboratorio di fisica nascosta")
    commands = parser.add_subparsers(dest="command", required=True)
    for name, description in (("shell", "Terminale interattivo"), ("demo", "Esegue un copione MANUALE, senza LLM")):
        child = commands.add_parser(name, help=description)
        child.add_argument("--config", required=True, type=Path, help="Configurazione privata dell'operatore")
        child.add_argument("--session", required=True, type=Path, help="Nuova cartella; non deve esistere")
        if name == "demo":
            child.add_argument("--script", required=True, type=Path, help="Copione testuale di comandi manuali")
    plot = commands.add_parser("plot", help="Genera un grafico da un registro pubblico esistente")
    plot.add_argument("--public", required=True, type=Path)
    plot.add_argument("--request", required=True)
    agent = commands.add_parser("investigate", help="Agente LLM con operatore umano, oppure client simulato offline")
    agent.add_argument("--config", required=True, type=Path)
    agent.add_argument("--session", required=True, type=Path)
    agent.add_argument("--provider", "--client", dest="provider", required=True,
                       choices=("openai", "anthropic", "gemini", "ollama", "simulated"))
    agent.add_argument("--model", help="ID del modello; altrimenti <PROVIDER>_MODEL, senza default reale")
    agent.add_argument("--max-calls", type=int, default=20)
    agent.add_argument("--max-turns", type=int, default=15)
    agent.add_argument("--max-corrections", type=int, default=2)
    agent.add_argument("--timeout", type=float, default=30)
    agent.add_argument("--max-output-tokens", type=int, default=2500)
    agent.add_argument("--max-points", type=int, default=9)
    agent.add_argument("--max-input-bytes", type=int, default=200000)
    from .benchmark_cli import add_parser as add_benchmark_parser
    add_benchmark_parser(commands)
    from .world_forge_cli import add_parser as add_forge_parser
    add_forge_parser(commands)
    from .identify_cli import add_parser as add_identify_parser
    add_identify_parser(commands)
    from .server_cli import add_parser as add_server_parser
    add_server_parser(commands)
    args = parser.parse_args(argv)
    try:
        if args.command == "plot":
            print(plot_trajectory(args.public, args.request))
            return 0
        if args.command == "benchmark":
            from .benchmark_cli import run_command
            return run_command(args)
        if args.command == "forge":
            from .world_forge_cli import run_command
            return run_command(args)
        if args.command == "identify":
            from .identify_cli import run_command
            return run_command(args)
        if args.command == "serve":
            from .server_cli import run_command
            return run_command(args)
        config = parse_config(decode(args.config.read_text(encoding="utf-8-sig")))
        if args.command == "investigate":
            from .investigation import Investigation
            from .provider_base import AgentSettings
            from .terminal import Terminal
            model_env = {"openai": "OPENAI_MODEL", "anthropic": "ANTHROPIC_MODEL",
                         "gemini": "GEMINI_MODEL", "ollama": "OLLAMA_MODEL"}
            settings = AgentSettings(model=(args.model or os.environ.get(model_env[args.provider], ""))
                                     if args.provider != "simulated" else "simulated-script-v1",
                                     max_calls=args.max_calls, max_turns=args.max_turns,
                                     max_corrections=args.max_corrections, timeout=args.timeout,
                                     max_output_tokens=args.max_output_tokens, max_points=args.max_points,
                                     max_input_bytes=args.max_input_bytes)
            if args.provider == "openai":
                from .provider_factory import create_real_client
                client = create_real_client(args.provider, settings)
            elif args.provider == "anthropic":
                from .provider_factory import create_real_client
                client = create_real_client(args.provider, settings)
            elif args.provider == "gemini":
                from .provider_factory import create_real_client
                client = create_real_client(args.provider, settings)
            elif args.provider == "ollama":
                from .provider_factory import create_real_client
                client = create_real_client(args.provider, settings)
            else:
                from .fake_client import SimulatedClient
                client = SimulatedClient()
            try:
                session = Session(args.session, config)
                completed = Investigation(session, client, settings, Terminal()).run()
                return 0 if completed else 2
            finally:
                client.close()
        script = args.script.read_text(encoding="utf-8-sig").splitlines() if args.command == "demo" else None
        session = Session(args.session, config)
        print(HELP)
        display(session.events)
        if script is not None:
            for line in script:
                if not execute_line(session, line):
                    break
            print(f"Demo MANUALE completata: {session.executed_count} esperimenti eseguiti.")
        else:
            while True:
                try:
                    line = input("lab> ")
                except EOFError:
                    break
                try:
                    if not execute_line(session, line):
                        break
                except ValidationError:
                    continue
                except ValueError as exc:
                    # Canale locale dell'operatore: mai nel registro pubblico.
                    print(f"Errore locale dell'operatore: {exc}", file=sys.stderr)
    except (OSError, ValueError, ImportError) as exc:
        print(f"Errore locale dell'operatore: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nSessione interrotta dall'operatore; controlla il registro prima di usarne i risultati.", file=sys.stderr)
        return 130
    return 0
