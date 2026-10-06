"""Repository SQLite per il backend; l'API usa solo questa interfaccia di persistenza."""

import json
from contextlib import contextmanager
from pathlib import Path
import secrets
import sqlite3
from typing import Protocol

from .protocol import ValidationError
from .local_worlds import local_manifest, validate_local_world


class ConflictError(Exception):
    pass


class NotFoundError(Exception):
    pass


class SessionRepository(Protocol):
    """Contratto usato dal servizio; il motore HTTP non conosce query SQL."""

    def list_worlds(self): ...
    def register_world(self, record): ...
    def read_world(self, world_id): ...
    def create_session(self, world_id, agent_token_hash, apparatus_message, profile=None): ...
    def read_session(self, session_id): ...
    def append(self, session_id, expected_version, entries): ...
    def save_score(self, session_id, expected_version, score, audit): ...
    def create_match(self, world_id, human_hash, agent_hash, apparatus_message, agent_profile, rules): ...
    def read_match(self, match_id): ...
    def daily_world(self, day, factory): ...
    def reserve_call(self, session_id, expected_version, max_calls): ...
    def finish_call(self, session_id, call_index, outcome, audit): ...


def _json(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


class SQLiteRepository:
    """Eventi append-only e CAS su seq; sostituibile dietro gli stessi metodi."""

    def __init__(self, path, worlds=()):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            from .migrations import migrate_connection
            migrate_connection(db)
            for record in worlds:
                validate_local_world(record)
                from .integrity_store import IntegrityCatalog
                IntegrityCatalog(self).check_registration(db, record)
                world_id = record["world_id"]
                old = db.execute("SELECT record_json FROM worlds WHERE id=?", (world_id,)).fetchone()
                if old is not None and json.loads(old[0]) != record:
                    raise ValidationError("ID mondo già presente con contenuto diverso.")
                if old is None:
                    db.execute("INSERT INTO worlds(id,record_json,manifest_json) VALUES(?,?,?)",
                               (world_id, _json(record), _json(local_manifest(record))))

    def register_world(self, record):
        manifest = local_manifest(record)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            from .integrity_store import IntegrityCatalog
            IntegrityCatalog(self).check_registration(db, record)
            old = db.execute("SELECT record_json FROM worlds WHERE id=?", (record["world_id"],)).fetchone()
            if old is not None and json.loads(old[0]) != record:
                raise ConflictError()
            db.execute("INSERT OR IGNORE INTO worlds VALUES(?,?,?)",
                       (record["world_id"], _json(record), _json(manifest)))
        return manifest

    def read_world(self, world_id):
        with self._connect() as db:
            row = db.execute("SELECT record_json FROM worlds WHERE id=?", (world_id,)).fetchone()
            if row is None:
                raise NotFoundError()
            return json.loads(row[0])

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
            from .integrity_store import IntegrityCatalog
            catalog = IntegrityCatalog(self)
            return [catalog.public_world(db, json.loads(row[0])) for row in db.execute(
                "SELECT manifest_json FROM worlds ORDER BY id").fetchall()]

    def _insert_session(self, db, world_id, agent_token_hash, apparatus_message, profile):
        from .integrity_store import IntegrityCatalog
        IntegrityCatalog(self).session_admission(db, world_id, profile)
        session_id = secrets.token_hex(16)
        if db.execute("SELECT 1 FROM worlds WHERE id=?", (world_id,)).fetchone() is None:
            raise NotFoundError()
        db.execute("INSERT INTO sessions(id,world_id,agent_token_hash) VALUES(?,?,?)",
                   (session_id, world_id, agent_token_hash))
        db.execute("INSERT INTO events(session_id,seq,actor,message_json) VALUES(?,?,?,?)",
                   (session_id, 1, "apparatus", _json(apparatus_message)))
        db.execute("INSERT INTO session_profiles VALUES(?,?)", (session_id, _json(profile)))
        return session_id

    def create_session(self, world_id, agent_token_hash, apparatus_message, profile=None):
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            return self._insert_session(db, world_id, agent_token_hash, apparatus_message,
                                        profile or {"mode": "scientist", "managed_agent": False})

    def create_match(self, world_id, human_hash, agent_hash, apparatus_message, agent_profile, rules):
        match_id = secrets.token_hex(16)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            human_id = self._insert_session(db, world_id, human_hash, apparatus_message,
                {"mode": "human_vs_ai", "participant": "human", "managed_agent": False,
                 "match_id": match_id})
            agent_id = self._insert_session(db, world_id, agent_hash, apparatus_message,
                {**agent_profile, "mode": "human_vs_ai", "participant": "agent", "match_id": match_id})
            db.execute("INSERT INTO matches VALUES(?,?,?,?)", (match_id, human_id, agent_id, _json(rules)))
        return {"match_id": match_id, "human_session_id": human_id, "agent_session_id": agent_id, "rules": rules}

    def read_match(self, match_id):
        with self._connect() as db:
            row = db.execute("SELECT human_id,agent_id,rules_json FROM matches WHERE id=?", (match_id,)).fetchone()
            if row is None:
                raise NotFoundError()
            return {"match_id": match_id, "human_session_id": row[0], "agent_session_id": row[1],
                    "rules": json.loads(row[2])}

    def daily_world(self, day, factory):
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT w.manifest_json FROM daily_worlds d JOIN worlds w ON w.id=d.world_id WHERE d.day=?", (day,)).fetchone()
            if row:
                return json.loads(row[0])
            record = factory()
            manifest = local_manifest(record)
            from .integrity_store import IntegrityCatalog
            catalog = IntegrityCatalog(self)
            catalog.check_registration(db, record)
            catalog.session_admission(db, record["world_id"], {"mode": "daily"})
            db.execute("INSERT OR IGNORE INTO worlds VALUES(?,?,?)", (record["world_id"], _json(record), _json(manifest)))
            db.execute("INSERT INTO daily_worlds VALUES(?,?)", (day, record["world_id"]))
            return manifest

    def read_session(self, session_id):
        with self._connect() as db:
            db.execute("BEGIN")
            return self._read_session(db, session_id)

    def _read_session(self, db, session_id):
        row = db.execute("SELECT s.world_id,s.agent_token_hash,s.score_json,s.audit_json,w.record_json "
            "FROM sessions s JOIN worlds w ON s.world_id=w.id WHERE s.id=?", (session_id,)).fetchone()
        if row is None:
            raise NotFoundError()
        events = [{"seq": seq, "actor": actor, "message": json.loads(message)}
                  for seq, actor, message in db.execute(
                      "SELECT seq,actor,message_json FROM events WHERE session_id=? ORDER BY seq",
                      (session_id,))]
        profile = db.execute("SELECT profile_json FROM session_profiles WHERE session_id=?", (session_id,)).fetchone()
        calls = [{"call_index": i, "outcome": outcome, **json.loads(audit)} for i, outcome, audit in
                 db.execute("SELECT call_index,outcome,audit_json FROM agent_calls WHERE session_id=? ORDER BY call_index", (session_id,))]
        return {"id": session_id, "world_id": row[0], "agent_token_hash": row[1],
                "score": json.loads(row[2]) if row[2] is not None else None,
                "audit": json.loads(row[3]) if row[3] is not None else None,
                "record": json.loads(row[4]), "events": events,
                "profile": json.loads(profile[0]) if profile else {"mode": "scientist", "managed_agent": False},
                "calls": calls}

    def reserve_call(self, session_id, expected_version, max_calls):
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            version = db.execute("SELECT COALESCE(MAX(seq),0) FROM events WHERE session_id=?", (session_id,)).fetchone()[0]
            count = db.execute("SELECT COUNT(*) FROM agent_calls WHERE session_id=?", (session_id,)).fetchone()[0]
            if version != expected_version:
                raise ConflictError()
            if count >= max_calls:
                raise ValidationError("Budget chiamate agente esaurito.")
            db.execute("INSERT INTO agent_calls VALUES(?,?,?,?)", (session_id, count + 1, "started", "{}"))
            return count + 1

    def finish_call(self, session_id, call_index, outcome, audit):
        with self._connect() as db:
            db.execute("UPDATE agent_calls SET outcome=?,audit_json=? WHERE session_id=? AND call_index=?",
                       (outcome, _json(audit), session_id, call_index))

    def append(self, session_id, expected_version, entries):
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            return self._append(db, session_id, expected_version, entries)

    def _append(self, db, session_id, expected_version, entries):
        if db.execute("SELECT 1 FROM sessions WHERE id=?", (session_id,)).fetchone() is None:
            raise NotFoundError()
        version = db.execute("SELECT COALESCE(MAX(seq),0) FROM events WHERE session_id=?",
                             (session_id,)).fetchone()[0]
        if version != expected_version:
            raise ConflictError()
        if any(message["type"] == "reveal_recorded" for _actor, message in entries):
            from .integrity_store import IntegrityCatalog
            catalog = IntegrityCatalog(self)
            wid = db.execute("SELECT world_id FROM sessions WHERE id=?", (session_id,)).fetchone()[0]
            catalog.authorize_reveal(db, wid)
            catalog.retire(db, wid)
        for actor, message in entries:
            version += 1
            db.execute("INSERT INTO events(session_id,seq,actor,message_json) VALUES(?,?,?,?)",
                       (session_id, version, actor, _json(message)))
        return version

    def save_score(self, session_id, expected_version, score, audit):
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            return self._save_score(db, session_id, expected_version, score, audit)

    def _save_score(self, db, session_id, expected_version, score, audit):
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
