"""Migrazioni additive atomiche e adozione verificata dei database fasi 4–8."""

from contextlib import closing
from hashlib import sha256
from pathlib import Path
import sqlite3

from .protocol import ValidationError
from .schema_sql import CORE_SQL, ARENA_SQL, INTEGRITY_SQL

INDEX_SQL = """
CREATE INDEX IF NOT EXISTS sessions_by_world ON sessions(world_id);
CREATE INDEX IF NOT EXISTS challenges_by_world ON arena_challenges(world_id,closed);
CREATE INDEX IF NOT EXISTS trials_by_challenge ON arena_trials(challenge_id);
CREATE INDEX IF NOT EXISTS tokens_by_agent ON arena_tokens(agent_id);
CREATE INDEX IF NOT EXISTS audit_by_principal ON arena_audit(principal,seq);
CREATE INDEX IF NOT EXISTS cases_by_pack ON integrity_cases(pack_id,split);
"""
MIGRATIONS = ((1, "adopt_local_schema", CORE_SQL + ARENA_SQL + INTEGRITY_SQL),
              (2, "operational_indexes", INDEX_SQL))
SCHEMA_VERSION = MIGRATIONS[-1][0]
LEDGER_SQL = """CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY, name TEXT NOT NULL, checksum TEXT NOT NULL,
    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"""


def checksum(sql):
    return sha256(sql.encode()).hexdigest()


def _statements(sql):
    # Only immutable internal SQL; no scripts or statements are accepted from a client.
    return [statement.strip() for statement in sql.split(";") if statement.strip()]


def _table_signature(db, name):
    unique = []
    for (index,) in db.execute('SELECT name FROM pragma_index_list(?) WHERE "unique"=1', (name,)):
        unique.append(tuple(row[0] for row in db.execute('SELECT name FROM pragma_index_info(?) ORDER BY seqno', (index,))))
    return (db.execute('SELECT * FROM pragma_table_info(?)', (name,)).fetchall(),
            db.execute('SELECT * FROM pragma_foreign_key_list(?)', (name,)).fetchall(),
            sorted(unique, key=repr))


def _expected_tables():
    with closing(sqlite3.connect(":memory:")) as db:
        for statement in _statements(MIGRATIONS[0][2]) + [LEDGER_SQL]:
            db.execute(statement)
        names = [row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name!='sqlite_sequence'")]
        return {name: _table_signature(db, name) for name in names}


EXPECTED_TABLES = _expected_tables()


def _layout(db, *, complete):
    tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name!='sqlite_sequence'")}
    if tables - EXPECTED_TABLES.keys() or complete and tables != EXPECTED_TABLES.keys():
        raise ValidationError("Schema SQLite non compatibile con Zone.")
    for name in tables:
        if _table_signature(db, name) != EXPECTED_TABLES[name]:
            raise ValidationError("Colonne o vincoli SQLite incompatibili: migrazione rifiutata.")
    if db.execute("SELECT 1 FROM sqlite_master WHERE type IN ('view','trigger')").fetchone():
        raise ValidationError("Oggetti SQLite inattesi: migrazione rifiutata.")


def schema_status(db):
    version = db.execute("PRAGMA user_version").fetchone()[0]
    if version < 0 or version > SCHEMA_VERSION:
        raise ValidationError("Versione SQLite futura o non supportata.")
    ledger = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_migrations'").fetchone()
    if version and not ledger:
        raise ValidationError("Registro delle migrazioni mancante.")
    if ledger:
        expected = [(v, name, checksum(sql)) for v, name, sql in MIGRATIONS if v <= version]
        if db.execute("SELECT version,name,checksum FROM schema_migrations ORDER BY version").fetchall() != expected:
            raise ValidationError("Registro delle migrazioni alterato o incoerente.")
    return {"schema_version": version, "target_version": SCHEMA_VERSION,
            "pending": [v for v, _, _ in MIGRATIONS if v > version], "legacy": version == 0}


def migrate_connection(db):
    if db.in_transaction:
        raise ValidationError("Migrazione richiede una connessione senza transazioni aperte.")
    db.execute("BEGIN IMMEDIATE")
    try:
        _layout(db, complete=False)
        status = schema_status(db)
        db.execute(LEDGER_SQL)
        for version, name, sql in MIGRATIONS:
            if version > status["schema_version"]:
                for statement in _statements(sql):
                    db.execute(statement)
                db.execute("INSERT INTO schema_migrations(version,name,checksum) VALUES(?,?,?)",
                           (version, name, checksum(sql)))
                db.execute(f"PRAGMA user_version={version}")
        _layout(db, complete=True)
        if db.execute("PRAGMA foreign_key_check").fetchone():
            raise ValidationError("Relazioni SQLite non valide: migrazione annullata.")
        db.commit()
    except BaseException:
        db.rollback()
        raise
    return schema_status(db)


def connect_existing(path, *, readonly=True):
    path = Path(path).resolve()
    if not path.is_file():
        raise ValidationError("Database SQLite esistente richiesto.")
    db = sqlite3.connect(path.as_uri() + ("?mode=ro" if readonly else "?mode=rw"), uri=True, timeout=5)
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA busy_timeout=5000")
    return db


def check_database(path):
    with closing(connect_existing(path)) as db:
        _layout(db, complete=db.execute("PRAGMA user_version").fetchone()[0] != 0)
        status = schema_status(db)
        if db.execute("PRAGMA integrity_check").fetchall() != [("ok",)] or db.execute("PRAGMA foreign_key_check").fetchone():
            raise ValidationError("Verifica SQLite fallita.")
        return status
