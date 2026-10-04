"""Avvio locale del backend: nessun provider o modello viene caricato."""

import os
from pathlib import Path

from .world_forge import read_world


def add_parser(commands):
    parser = commands.add_parser("serve", help="Backend FastAPI locale (extra backend)")
    parser.add_argument("--db", required=True, type=Path, help="File SQLite privato")
    parser.add_argument("--world", action="append", type=Path, default=[],
                        help="Record World Forge privato; ripetibile")
    parser.add_argument("--port", type=int, default=8765)


def run_command(args):
    if not 1024 <= args.port <= 65535:
        raise ValueError("Porta locale fuori intervallo.")
    if not os.environ.get("ZONE_OPERATOR_TOKEN"):
        raise ValueError("Imposta ZONE_OPERATOR_TOKEN prima dell'avvio.")
    records = [read_world(path) for path in args.world]
    from .backend import create_app
    app = create_app(args.db, worlds=records)
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=args.port, access_log=False)
    return 0
