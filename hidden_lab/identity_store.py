"""Invited identities, opaque credentials and quotas. No passwords or provider secrets."""

from contextlib import contextmanager
from contextvars import ContextVar
from hashlib import sha256
import json
import re
import secrets
import time

from fastapi import HTTPException

from .backend_store import ConflictError, NotFoundError
from .protocol import ValidationError, require_keys

CURRENT_ACCOUNT = ContextVar('zone_account', default=None)
ROLES = ('admin', 'operator', 'member')
DEFAULT_QUOTAS = {'sessions': 30, 'experiments': 100, 'model_calls': 50,
                  'read': 120, 'write': 30, 'run': 10}
SESSION_TTL = 8 * 3600
IDLE_TTL = 1800


def hashed(value):
    return sha256(value.encode('utf-8')).hexdigest()


def limits(value):
    require_keys(value, DEFAULT_QUOTAS)
    if any(type(n) is not int or not 0 <= n <= 1000000 for n in value.values()):
        raise ValidationError('Quote account non valide.')
    return dict(value)


def lifetime(value):
    if type(value) is not int or not 60 <= value <= 2592000:
        raise ValidationError('Durata chiave richiesta fra 60 e 2592000 secondi.')
    return value


@contextmanager
def account_scope(account):
    marker = CURRENT_ACCOUNT.set(account)
    try:
        yield
    finally:
        CURRENT_ACCOUNT.reset(marker)


def account_view(db, account_id):
    row = db.execute('SELECT id,handle,role,enabled,key_expires,quotas_json,sessions,experiments,model_calls '
                     'FROM accounts WHERE id=?', (account_id,)).fetchone()
    if row is None:
        raise NotFoundError()
    return {'account_id': row[0], 'handle': row[1], 'role': row[2], 'enabled': bool(row[3]),
            'key_expires_at': row[4], 'quotas': json.loads(row[5]),
            'usage': dict(zip(('sessions', 'experiments', 'model_calls'), row[6:]))}


def charge(db, account_id, resource):
    if resource not in ('sessions', 'experiments', 'model_calls'):
        raise ValueError('Unknown account resource')
    account = account_view(db, account_id)
    if not account['enabled']:
        raise HTTPException(401, 'Account disabilitato.')
    if account['usage'][resource] >= account['quotas'][resource]:
        raise HTTPException(429, 'Quota account esaurita: ' + resource)
    db.execute(f'UPDATE accounts SET {resource}={resource}+1 WHERE id=?', (account_id,))


def charge_session(db, session_id, resource):
    row = db.execute('SELECT account_id FROM session_owners WHERE session_id=?', (session_id,)).fetchone()
    if row:
        charge(db, row[0], resource)
    elif CURRENT_ACCOUNT.get() is not None:
        charge(db, CURRENT_ACCOUNT.get()['account_id'], resource)


