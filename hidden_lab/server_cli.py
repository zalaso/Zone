"""Avvio locale: baseline offline, provider reale solo con opzioni esplicite."""

import os
from pathlib import Path

from .world_forge import read_world


def add_parser(commands):
    parser = commands.add_parser("serve", help="Backend FastAPI locale (extra backend)")
    parser.add_argument("--db", required=True, type=Path, help="File SQLite privato")
    parser.add_argument("--world", action="append", type=Path, default=[],
                        help="Record World Forge privato; ripetibile")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--agent-provider", choices=("openai", "anthropic", "gemini", "ollama"))
    parser.add_argument("--agent-model")
    parser.add_argument("--allow-real-agent", action="store_true",
                        help="Abilita un provider reale: ogni passo web può consumare chiamate")
    parser.add_argument("--agent-max-calls", type=int, default=20)
    parser.add_argument("--agent-max-turns", type=int, default=15)
    parser.add_argument("--agent-timeout", type=float, default=30)
    parser.add_argument("--agent-max-corrections", type=int, default=2)


def run_command(args):
    if not 1024 <= args.port <= 65535:
        raise ValueError("Porta locale fuori intervallo.")
    if not os.environ.get("ZONE_OPERATOR_TOKEN"):
        raise ValueError("Imposta ZONE_OPERATOR_TOKEN prima dell'avvio.")
    records = [read_world(path) for path in args.world]
    from .provider_base import AgentSettings
    settings = AgentSettings(args.agent_model or "offline-affine-v1", max_calls=args.agent_max_calls,
        max_turns=args.agent_max_turns, timeout=args.agent_timeout, max_corrections=args.agent_max_corrections)
    client = None
    if args.agent_provider or args.agent_model or args.allow_real_agent:
        if not (args.agent_provider and args.agent_model and args.allow_real_agent):
            raise ValueError("Per un agente reale servono --agent-provider, --agent-model e --allow-real-agent.")
        from .provider_factory import create_real_client
        client = create_real_client(args.agent_provider, settings)
    from .backend import create_app
    import uvicorn
    try:
        app = create_app(args.db, worlds=records, agent_client=client, agent_settings=settings)
        uvicorn.run(app, host="127.0.0.1", port=args.port, access_log=False)
    finally:
        if client is not None:
            client.close()
    return 0
