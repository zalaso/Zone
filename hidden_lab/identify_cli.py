"""Identificazione locale su un mondo Forge dopo la chiusura dell'indagine."""

from hashlib import sha256
from pathlib import Path

from .benchmark_suite import save_new
from .identification import (identification_material, score_scientific_submission,
                             validate_scientific_submission)
from .protocol import ValidationError, decode, identifier, number, require_keys
from .simulator import parse_config
from .world_forge import read_world


def add_parser(commands):
    root = commands.add_parser("identify", help="Identificazione AST e previsione numerica offline")
    sub = root.add_subparsers(dest="identify_command", required=True)
    challenge = sub.add_parser("challenge", help="Pubblica i probe solo dopo una conclusione")
    challenge.add_argument("--world", required=True, type=Path)
    challenge.add_argument("--session", required=True, type=Path)
    challenge.add_argument("--out", required=True, type=Path)
    check = sub.add_parser("check", help="Valida una submission senza calcolare la verità")
    check.add_argument("--challenge", required=True, type=Path)
    check.add_argument("--submission", required=True, type=Path)
    score = sub.add_parser("score", help="Valuta la submission e conserva l'audit privato")
    score.add_argument("--world", required=True, type=Path)
    score.add_argument("--session", required=True, type=Path)
    score.add_argument("--challenge", required=True, type=Path)
    score.add_argument("--submission", required=True, type=Path)
    score.add_argument("--out", required=True, type=Path)


def _closed_session(record, directory):
    directory = Path(directory)
    config = decode((directory / "private" / "reproducibility.json").read_text(encoding="utf-8"))["config"]
    if config != parse_config(record["config"]).to_dict():
        raise ValidationError("La sessione non usa il mondo Forge selezionato.")
    raw = (directory / "public" / "events.jsonl").read_bytes()
    events = [decode(line) for line in raw.decode("utf-8").splitlines()]
    conclusions = [event for event in events if event.get("actor") == "agent" and
                   event.get("message", {}).get("type") == "conclusion"]
    if len(conclusions) != 1 or not events or events[-1] != conclusions[0]:
        raise ValidationError("La sessione deve terminare con una conclusione dell'agente.")
    return sha256(raw).hexdigest()


def _challenge(record, session_hash):
    return {"identification_version": "1", "world_id": record["world_id"],
            "world_manifest_hash": record["sha256"], "session_public_hash": session_hash,
            "probes": record["probes"]}


def _read_challenge(path):
    challenge = decode(Path(path).read_text(encoding="utf-8"))
    require_keys(challenge, ("identification_version", "world_id", "world_manifest_hash",
                             "session_public_hash", "probes"))
    if challenge["identification_version"] != "1" or not isinstance(challenge["probes"], list):
        raise ValidationError("Challenge di identificazione non valido.")
    if not challenge["probes"] or len(challenge["probes"]) > 64:
        raise ValidationError("Numero di probe non valido.")
    ids = set()
    for probe in challenge["probes"]:
        require_keys(probe, ("probe_id", "category", "x", "y", "vx", "vy"))
        probe_id = identifier(probe["probe_id"])
        if probe_id in ids or probe["category"] not in ("interpolation", "extrapolation"):
            raise ValidationError("ID o categoria di probe non validi.")
        ids.add(probe_id)
        for key in ("x", "y", "vx", "vy"):
            number(probe[key], -100, 100)
    return challenge


def _submission(path, challenge):
    raw = decode(Path(path).read_text(encoding="utf-8"))
    return validate_scientific_submission(raw, tuple(probe["probe_id"] for probe in challenge["probes"]))


def run_command(args):
    if args.identify_command == "check":
        challenge = _read_challenge(args.challenge)
        submission = _submission(args.submission, challenge)
        print(f"Submission valida: {len(submission['predictions'])} previsioni; "
              f"AST={'sì' if 'law_ast_json' in submission else 'no'}; "
              f"incertezza={'sì' if 'uncertainty_sigma' in submission else 'no'}.")
        return 0
    record = read_world(args.world)
    session_hash = _closed_session(record, args.session)
    expected = _challenge(record, session_hash)
    if args.identify_command == "challenge":
        save_new(args.out, expected)
        print(f"Challenge pubblico salvato: {args.out}; {len(record['probes'])} probe.")
        return 0
    challenge = _read_challenge(args.challenge)
    if challenge != expected:
        raise ValidationError("Challenge incoerente con il mondo o la sessione conclusa.")
    submission = _submission(args.submission, challenge)
    output = args.out
    output.mkdir(parents=True, exist_ok=False)
    (output / "public").mkdir()
    (output / "private").mkdir()
    save_new(output / "public" / "challenge.json", challenge)
    # Il commit della submission precede ogni accesso alla verità fisica.
    save_new(output / "public" / "submission.json", submission)
    material = identification_material(record["config"]["seed"], record["world_id"],
                                       record["sha256"])
    scores, audit = score_scientific_submission(submission, record["probes"],
                                                 parse_config(record["config"]).world, material)
    save_new(output / "private" / "probe_truth.json", audit["probe_truth"])
    if audit["secret_grid"] is not None:
        save_new(output / "private" / "identification_grid.json", audit["secret_grid"])
    result = {"identification_version": "1", "world_id": record["world_id"],
              "world_manifest_hash": record["sha256"], "session_public_hash": session_hash,
              "scores": scores}
    save_new(output / "result.json", result)
    print(f"RMSE previsione: {scores['prediction']['acceleration_rmse']:.6g} m/s²; "
          f"risultato: {output / 'result.json'}")
    return 0
