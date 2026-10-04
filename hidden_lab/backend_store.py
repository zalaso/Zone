"""Repository SQLite per il backend; l'API usa solo questa interfaccia di persistenza."""

import json
from contextlib import contextmanager
from pathlib import Path
import secrets
import sqlite3
from typing import Protocol

from .protocol import ValidationError
from .world_forge import public_manifest, validate_generated_world


class ConflictError(Exception):
    pass


class NotFoundError(Exception):
    pass


class SessionRepository(Protocol):
    """Contratto usato dal servizio; il motore HTTP non conosce query SQL."""

    def list_worlds(self): ...
    def create_session(self, world_id, agent_token_hash, apparatus_message): ...
    def read_session(self, session_id): ...
    def append(self, session_id, expected_version, entries): ...
    def save_score(self, session_id, expected_version, score, audit): ...


def _json(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


class SQLiteRepository:
    """Eventi append-only e CAS su seq; sostituibile dietro gli stessi metodi."""

    def __init__(self, path, worlds=()):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS worlds (
                    id TEXT PRIMARY KEY, record_json TEXT NOT NULL, manifest_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY, world_id TEXT NOT NULL REFERENCES worlds(id),
                    agent_token_hash TEXT NOT NULL, score_json TEXT, audit_json TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS events (
                    session_id TEXT NOT NULL REFERENCES sessions(id), seq INTEGER NOT NULL,
                    actor TEXT NOT NULL, message_json TEXT NOT NULL,
                    PRIMARY KEY (session_id, seq)
                );
            """)
            for record in worlds:
                validate_generated_world(record)
                world_id = record["world_id"]
                old = db.execute("SELECT record_json FROM worlds WHERE id=?", (world_id,)).fetchone()
                if old is not None and json.loads(old[0]) != record:
                    raise ValidationError("ID mondo già presente con contenuto diverso.")
                if old is None:
                    db.execute("INSERT INTO worlds(id,record_json,manifest_json) VALUES(?,?,?)",
                               (world_id, _json(record), _json(public_manifest(record))))

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        try:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("PRAGMA busy_timeout=5000")
            with db:
                yield db
        finally:
            db.close()

    def list_worlds(self):
        with self._connect() as db:
            return [json.loads(row[0]) for row in db.execute(
                "SELECT manifest_json FROM worlds ORDER BY id")]

    def create_session(self, world_id, agent_token_hash, apparatus_message):
        session_id = secrets.token_hex(16)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM worlds WHERE id=?", (world_id,)).fetchone() is None:
                raise NotFoundError()
            db.execute("INSERT INTO sessions(id,world_id,agent_token_hash) VALUES(?,?,?)",
                       (session_id, world_id, agent_token_hash))
            db.execute("INSERT INTO events(session_id,seq,actor,message_json) VALUES(?,?,?,?)",
                       (session_id, 1, "apparatus", _json(apparatus_message)))
        return session_id

    def read_session(self, session_id):
        with self._connect() as db:
            db.execute("BEGIN")  # metadata ed eventi nella stessa snapshot
            row = db.execute("SELECT s.world_id,s.agent_token_hash,s.score_json,s.audit_json,w.record_json "
                "FROM sessions s JOIN worlds w ON s.world_id=w.id WHERE s.id=?", (session_id,)).fetchone()
            if row is None:
                raise NotFoundError()
            events = [{"seq": seq, "actor": actor, "message": json.loads(message)}
                      for seq, actor, message in db.execute(
                          "SELECT seq,actor,message_json FROM events WHERE session_id=? ORDER BY seq",
                          (session_id,))]
            return {"id": session_id, "world_id": row[0], "agent_token_hash": row[1],
                    "score": json.loads(row[2]) if row[2] is not None else None,
                    "audit": json.loads(row[3]) if row[3] is not None else None,
                    "record": json.loads(row[4]), "events": events}

    def append(self, session_id, expected_version, entries):
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM sessions WHERE id=?", (session_id,)).fetchone() is None:
                raise NotFoundError()
            version = db.execute("SELECT COALESCE(MAX(seq),0) FROM events WHERE session_id=?",
                                 (session_id,)).fetchone()[0]
            if version != expected_version:
                raise ConflictError()
            for actor, message in entries:
                version += 1
                db.execute("INSERT INTO events(session_id,seq,actor,message_json) VALUES(?,?,?,?)",
                           (session_id, version, actor, _json(message)))
        return version

    def save_score(self, session_id, expected_version, score, audit):
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT score_json FROM sessions WHERE id=?", (session_id,)).fetchone()
            if row is None:
                raise NotFoundError()
            version = db.execute("SELECT COALESCE(MAX(seq),0) FROM events WHERE session_id=?",
                                 (session_id,)).fetchone()[0]
            if version != expected_version or row[0] is not None:
                raise ConflictError()
            db.execute("UPDATE sessions SET score_json=?,audit_json=? WHERE id=?",
                       (_json(score), _json(audit), session_id))
            db.execute("INSERT INTO events(session_id,seq,actor,message_json) VALUES(?,?,?,?)",
                       (session_id, version + 1, "apparatus",
                        _json({"type": "result_recorded", "scores": score})))
