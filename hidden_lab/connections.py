"""Personal AI connections, encrypted BYOK and outbound local-connector jobs.

No user-supplied network endpoint is accepted by the server. Connector credentials
authorize only polling and replying for a single connection, never experiments.
"""

import base64
from dataclasses import asdict
import json
import secrets
import time

from fastapi import HTTPException, Request

from .agent_contract import ModelRequest
from .backend_store import ConflictError, NotFoundError
from .identity_store import account_view, hashed
from .protocol import ValidationError, require_keys
from .provider_base import AgentSettings, ModelReply, ProviderError
from .web_agent import safe_metadata

API_PROVIDERS = ('openai', 'anthropic', 'gemini')
LOCAL_PROVIDERS = ('chatgpt', 'ollama')


class Connections:
    def __init__(self, repository, vault_key=None, *, client_factory=None, clock=None):
        self.repo = repository
        self.clock = clock or time.time
        self.factory = client_factory
        self.cipher = None
        if vault_key is not None:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            try:
                key = base64.urlsafe_b64decode(vault_key)
                if len(key) != 32:
                    raise ValueError()
                self.cipher = AESGCM(key)
            except Exception:
                raise ValueError('ZONE_CONNECTION_KEY richiede 32 byte codificati base64url.') from None

    def list(self, owner):
        with self.repo._connect() as db:
            rows = db.execute('SELECT id,label,provider,model,transport,enabled,last_seen,created FROM ai_connections '
                              'WHERE account_id=? ORDER BY created', (owner,)).fetchall()
            selected = db.execute('SELECT connection_id FROM ai_preferences WHERE account_id=?', (owner,)).fetchone()
        return {'connections': [dict(zip(('id', 'label', 'provider', 'model', 'transport', 'enabled', 'last_seen', 'created'), r))
                                for r in rows], 'selected': selected[0] if selected else None,
                'api_enabled': self.cipher is not None, 'hosted_chatgpt_plan': False}

    def read(self, owner, cid):
        if not isinstance(cid, str) or len(cid) != 32:
            raise ValidationError('ID connessione non valido.')
        with self.repo._connect() as db:
            row = db.execute('SELECT provider,model,transport,secret,enabled,last_seen FROM ai_connections '
                             'WHERE id=? AND account_id=?', (cid, owner)).fetchone()
        if row is None:
            raise NotFoundError()
        if not row[4]:
            raise HTTPException(409, 'Connessione disconnessa; nessun fallback. Crea una nuova sessione con un’altra AI.')
        return dict(zip(('provider', 'model', 'transport', 'secret', 'enabled', 'last_seen'), row))

    def create(self, owner, body):
        require_keys(body, ('label', 'provider', 'model', 'transport'), ('api_key',))
        provider, transport = body['provider'], body['transport']
        if (transport == 'api' and provider not in API_PROVIDERS or
                transport == 'connector' and provider not in (*API_PROVIDERS, *LOCAL_PROVIDERS) or
                transport not in ('api', 'connector')):
            raise ValidationError('Scegli API personale o connettore locale compatibile.')
        if not isinstance(body['label'], str) or not 1 <= len(body['label'].strip()) <= 80:
            raise ValidationError('Nome connessione: 1–80 caratteri.')
        AgentSettings(body['model'])
        if provider == 'ollama' and body['model'].endswith(':cloud'):
            raise ValidationError('Scegli un modello Ollama locale.')
        cid, connector_key, secret = secrets.token_hex(16), None, None
        if transport == 'api':
            if self.cipher is None:
                raise HTTPException(503, 'Archivio API non configurato dal gestore. Usa il connettore locale.')
            key = body.get('api_key')
            if not isinstance(key, str) or not 8 <= len(key) <= 4096 or any(c.isspace() for c in key):
                raise ValidationError('Chiave API non valida.')
            nonce = secrets.token_bytes(12)
            secret = nonce + self.cipher.encrypt(nonce, key.encode(), self.aad(owner, cid, provider, body['model']))
        else:
            if 'api_key' in body:
                raise ValidationError('Il connettore conserva la credenziale sul computer, non sul sito.')
            connector_key = 'zc_' + secrets.token_urlsafe(32)
        with self.repo._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT COUNT(*) FROM ai_connections WHERE account_id=? AND enabled=1', (owner,)).fetchone()[0] >= 10:
                raise HTTPException(429, 'Massimo dieci connessioni attive.')
            db.execute('INSERT INTO ai_connections(id,account_id,label,provider,model,transport,secret,connector_hash,created) '
                       'VALUES(?,?,?,?,?,?,?,?,?)', (cid, owner, body['label'].strip(), provider, body['model'], transport,
                                                  secret, hashed(connector_key) if connector_key else None, self.clock()))
            db.execute('INSERT OR REPLACE INTO ai_preferences VALUES(?,?)', (owner, cid))
        return {'id': cid, 'connector_key': connector_key, 'inferences': 0}

    @staticmethod
    def aad(owner, cid, provider, model):
        return json.dumps([owner, cid, provider, model]).encode()

    def select(self, owner, cid):
        if cid is not None:
            self.read(owner, cid)
        with self.repo._connect() as db:
            db.execute('INSERT OR REPLACE INTO ai_preferences VALUES(?,?)', (owner, cid))

    def revoke(self, owner, cid):
        # Idempotent removal, also clears jobs so a late worker cannot commit a reply.
        with self.repo._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if not db.execute('SELECT 1 FROM ai_connections WHERE id=? AND account_id=?', (cid, owner)).fetchone():
                raise NotFoundError()
            db.execute('UPDATE ai_connections SET enabled=0,secret=NULL,connector_hash=NULL WHERE id=?', (cid,))
            db.execute('UPDATE ai_preferences SET connection_id=NULL WHERE account_id=? AND connection_id=?', (owner, cid))
            db.execute("UPDATE connector_jobs SET status='cancelled',request_json=NULL,reply_json=NULL WHERE connection_id=?", (cid,))

    def configured(self, owner, cid=None):
        if cid is None:
            with self.repo._connect() as db:
                row = db.execute('SELECT connection_id FROM ai_preferences WHERE account_id=?', (owner,)).fetchone()
            cid = row[0] if row else None
        if not cid:
            return None
        row = self.read(owner, cid)
        settings = AgentSettings(row['model'], max_calls=8, max_turns=8, max_corrections=1, max_points=3, timeout=110)
        return ConnectionClient(self, owner, cid, row, settings), settings

    def authenticate_connector(self, key):
        if not isinstance(key, str) or not key.startswith('zc_') or len(key) > 128:
            raise HTTPException(401, 'Connettore non autorizzato.')
        with self.repo._connect() as db:
            row = db.execute('SELECT id,account_id,created FROM ai_connections WHERE connector_hash=? AND enabled=1',
                             (hashed(key),)).fetchone()
            if row is None or self.clock() - row[2] > 30 * 86400:
                raise HTTPException(401, 'Connettore scaduto o disconnesso.')
            account = account_view(db, row[1])
            if not account['enabled']:
                raise HTTPException(401, 'Account disabilitato.')
        return account, row[0]

    def claim(self, owner, cid):
        self.read(owner, cid)
        now = self.clock()
        with self.repo._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('UPDATE ai_connections SET last_seen=? WHERE id=?', (now, cid))
            db.execute("UPDATE connector_jobs SET status='expired',request_json=NULL,reply_json=NULL WHERE deadline<=?", (now,))
            row = db.execute("SELECT id,deadline,request_json FROM connector_jobs WHERE connection_id=? AND status='pending' ORDER BY rowid LIMIT 1", (cid,)).fetchone()
            if row is None:
                return {'job': None}
            lease = secrets.token_urlsafe(32)
            db.execute("UPDATE connector_jobs SET status='claimed',lease=? WHERE id=?", (lease, row[0]))
        return {'job': {'id': row[0], 'deadline': row[1], 'lease': lease, 'request': json.loads(row[2])}}

    def reply(self, cid, job_id, body):
        require_keys(body, ('lease',), ('text', 'metadata', 'error', 'issue'))
        if not isinstance(body['lease'], str) or len(body['lease']) > 128:
            raise ValidationError('Lease connettore non valido.')
        if 'error' in body:
            if not isinstance(body['error'], str) or len(body['error']) > 64:
                raise ValidationError('Errore connettore non valido.')
            result = {'error': ProviderError(body['error']).code}
        else:
            if not isinstance(body.get('text'), str) or len(body['text'].encode()) > 65536 or not isinstance(body.get('metadata'), dict):
                raise ValidationError('Risposta connettore oltre limite o non valida.')
            issue = body.get('issue')
            if issue not in (None, 'incomplete_response', 'refusal'):
                raise ValidationError('Stato risposta non valido.')
            result = {'text': body['text'], 'metadata': safe_metadata(ModelReply('', body['metadata'])), 'issue': issue}
        encoded = json.dumps(result, allow_nan=False)
        with self.repo._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT status,deadline,lease,reply_json FROM connector_jobs WHERE id=? AND connection_id=?', (job_id, cid)).fetchone()
            if row is None or row[1] <= self.clock() or not secrets.compare_digest(str(row[2]), str(body['lease'])):
                raise ConflictError()
            if row[0] == 'done' and row[3] == encoded:
                return {'accepted': True}
            if row[0] != 'claimed':
                raise ConflictError()
            db.execute("UPDATE connector_jobs SET status='done',reply_json=?,request_json=NULL WHERE id=?", (encoded, job_id))
        return {'accepted': True}

    def dispatch(self, owner, cid, request, timeout):
        row = self.read(owner, cid)
        if row['last_seen'] is None or self.clock() - row['last_seen'] > 15:
            raise ProviderError('service_unavailable')
        job_id, deadline = secrets.token_hex(16), self.clock() + timeout - 2
        with self.repo._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute("SELECT 1 FROM connector_jobs WHERE connection_id=? AND status IN ('pending','claimed') AND deadline>?", (cid, self.clock())).fetchone():
                raise ProviderError('rate_limit')
            db.execute('INSERT INTO connector_jobs VALUES(?,?,?,?,?,?,?)',
                       (job_id, cid, 'pending', deadline, json.dumps(asdict(request), allow_nan=False), None, None))
        try:
            while self.clock() < deadline:
                with self.repo._connect() as db:
                    job = db.execute('SELECT status,reply_json FROM connector_jobs WHERE id=?', (job_id,)).fetchone()
                if job[0] == 'done':
                    data = json.loads(job[1])
                    if 'error' in data:
                        raise ProviderError(data['error'])
                    return ModelReply(data['text'], data['metadata'], data.get('issue'))
                if job[0] in ('cancelled', 'expired'):
                    raise ProviderError('service_unavailable')
                time.sleep(0.1)
            raise ProviderError('timeout')
        finally:
            with self.repo._connect() as db:
                db.execute('DELETE FROM connector_jobs WHERE id=?', (job_id,))


