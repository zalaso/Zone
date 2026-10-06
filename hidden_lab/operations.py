"""Backup privati con SQLite Online Backup API; restore solo su destinazioni nuove."""

from contextlib import closing
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
import re
from pathlib import Path
import sqlite3
import time

from . import __version__
from .migrations import check_database, connect_existing, migrate_connection, schema_status
from .protocol import ValidationError, _unique_object, _invalid_constant, require_keys


def file_hash(path):
    result = sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def _new_file(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise ValidationError("La destinazione deve essere nuova; nessuna sovrascrittura.") from None
    os.close(fd)


def _copy_database(source, destination, timeout):
    start = time.monotonic()
    def progress(_status, _remaining, _total):
        if time.monotonic() - start >= timeout:
            raise ValidationError("Timeout del backup SQLite; copia incompleta rimossa.")
    with closing(connect_existing(source)) as old, closing(sqlite3.connect(destination, timeout=5)) as new:
        old.backup(new, pages=64, progress=progress, sleep=0.05)
    with Path(destination).open("r+b") as stream:
        os.fsync(stream.fileno())


def backup_database(source, destination, *, timeout=60):
    destination = Path(destination)
    proof = Path(str(destination) + ".manifest.json")
    if not 1 <= timeout <= 60:
        raise ValidationError("Timeout backup fuori limite (1–60 secondi).")
    if destination.exists() or proof.exists():
        raise ValidationError("Backup e manifest richiedono destinazioni nuove.")
    check_database(source)
    made = []
    try:
        _new_file(destination)
        made.append(destination)
        _new_file(proof)
        made.append(proof)
        _copy_database(source, destination, timeout)
        status = check_database(destination)
        record = {"backup_version": 1, "zone_version": __version__, "schema_version": status["schema_version"],
                  "created_at": datetime.now(timezone.utc).isoformat(), "sha256": file_hash(destination)}
        with proof.open("w", encoding="utf-8") as stream:
            json.dump(record, stream, ensure_ascii=False, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        return record
    except BaseException:
        for path in reversed(made):
            path.unlink(missing_ok=True)
        raise


def restore_database(source, destination, *, timeout=60):
    source, destination = Path(source), Path(destination)
    if not 1 <= timeout <= 60:
        raise ValidationError("Timeout restore fuori limite (1–60 secondi).")
    proof = Path(str(source) + ".manifest.json")
    try:
        with proof.open("rb") as stream:
            raw = stream.read(4097)
        if len(raw) > 4096:
            raise ValueError()
        record = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object, parse_constant=_invalid_constant)
        require_keys(record, ("backup_version", "zone_version", "schema_version", "created_at", "sha256"))
        if (type(record["backup_version"]) is not int or record["backup_version"] != 1
                or type(record["schema_version"]) is not int or record["schema_version"] < 0
                or not isinstance(record["zone_version"], str) or not record["zone_version"]
                or not isinstance(record["sha256"], str) or not re.fullmatch(r"[a-f0-9]{64}", record["sha256"])
                or not isinstance(record["created_at"], str)
                or datetime.fromisoformat(record["created_at"]).tzinfo is None):
            raise ValueError()
    except (OSError, ValueError, UnicodeError, TypeError):
        raise ValidationError("Manifest del backup mancante o non valido.") from None
    if record["backup_version"] != 1 or record["sha256"] != file_hash(source):
        raise ValidationError("Hash o versione del backup non validi.")
    status = check_database(source)
    if record["schema_version"] != status["schema_version"]:
        raise ValidationError("Schema del backup incoerente.")
    _new_file(destination)
    try:
        _copy_database(source, destination, timeout)
        restored = check_database(destination)
        if file_hash(source) != record["sha256"]:
            raise ValidationError("Backup modificato durante il restore.")
        return restored
    except BaseException:
        destination.unlink(missing_ok=True)
        raise


def retention_status(path):
    status = check_database(path)
    names = ("events", "agent_calls", "arena_receipts", "arena_audit", "arena_tokens", "integrity_cases")
    with closing(connect_existing(path)) as db:
        present = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        counts = {name: db.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0] if name in present else 0 for name in names}
    return {**status, "bytes": Path(path).stat().st_size, "rows": counts, "deleted": 0}


def add_parser(commands):
    root = commands.add_parser("ops", help="Migrazioni, backup/restore privati e demo offline")
    sub = root.add_subparsers(dest="ops_command", required=True)
    for name in ("status", "check", "migrate", "retention", "backup"):
        item = sub.add_parser(name)
        item.add_argument("--db", type=Path, required=True)
        if name == "backup":
            item.add_argument("--out", type=Path, required=True)
            item.add_argument("--timeout", type=int, default=60)
    restore = sub.add_parser("restore")
    restore.add_argument("--backup", type=Path, required=True)
    restore.add_argument("--out", type=Path, required=True)
    restore.add_argument("--timeout", type=int, default=60)
    demo = sub.add_parser("demo")
    demo.add_argument("--out", type=Path, required=True, help="Cartella nuova; nessuna chiamata API")


def run_command(args):
    try:
        return _run_command(args)
    except sqlite3.Error:
        raise ValidationError("Operazione SQLite fallita; conserva il database originale e verifica schema e accesso.") from None


def _run_command(args):
    command = args.ops_command
    if command == "demo":
        from .demo_workflow import run_demo
        return run_demo(args.out)
    if command == "migrate":
        with closing(connect_existing(args.db, readonly=False)) as db:
            result = migrate_connection(db)
    elif command == "status":
        with closing(connect_existing(args.db)) as db:
            result = schema_status(db)
    elif command == "check":
        result = check_database(args.db)
    elif command == "retention":
        result = retention_status(args.db)
    elif command == "backup":
        result = backup_database(args.db, args.out, timeout=args.timeout)
    else:
        result = restore_database(args.backup, args.out, timeout=args.timeout)
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))
    return 0
