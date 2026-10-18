"""Self-service accounts. Passwords and single-use recovery codes never leave this boundary."""

import hashlib
import hmac
import json
import re
import secrets

from fastapi import HTTPException

from .backend_store import ConflictError
from .identity_store import DEFAULT_QUOTAS, account_view, hashed
from .protocol import ValidationError


def password_hash(password, salt):
    if not isinstance(password, str) or not 12 <= len(password) <= 256:
        raise ValidationError('Password: da 12 a 256 caratteri.')
    return hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()


class PublicAccounts:
    def __init__(self, identity, *, max_accounts=1000):
        self.identity = identity
        self.repo = identity.repo
        self.max_accounts = max_accounts

    def register(self, handle, password):
        if not isinstance(handle, str) or not re.fullmatch(r'[a-z][a-z0-9_-]{2,47}', handle):
            raise ValidationError('Nome: 3–48 caratteri minuscoli, numeri, _ e -; iniziale alfabetica.')
        salt, recovery, aid = secrets.token_hex(16), secrets.token_urlsafe(32), secrets.token_hex(16)
        digest = password_hash(password, salt)
        with self.repo._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT COUNT(*) FROM accounts').fetchone()[0] >= self.max_accounts:
                raise HTTPException(503, 'Registrazioni temporaneamente sospese.')
            if db.execute('SELECT 1 FROM accounts WHERE handle=?', (handle,)).fetchone():
                raise ConflictError()
            # An internal opaque key is not returned. Password users authenticate via cookies.
            db.execute('INSERT INTO accounts(id,handle,role,key_hash,key_expires,quotas_json) VALUES(?,?,?,?,?,?)',
                       (aid, handle, 'member', hashed(secrets.token_urlsafe(48)), 1e12, json.dumps(DEFAULT_QUOTAS)))
            db.execute('INSERT INTO account_passwords VALUES(?,?,?,?)', (aid, salt, digest, hashed(recovery)))
            self.identity.audit(db, aid, 'self_register', aid)
            return account_view(db, aid), recovery

    def authenticate(self, handle, password):
        if not isinstance(handle, str) or len(handle) > 48:
            raise HTTPException(401, 'Nome o password non validi.')
        with self.repo._connect() as db:
            row = db.execute('SELECT a.id,p.salt,p.password_hash FROM accounts a JOIN account_passwords p '
                             'ON p.account_id=a.id WHERE a.handle=? AND a.enabled=1', (handle,)).fetchone()
            salt = row[1] if row else '00' * 16
            digest = password_hash(password, salt)
            if not hmac.compare_digest(digest, row[2] if row else '00' * 64):
                raise HTTPException(401, 'Nome o password non validi.')
            return account_view(db, row[0])

    def recover(self, handle, code, password):
        if not isinstance(handle, str) or len(handle) > 48 or not isinstance(code, str) or not 32 <= len(code) <= 128:
            raise HTTPException(401, 'Recupero non valido.')
        salt, replacement = secrets.token_hex(16), secrets.token_urlsafe(32)
        digest = password_hash(password, salt)
        with self.repo._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT a.id,p.recovery_hash FROM accounts a JOIN account_passwords p '
                             'ON p.account_id=a.id WHERE a.handle=? AND a.enabled=1', (handle,)).fetchone()
            if row is None or not hmac.compare_digest(hashed(code), row[1]):
                raise HTTPException(401, 'Recupero non valido.')
            db.execute('UPDATE account_passwords SET salt=?,password_hash=?,recovery_hash=? WHERE account_id=?',
                       (salt, digest, hashed(replacement), row[0]))
            db.execute('DELETE FROM account_sessions WHERE account_id=?', (row[0],))
            db.execute('UPDATE ai_connections SET enabled=0,secret=NULL,connector_hash=NULL WHERE account_id=?', (row[0],))
            db.execute('UPDATE ai_preferences SET connection_id=NULL WHERE account_id=?', (row[0],))
            db.execute("UPDATE connector_jobs SET status='cancelled',request_json=NULL,reply_json=NULL WHERE connection_id IN "
                       '(SELECT id FROM ai_connections WHERE account_id=?)', (row[0],))
            self.identity.audit(db, row[0], 'self_recover', row[0])
        return replacement

    def session(self, account):
        from .identity_store import SESSION_TTL
        sid, now = secrets.token_urlsafe(32), self.identity.clock()
        with self.repo._connect() as db:
            db.execute('INSERT INTO account_sessions VALUES(?,?,?,?)',
                       (hashed(sid), account['account_id'], now + SESSION_TTL, now))
        return sid