class IdentityStore:
    def __init__(self, repository, clock=None):
        self.repo = repository
        self.clock = clock or time.time

    def audit(self, db, actor, action, target):
        db.execute('INSERT INTO account_audit(time,actor,action,target) VALUES(?,?,?,?)',
                   (self.clock(), actor, action, target))

    def create(self, handle, role='member', quotas=None, ttl=2592000, *, bootstrap=False, actor=None):
        if not isinstance(handle, str) or not re.fullmatch(r'[a-z][a-z0-9_-]{2,47}', handle):
            raise ValidationError('Nome account: 3–48 caratteri minuscoli, numeri, _ e -; iniziale alfabetica.')
        if role not in ROLES:
            raise ValidationError('Ruolo account non valido.')
        quota = limits(DEFAULT_QUOTAS if quotas is None else quotas)
        expires = self.clock() + lifetime(ttl)
        key, aid = 'zk_' + secrets.token_urlsafe(32), secrets.token_hex(16)
        with self.repo._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if bootstrap:
                if db.execute('SELECT 1 FROM accounts').fetchone():
                    raise ValidationError('Bootstrap già completato; usa un amministratore esistente.')
                if role != 'admin':
                    raise ValidationError('Il bootstrap deve creare un amministratore.')
            elif actor is None or account_view(db, actor)['role'] != 'admin' or not account_view(db, actor)['enabled']:
                raise HTTPException(403, 'Serve un amministratore.')
            if db.execute('SELECT 1 FROM accounts WHERE handle=?', (handle,)).fetchone():
                raise ConflictError()
            db.execute('INSERT INTO accounts(id,handle,role,key_hash,key_expires,quotas_json) VALUES(?,?,?,?,?,?)',
                       (aid, handle, role, hashed(key), expires, json.dumps(quota)))
            self.audit(db, actor or aid, 'bootstrap' if bootstrap else 'create', aid)
            return {**account_view(db, aid), 'login_key': key}

    def authenticate(self, supplied, *, cookie=False):
        if not isinstance(supplied, str) or not 32 <= len(supplied) <= 128:
            raise HTTPException(401, 'Accesso mancante, scaduto o revocato.')
        now = self.clock()
        with self.repo._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if cookie:
                row = db.execute('SELECT s.account_id FROM account_sessions s JOIN accounts a ON a.id=s.account_id '
                    'WHERE s.hash=? AND s.expires>? AND s.last_seen>? AND a.enabled=1 AND a.key_expires>?',
                    (hashed(supplied), now, now - IDLE_TTL, now)).fetchone()
            else:
                row = db.execute('SELECT id FROM accounts WHERE key_hash=? AND enabled=1 AND key_expires>?',
                                 (hashed(supplied), now)).fetchone()
            if not row:
                raise HTTPException(401, 'Accesso mancante, scaduto o revocato.')
            if cookie:
                db.execute('UPDATE account_sessions SET last_seen=? WHERE hash=?', (now, hashed(supplied)))
            return account_view(db, row[0])

    def login(self, key):
        account = self.authenticate(key)
        sid = secrets.token_urlsafe(32)
        now = self.clock()
        with self.repo._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            # Recheck while locked: a concurrent disable/rotation must not issue a session.
            if not db.execute('SELECT 1 FROM accounts WHERE id=? AND key_hash=? AND enabled=1 AND key_expires>?',
                              (account['account_id'], hashed(key), now)).fetchone():
                raise HTTPException(401, 'Accesso mancante, scaduto o revocato.')
            db.execute('DELETE FROM account_sessions WHERE expires<=? OR last_seen<=?', (now, now - IDLE_TTL))
            db.execute('DELETE FROM account_sessions WHERE hash IN (SELECT hash FROM account_sessions '
                       'WHERE account_id=? ORDER BY last_seen DESC LIMIT -1 OFFSET 7)', (account['account_id'],))
            db.execute('INSERT INTO account_sessions VALUES(?,?,?,?)', (hashed(sid), account['account_id'], now + SESSION_TTL, now))
            self.audit(db, account['account_id'], 'login', account['account_id'])
        return account, sid

    def update(self, actor, account_id, body):
        require_keys(body, ('role', 'enabled', 'quotas'))
        if body['role'] not in ROLES or type(body['enabled']) is not bool:
            raise ValidationError('Ruolo o stato account non valido.')
        quota = limits(body['quotas'])
        with self.repo._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            actor_account = account_view(db, actor)
            if actor_account['role'] != 'admin' or not actor_account['enabled']:
                raise HTTPException(403, 'Serve un amministratore.')
            old = account_view(db, account_id)
            if old['role'] == 'admin' and old['enabled'] and (body['role'] != 'admin' or not body['enabled']):
                if db.execute("SELECT COUNT(*) FROM accounts WHERE role='admin' AND enabled=1 AND key_expires>?",
                              (self.clock(),)).fetchone()[0] <= 1:
                    raise ValidationError('Non puoi rimuovere l’ultimo amministratore attivo.')
            db.execute('UPDATE accounts SET role=?,enabled=?,quotas_json=? WHERE id=?',
                       (body['role'], int(body['enabled']), json.dumps(quota), account_id))
            db.execute('DELETE FROM account_sessions WHERE account_id=?', (account_id,))
            self.audit(db, actor, 'update', account_id)
            return account_view(db, account_id)

    def rotate(self, actor, account_id, ttl):
        expires = self.clock() + lifetime(ttl)
        key = 'zk_' + secrets.token_urlsafe(32)
        with self.repo._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            admin = account_view(db, actor)
            if admin['role'] != 'admin' or not admin['enabled']:
                raise HTTPException(403, 'Serve un amministratore.')
            account_view(db, account_id)
            db.execute('UPDATE accounts SET key_hash=?,key_expires=? WHERE id=?', (hashed(key), expires, account_id))
            db.execute('DELETE FROM account_sessions WHERE account_id=?', (account_id,))
            self.audit(db, actor, 'rotate', account_id)
            return {**account_view(db, account_id), 'login_key': key}

    def recover_admin(self, handle, ttl=2592000):
        """Local filesystem authority only. Deliberately not exposed over HTTP."""
        expires, key = self.clock() + lifetime(ttl), 'zk_' + secrets.token_urlsafe(32)
        with self.repo._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute("SELECT id FROM accounts WHERE handle=? AND role='admin'", (handle,)).fetchone()
            if not row:
                raise ValidationError('Amministratore esistente richiesto per il recupero locale.')
            db.execute('UPDATE accounts SET key_hash=?,key_expires=?,enabled=1 WHERE id=?', (hashed(key), expires, row[0]))
            db.execute('DELETE FROM account_sessions WHERE account_id=?', (row[0],))
            self.audit(db, 'local_recovery', 'recover_admin', row[0])
            return {**account_view(db, row[0]), 'login_key': key}

    def admit(self, principal, bucket, limit):
        now = self.clock()
        with self.repo._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT window,count FROM account_rates WHERE principal=? AND bucket=?', (principal, bucket)).fetchone()
            if row is None or now - row[0] >= 60:
                db.execute('INSERT OR REPLACE INTO account_rates VALUES(?,?,?,0)', (principal, bucket, now))
                count = 0
            else:
                count = row[1]
            if count >= limit:
                raise HTTPException(429, 'Limite persistente di richieste raggiunto.')
            db.execute('UPDATE account_rates SET count=count+1 WHERE principal=? AND bucket=?', (principal, bucket))
            # Bound failed-login IP records as well as expired account windows.
            db.execute('DELETE FROM account_rates WHERE window<?', (now - 3600,))

    def owns_session(self, account, session_id):
        with self.repo._connect() as db:
            row = db.execute('SELECT account_id FROM session_owners WHERE session_id=?', (session_id,)).fetchone()
        if account['role'] not in ('admin', 'operator') and (not row or row[0] != account['account_id']):
            raise NotFoundError()

    def bind_agent(self, actor, account_id, agent_id):
        with self.repo._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            admin = account_view(db, actor)
            if admin['role'] != 'admin' or not admin['enabled']:
                raise HTTPException(403, 'Serve un amministratore.')
            account_view(db, account_id)
            if not db.execute('SELECT 1 FROM arena_agents WHERE id=?', (agent_id,)).fetchone():
                raise NotFoundError()
            if db.execute('SELECT 1 FROM arena_owners WHERE agent_id=?', (agent_id,)).fetchone():
                raise ConflictError()
            if db.execute('SELECT 1 FROM arena_trials WHERE agent_id=?', (agent_id,)).fetchone():
                raise ValidationError('Assegna l’agente prima di avviare trial.')
            db.execute('INSERT INTO arena_owners VALUES(?,?)', (agent_id, account_id))
            self.audit(db, actor, 'bind_arena', agent_id)
