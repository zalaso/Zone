"""Preparazione e verifiche offline: output pubblici e privati in cartelle distinte."""

from pathlib import Path

from .benchmark_suite import save_new
from .integrity_suite import SPLITS, make_pack, manifest, read_json, read_pack, verify_reveal
from .protocol import ValidationError


def add_parser(commands):
    root = commands.add_parser("integrity", help="Split train/development/test e manifest impegnati v1")
    sub = root.add_subparsers(dest="integrity_command", required=True)
    prepare = sub.add_parser("prepare", help="Nuovo pacchetto; nessun modello o rete")
    prepare.add_argument("--out", required=True, type=Path)
    prepare.add_argument("--kind", choices=("forge", "benchmark"), default="forge")
    prepare.add_argument("--levels", type=int, nargs="+", default=[1, 2, 3, 4, 5])
    prepare.add_argument("--per-level", type=int, default=1)
    prepare.add_argument("--budget", type=int, default=3)
    prepare.add_argument("--seed", type=int, help="Solo demo; omettere per un test cieco")
    check = sub.add_parser("check", help="Verifica split, duplicati, commitment e file pubblici")
    check.add_argument("--pack", required=True, type=Path, help="Cartella prodotta da prepare")
    verify = sub.add_parser("verify-reveal", help="Verifica proof contro il manifest originale")
    verify.add_argument("--manifest", required=True, type=Path)
    verify.add_argument("--proof", required=True, type=Path)
    verify.add_argument("--expected-manifest-hash", required=True, help="Hash conservato prima del reveal")


def run_command(args):
    if args.integrity_command == "prepare":
        if args.out.exists():
            raise ValidationError("La cartella del pacchetto deve essere nuova.")
        pack = make_pack(args.seed, kind=args.kind, levels=args.levels, per_level=args.per_level, budget=args.budget)
        args.out.mkdir(parents=True, exist_ok=False)
        save_new(args.out / "private" / "pack.json", pack)
        save_new(args.out / "public" / "manifest.json", manifest(pack))
        for split in SPLITS:
            destination = "private" if split == "test" else "public"
            save_new(args.out / destination / f"{split}.json", pack["splits"][split])
        print(f"Pacchetto {args.kind} preparato; manifest SHA-256 {manifest(pack)['sha256']}. Nessun trial eseguito.")
        return 0
    if args.integrity_command == "check":
        pack = read_pack(args.pack / "private" / "pack.json")
        if read_json(args.pack / "public" / "manifest.json") != manifest(pack):
            raise ValidationError("Manifest pubblico alterato o non corrispondente.")
        for split in SPLITS:
            path = args.pack / ("private" if split == "test" else "public") / f"{split}.json"
            if read_json(path) != pack["splits"][split]:
                raise ValidationError("Dataset split alterato o non corrispondente.")
        print("Pacchetto valido: split disgiunti, commitment coerenti, duplicati controllati sulla griglia finita.")
        return 0
    try:
        verify_reveal(read_json(args.manifest), read_json(args.proof), args.expected_manifest_hash)
    except (KeyError, TypeError, AttributeError):
        raise ValidationError("Struttura di manifest o proof non valida.") from None
    print("Reveal verificato contro l'hash del manifest originale.")
    return 0
