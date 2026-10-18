"""Avvio locale: baseline offline, provider reale solo con opzioni esplicite."""

import os
from pathlib import Path

from .world_forge import read_world


def add_parser(commands):
    parser = commands.add_parser("serve", help="Backend FastAPI locale (extra backend)")
    parser.add_argument("--db", required=True, type=Path, help="File SQLite privato")
    parser.add_argument('--auth-mode', choices=('local', 'accounts'), default='local')
    parser.add_argument('--public-origin', help='Origine esatta del browser, senza slash finale')
    parser.add_argument('--local-cookies', action='store_true', help='Cookie HTTP solo per loopback; mai per utenti esterni')
    parser.add_argument('--public-workspace', action='store_true', help='Workspace multiutente con AI personali')
    parser.add_argument('--open-registration', action='store_true', help='Abilita registrazione autonoma soltanto sul bersaglio scelto')
    parser.add_argument('--max-accounts', type=int, default=1000, help='Capacità iniziale registrazioni; non modifica gli account esistenti')
    parser.add_argument("--world", action="append", type=Path, default=[],
                        help="Record World Forge privato; ripetibile")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--host", choices=("127.0.0.1", "0.0.0.0"), default="127.0.0.1")
    parser.add_argument("--container-local", action="store_true", help="Consente 0.0.0.0 solo per il container pubblicato su loopback")
    parser.add_argument("--web-dir", type=Path, help="Solo bundle compilato, es. frontend/dist")
    parser.add_argument("--environment", choices=("local", "staging-local"), default=os.environ.get("ZONE_ENV", "local"))
    parser.add_argument("--integrity-pack", action="append", type=Path, default=[], help="Pacchetto split privato v1; registra mondi e policy")
    parser.add_argument("--agent-provider", choices=("openai", "chatgpt", "anthropic", "gemini", "ollama"))
    parser.add_argument("--agent-model")
    parser.add_argument("--agent-owner", help="ID account Zone autorizzato al piano ChatGPT personale")
    parser.add_argument("--chatgpt-credentials-dir", type=Path, help="Archivio OAuth privato, fuori da dati e registri")
    parser.add_argument("--allow-real-agent", action="store_true",
                        help="Abilita un provider reale: ogni passo web può consumare chiamate")
    parser.add_argument("--agent-max-calls", type=int, default=20)
    parser.add_argument("--agent-max-turns", type=int, default=15)
    parser.add_argument("--agent-timeout", type=float, default=30)
    parser.add_argument("--agent-max-corrections", type=int, default=2)
    parser.add_argument("--agent-max-points", type=int, default=9)


def run_command(args):
    if args.host != "127.0.0.1" and not args.container_local:
        raise ValueError("Il bind non loopback richiede --container-local; non pubblicare la porta all'esterno.")
    if args.environment not in ("local", "staging-local"):
        raise ValueError("Ambiente Zone non supportato; nessuna modalità pubblica abilitata.")
    if not 1024 <= args.port <= 65535:
        raise ValueError("Porta locale fuori intervallo.")
    if args.auth_mode == 'local' and (args.public_origin or args.local_cookies):
        raise ValueError('Origine e cookie sono opzioni della modalità accounts.')
    if args.chatgpt_credentials_dir is not None and args.agent_provider != 'chatgpt':
        raise ValueError('Archivio OAuth ammesso solo con --agent-provider chatgpt.')
    if args.agent_owner and (args.agent_provider != 'chatgpt' or args.auth_mode != 'accounts'):
        raise ValueError('--agent-owner richiede chatgpt e autenticazione accounts.')
    if args.agent_provider == 'chatgpt' and args.auth_mode == 'accounts' and not args.agent_owner:
        raise ValueError('Il piano ChatGPT personale richiede --agent-owner in modalità accounts.')
    if args.auth_mode == 'local' and not os.environ.get("ZONE_OPERATOR_TOKEN"):
        raise ValueError("Imposta ZONE_OPERATOR_TOKEN prima dell'avvio.")
    records = [read_world(path) for path in args.world]
    from .integrity_suite import read_pack
    packs = [read_pack(path) for path in args.integrity_pack]
    from .provider_base import AgentSettings
    settings = AgentSettings(args.agent_model or "offline-affine-v1", max_calls=args.agent_max_calls,
        max_turns=args.agent_max_turns, timeout=args.agent_timeout, max_corrections=args.agent_max_corrections,
        max_points=args.agent_max_points)
    client = None
    if args.agent_provider or args.agent_model or args.allow_real_agent:
        if not (args.agent_provider and args.agent_model and args.allow_real_agent):
            raise ValueError("Per un agente reale servono --agent-provider, --agent-model e --allow-real-agent.")
        from .provider_factory import create_real_client
        if args.agent_provider == 'chatgpt':
            from .chatgpt_auth import CredentialStore
            client = create_real_client(args.agent_provider, settings,
                chatgpt_store=CredentialStore(args.chatgpt_credentials_dir))
        else:
            client = create_real_client(args.agent_provider, settings)
    from .backend import create_app
    from .runtime_ops import configure_logging
    configure_logging()
    import uvicorn
    try:
        app = create_app(args.db, worlds=records, agent_client=client, agent_settings=settings, integrity_packs=packs,
                         static_dir=args.web_dir, auth_mode=args.auth_mode, public_origin=args.public_origin,
                         secure_cookies=not args.local_cookies, agent_owner=args.agent_owner,
                         public_workspace=args.public_workspace, open_registration=args.open_registration,
                         connection_key=os.environ.get('ZONE_CONNECTION_KEY'), max_accounts=args.max_accounts)
        uvicorn.run(app, host=args.host, port=args.port, access_log=False, proxy_headers=False)
    finally:
        if client is not None:
            client.close()
    return 0