class ConnectionClient:
    sdk_version = None

    def __init__(self, store, owner, cid, row, settings):
        self.store, self.owner, self.connection_id, self.settings = store, owner, cid, settings
        self.provider = row['provider']
        if row['transport'] == 'api':
            from importlib.metadata import PackageNotFoundError, version
            try:
                self.sdk_version = version({'openai': 'openai', 'anthropic': 'anthropic', 'gemini': 'google-genai'}[self.provider])
            except PackageNotFoundError:
                self.sdk_version = None
        self.generation_settings = {'authentication': 'personal_api' if row['transport'] == 'api' else 'local_connector',
                                    'tools': [], 'max_retries': 0, 'timeout_seconds': settings.timeout}

    def complete(self, request):
        if not isinstance(request, ModelRequest) or request.model != self.settings.model:
            raise ProviderError('request_rejected')
        row = self.store.read(self.owner, self.connection_id)
        if row['transport'] == 'connector':
            return self.store.dispatch(self.owner, self.connection_id, request, self.settings.timeout)
        if self.store.cipher is None:
            raise ProviderError('authentication')
        try:
            secret = row['secret']
            key = self.store.cipher.decrypt(secret[:12], secret[12:], self.store.aad(
                self.owner, self.connection_id, row['provider'], row['model'])).decode()
        except Exception:
            raise ProviderError('authentication') from None
        from .provider_factory import create_real_client
        factory = self.store.factory or create_real_client
        client = factory(self.provider, self.settings, api_key=key)
        try:
            return client.complete(request)
        finally:
            client.close()


def install_connections(app, store):
    from .backend import _body

    @app.get('/v1/my/connections')
    async def listing(request: Request):
        return store.list(request.state.account['account_id'])

    @app.post('/v1/my/connections', status_code=201)
    async def create(request: Request):
        return store.create(request.state.account['account_id'], await _body(request))

    @app.post('/v1/my/connections/select')
    async def select(request: Request):
        body = await _body(request)
        require_keys(body, ('connection_id',))
        store.select(request.state.account['account_id'], body['connection_id'])
        return {'selected': body['connection_id']}

    @app.delete('/v1/my/connections/{cid}')
    async def revoke(cid: str, request: Request):
        store.revoke(request.state.account['account_id'], cid)
        return {'disconnected': True}

    @app.post('/v1/connector/poll')
    async def poll(request: Request):
        require_keys(await _body(request), ())
        return store.claim(request.state.account['account_id'], request.state.connection_id)

    @app.post('/v1/connector/jobs/{job_id}')
    async def reply(job_id: str, request: Request):
        return store.reply(request.state.connection_id, job_id, await _body(request))
