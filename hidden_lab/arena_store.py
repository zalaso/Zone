"""Persistenza Arena condivisa tra processi: quote, credenziali, receipt e audit."""

from hashlib import sha256
import hmac
import json
import re
import secrets
import time

from fastapi import HTTPException

from .backend_store import ConflictError, NotFoundError, _json
from .protocol import ValidationError


def fingerprint(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                             separators=(",", ":")).encode()).hexdigest()


class ArenaStore:
    def __init__(self, repository, operator_token, clock=None):
        self.repo, self.operator_token = repository, operator_token
        self.clock = clock or time.time
        with repository._connect() as db:
            from .migrations import migrate_connection
            migrate_connection(db)

    def authenticate(self, db, supplied, operator=False):
        if not isinstance(supplied, str) or len(supplied) > 256:
            raise HTTPException(401, "Credenziale Arena non valida.")
        if hmac.compare_digest(supplied.encode(), self.operator_token.encode()):
            return "operator"
        if not operator:
            row = db.execute("SELECT agent_id FROM arena_tokens WHERE hash=? AND revoked=0 AND expires>?",
                             (sha256(supplied.encode()).hexdigest(), self.clock())).fetchone()
            if row:
                return row[0]
        raise HTTPException(401, "Credenziale Arena scaduta, revocata o non valida.")

    def agent(self, db, aid):
        row = db.execute("SELECT metadata_json,quotas_json,sessions,requests,experiments,invalid "
                         "FROM arena_agents WHERE id=?", (aid,)).fetchone()
        if row is None:
            raise NotFoundError()
        return {"agent_id": aid, **json.loads(row[0]), "quotas": json.loads(row[1]),
                "usage": dict(zip(("sessions", "requests", "experiments", "invalid"), row[2:]))}

    def charge(self, db, aid, resource):
        # Column names are selected internally, never interpolated from HTTP input.
        if resource not in ("sessions", "requests", "experiments"):
            raise ValueError("Unknown quota")
        agent = self.agent(db, aid)
        if agent["usage"][resource] >= agent["quotas"][resource]:
            raise HTTPException(429, "Quota Arena esaurita: " + resource)
        db.execute(f"UPDATE arena_agents SET {resource}={resource}+1 WHERE id=?", (aid,))

    def issue(self, db, aid, ttl):
        self.agent(db, aid)
        tid = secrets.token_hex(16)
        token = "za_" + secrets.token_urlsafe(32)
        expires = self.clock() + ttl
        db.execute("INSERT INTO arena_tokens VALUES(?,?,?,?,0)",
                   (tid, aid, sha256(token.encode()).hexdigest(), expires))
        return {"agent_id": aid, "token_id": tid, "expires_at": expires, "token": token}

    def read(self, supplied, callback, *, operator=False):
        with self.repo._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            principal = self.authenticate(db, supplied, operator)
            self.admit(db, principal, "reads")
            db.commit()  # Invalid resource lookups must still consume rate admission.
            db.execute("BEGIN")
            principal = self.authenticate(db, supplied, operator)
            return callback(db, principal)

    def admit(self, db, principal, bucket):
        if principal == "operator":
            return
        if bucket not in ("reads", "writes"):
            raise ValueError("Unknown rate bucket")
        now = self.clock()
        row = db.execute("SELECT window,reads,writes FROM arena_rates WHERE agent_id=?", (principal,)).fetchone()
        if row is None or now - row[0] >= 60:
            db.execute("INSERT OR REPLACE INTO arena_rates VALUES(?,?,0,0)", (principal, now))
            row = (now, 0, 0)
        count = row[1 if bucket == "reads" else 2]
        if count >= (120 if bucket == "reads" else 30):
            raise HTTPException(429, "Limite persistente Arena per account raggiunto.")
        db.execute(f"UPDATE arena_rates SET {bucket}={bucket}+1 WHERE agent_id=?", (principal,))

    def perform(self, supplied, key, path, body, callback, *, operator=False):
        if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{8,128}", key):
            raise HTTPException(400, "Idempotency-Key obbligatorio e non valido.")
        key_hash, body_hash = sha256(key.encode()).hexdigest(), fingerprint(body)
        transient = None
        with self.repo._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            principal = self.authenticate(db, supplied, operator)
            self.admit(db, principal, "writes")
            db.commit()
            db.execute("BEGIN IMMEDIATE")
            principal = self.authenticate(db, supplied, operator)
            row = db.execute("SELECT path,body_hash,status,response_json FROM arena_receipts "
                             "WHERE principal=? AND key_hash=?", (principal, key_hash)).fetchone()
            if row:
                if row[:2] != (path, body_hash):
                    raise HTTPException(409, "Chiave idempotente già usata per una richiesta diversa.")
                return row[2], json.loads(row[3]), None, (principal, key_hash)
            if principal != "operator":
                if self.agent(db, principal)["usage"]["invalid"] >= 20:
                    raise HTTPException(429, "Troppe risposte invalide; l'operatore deve revocare il token.")
                self.charge(db, principal, "requests")
            db.execute("SAVEPOINT action")
            try:
                status, result, transient = callback(db, principal)
            except (ValidationError, ConflictError, NotFoundError, HTTPException) as exc:
                db.execute("ROLLBACK TO action")
                status = (exc.status_code if isinstance(exc, HTTPException) else
                          422 if isinstance(exc, ValidationError) else 409 if isinstance(exc, ConflictError) else 404)
                # Never return arbitrary exception text or request bodies.
                result = {"detail": exc.detail if isinstance(exc, HTTPException) else
                          str(exc) if isinstance(exc, ValidationError) else
                          "Versione obsoleta o risorsa non disponibile."}
                transient = None
                if principal != "operator":
                    db.execute("UPDATE arena_agents SET invalid=invalid+1 WHERE id=?", (principal,))
            db.execute("RELEASE action")
            saved = {**result, "token": None} if "token" in result else result
            db.execute("INSERT INTO arena_receipts VALUES(?,?,?,?,?,?)",
                       (principal, key_hash, path, body_hash, status, _json(saved)))
            db.execute("INSERT INTO arena_audit(time,principal,action,status,key_hash) VALUES(?,?,?,?,?)",
                       (self.clock(), principal, path, status, key_hash))
        return status, result, transient, (principal, key_hash)

    def complete(self, receipt, callback):
        """Seconda transazione: mai riavviare lavoro già prenotato dal receipt 202."""
        with self.repo._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("SAVEPOINT completion")
            try:
                result = callback(db)
                status = 200
            except ConflictError:
                db.execute("ROLLBACK TO completion")
                result, status = {"detail": "Operazione interrotta; leggere lo stato prima di proseguire."}, 409
            db.execute("RELEASE completion")
            db.execute("UPDATE arena_receipts SET status=?,response_json=? WHERE principal=? AND key_hash=?",
                       (status, _json(result), *receipt))
            db.execute("INSERT INTO arena_audit(time,principal,action,status,key_hash) VALUES(?,?,?,?,?)",
                       (self.clock(), receipt[0], "completion", status, receipt[1]))
        return status, result

    def interrupted(self, receipt):
        with self.repo._connect() as db:
            db.execute("INSERT INTO arena_audit(time,principal,action,status,key_hash) VALUES(?,?,?,?,?)",
                       (self.clock(), receipt[0], "interrupted", 503, receipt[1]))

    def world_open(self, world_id):
        with self.repo._connect() as db:
            return db.execute("SELECT 1 FROM arena_challenges WHERE world_id=? AND closed=0", (world_id,)).fetchone() is not None
