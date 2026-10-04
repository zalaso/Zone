"""CLI locale World Forge: file privati nuovi, manifest pubblico ridotto."""

import json
from pathlib import Path

from .protocol import ValidationError, decode
from .world_forge import (LEVEL_SPECS, generate_world, public_manifest,
                          read_world, validate_generated_world)


def add_parser(commands):
    root = commands.add_parser("forge", help="Genera e verifica mondi AST offline")
    sub = root.add_subparsers(dest="forge_command", required=True)
    generate = sub.add_parser("generate", help="Genera un mondo privato e un manifest pubblico")
    generate.add_argument("--level", type=int, required=True)
    generate.add_argument("--seed", type=int, help="Per demo riproducibili; senza seed usa 128 bit casuali")
    generate.add_argument("--budget", type=int, default=3)
    generate.add_argument("--private", required=True, type=Path)
    generate.add_argument("--manifest", required=True, type=Path)
    generate.add_argument("--config-out", type=Path,
                          help="Configurazione privata utilizzabile da shell/investigate")
    check = sub.add_parser("check", help="Ricalcola legge e controlli del mondo privato")
    check.add_argument("--private", required=True, type=Path)
    check.add_argument("--manifest", type=Path)
    sub.add_parser("levels", help="Elenca livelli implementati e interfacce future")


def _save_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def run_command(args):
    if args.forge_command == "levels":
        for spec in LEVEL_SPECS.values():
            status = "implementato" if spec.implemented else "interfaccia, non generabile"
            print(f"{spec.level}: {spec.name} - {status}; stato: {', '.join(spec.state_inputs)}")
        return 0
    if args.forge_command == "generate":
        paths = [args.private, args.manifest] + ([args.config_out] if args.config_out else [])
        resolved = [path.resolve() for path in paths]
        if len(set(resolved)) != len(resolved) or any(path.exists() for path in paths):
            raise ValidationError("Scegli percorsi nuovi e distinti per i file World Forge.")
        record = generate_world(args.seed, args.level, args.budget)
        manifest = public_manifest(record)
        _save_new(args.private, record)
        _save_new(args.manifest, manifest)
        if args.config_out:
            _save_new(args.config_out, record["config"])
        print(f"Mondo World Forge livello {args.level}: {record['world_id']}; "
              f"tentativo {record['attempt']}; SHA-256 {record['sha256']}.")
        return 0
    record = read_world(args.private)
    manifest = public_manifest(record)
    if args.manifest is not None and decode(args.manifest.read_text(encoding="utf-8")) != manifest:
        raise ValidationError("Manifest World Forge non corrispondente.")
    difficulty = validate_generated_world(record)
    print(f"Mondo valido: {record['world_id']}; livello {record['level']}; "
          f"esperimenti informativi {difficulty['informative_experiments']}; SHA-256 {record['sha256']}.")
    return 0
