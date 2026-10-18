"""Account HTTP boundary: authenticate before resource lookup, fail closed on writes."""

import hmac
import re
from urllib.parse import urlsplit

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from .backend_store import NotFoundError
from .identity_store import (DEFAULT_QUOTAS, SESSION_TTL, IdentityStore, account_scope,
                             account_view, hashed)
from .protocol import ValidationError, require_keys


def authorization_present(request):
    return bool(request.headers.get('authorization') or request.headers.get('cookie'))


def install_identity(app, repository, *, enabled=False, origin=None, secure_cookies=True, clock=None,
                     public_workspace=False, open_registration=False, max_accounts=1000):
    from .backend import _body
    store = IdentityStore(repository, clock)
    app.state.identity = store if enabled else None
    from .public_accounts import PublicAccounts
    public = PublicAccounts(store, max_accounts=max_accounts)
    if enabled:
        parsed = urlsplit(origin or '')
        _ = parsed.port  # Reject malformed ports before starting the server.
        if (parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password
                or parsed.path or parsed.query or parsed.fragment):
            raise ValueError('Imposta una singola origine pubblica senza percorso o credenziali.')
        if parsed.scheme == 'http' and parsed.hostname not in ('127.0.0.1', 'localhost', '::1'):
            raise ValueError('HTTP consentito solo su loopback; per utenti esterni serve HTTPS.')
        if not secure_cookies and (parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1', 'localhost', '::1')):
            raise ValueError('Cookie non Secure consentiti soltanto per HTTP locale esplicito.')
        if parsed.scheme == 'http' and secure_cookies:
            raise ValueError('HTTP locale richiede --local-cookies; fuori dal PC usa HTTPS.')
    cookie_name = '__Host-zone_session' if secure_cookies else 'zone_local_session'

    @app.get('/v1/auth/config')
    async def auth_config():
        return {'mode': 'accounts' if enabled else 'local', **({'public_workspace': True,
                'registration_open': open_registration, 'chatgpt_local_connector': True} if public_workspace else {})}

    if not enabled:
        @app.middleware('http')
        async def prevent_downgrade(request, call_next):
            # Also covers a local process still running when the trusted CLI bootstraps accounts.
            if request.url.path.startswith('/v1/'):
                with repository._connect() as db:
                    if db.execute('SELECT 1 FROM accounts').fetchone():
                        return JSONResponse({'detail': 'Riavvia Zone in modalità accounts.'}, status_code=503)
            return await call_next(request)
        return

    def csrf(sid):
        return hashed('zone-csrf:' + sid)

    @app.middleware('http')
    async def account_boundary(request, call_next):
        if not request.url.path.startswith('/v1/'):
            return await call_next(request)
        account = None
        try:
            if request.url.hostname != parsed.hostname:
                raise HTTPException(400, 'Host non consentito.')
            incoming_origin = request.headers.get('origin')
            if incoming_origin is not None and incoming_origin != origin:
                raise HTTPException(403, 'Origine non consentita.')
            if request.headers.get('sec-fetch-site') == 'cross-site':
                raise HTTPException(403, 'Origine non consentita.')
            path = request.url.path
            if path == '/v1/auth/config':
                return await call_next(request)
            if path in ('/v1/auth/login', '/v1/auth/password', '/v1/auth/register', '/v1/auth/recover') and request.method == 'POST':
                if incoming_origin != origin:
                    raise HTTPException(403, 'Il login richiede l’origine configurata.')
                address = request.client.host if request.client else 'unknown'
                store.admit('ip:' + hashed(address), 'login', 10)
                return await call_next(request)
            if path.startswith('/v1/connector/'):
                if not public_workspace or authorization_present(request):
                    raise HTTPException(401, 'Usa soltanto la credenziale del connettore.')
                account, cid = app.state.connections.authenticate_connector(request.headers.get('x-zone-connector'))
                request.state.account, request.state.connection_id = account, cid
                store.admit('connector:' + cid, 'poll', 120)
                result = await call_next(request)
                result.headers['Cache-Control'] = 'no-store'
                return result
            authorization = request.headers.get('authorization', '')
            sid = request.cookies.get(cookie_name, '')
            if authorization:
                if not authorization.startswith('Bearer ') or sid:
                    raise HTTPException(401, 'Usa una sola credenziale account.')
                account = store.authenticate(authorization[7:])
            else:
                account = store.authenticate(sid, cookie=True)
                if request.method not in ('GET', 'HEAD'):
                    supplied = request.headers.get('x-zone-csrf', '')
                    if incoming_origin != origin or not hmac.compare_digest(supplied.encode(), csrf(sid).encode()):
                        raise HTTPException(403, 'Conferma CSRF mancante o non valida.')
            request.state.account = account
            request.state.csrf = csrf(sid) if sid else None
            bucket = 'run' if path.endswith('/run') and request.method == 'POST' else 'read' if request.method in ('GET', 'HEAD') else 'write'
            if path != '/v1/auth/logout':
                store.admit(account['account_id'], bucket, account['quotas'][bucket])
            if path.startswith('/v1/admin/') and account['role'] != 'admin':
                raise HTTPException(403, 'Serve un amministratore.')
            if path.endswith('/reveal') and account['role'] != 'admin':
                raise HTTPException(403, 'Reveal riservato all’amministratore.')
            if path in ('/v1/worlds/build', '/v1/worlds/generate') and account['role'] != 'admin' and not public_workspace:
                raise HTTPException(403, 'Creazione mondi riservata all’amministratore.')
            parts = path.split('/')
            if len(parts) >= 4 and parts[2] == 'sessions':
                store.owns_session(account, parts[3])
            if len(parts) >= 4 and parts[2] == 'matches':
                match = repository.read_match(parts[3])
                store.owns_session(account, match['human_session_id'])
                store.owns_session(account, match['agent_session_id'])
            if request.method not in ('GET', 'HEAD') and not (
                    path in ('/v1/sessions', '/v1/matches', '/v1/auth/logout') or
                    path.startswith(('/v1/sessions/', '/v1/arena/', '/v1/admin/')) or
                    public_workspace and path.startswith(('/v1/my/connections', '/v1/my/arena')) or
                    path in ('/v1/worlds/build', '/v1/worlds/generate')):
                raise HTTPException(403, 'Operazione non abilitata per gli account.')
            with account_scope(account):
                response = await call_next(request)
            if request.method not in ('GET', 'HEAD'):
                route = request.scope.get('route')
                template = getattr(route, 'path', 'unmatched')
                with repository._connect() as db:
                    store.audit(db, account['account_id'], 'http_' + request.method.lower(), template)
            response.headers['Cache-Control'] = 'no-store'
            return response
        except (HTTPException, NotFoundError) as exc:
            status = exc.status_code if isinstance(exc, HTTPException) else 404
            detail = exc.detail if isinstance(exc, HTTPException) else 'Risorsa non trovata.'
            return JSONResponse({'detail': detail}, status_code=status,
                                headers={'Cache-Control': 'no-store', **({'Retry-After': '60'} if status == 429 else {})})

    @app.post('/v1/auth/login')
    async def login(request: Request):
        body = await _body(request)
        require_keys(body, ('login_key',))
        account, sid = store.login(body['login_key'])
        response = JSONResponse({'account': account, 'csrf': csrf(sid)})
        response.set_cookie(cookie_name, sid, max_age=SESSION_TTL, httponly=True,
                            secure=secure_cookies, samesite='strict', path='/')
        return response

    def signed_in(account, sid, **extra):
        result = JSONResponse({'account': account, 'csrf': csrf(sid), **extra})
        result.set_cookie(cookie_name, sid, max_age=SESSION_TTL, httponly=True,
                          secure=secure_cookies, samesite='strict', path='/')
        result.headers['Cache-Control'] = 'no-store'
        return result

    @app.post('/v1/auth/register')
    async def register(request: Request):
        if not public_workspace or not open_registration:
            raise HTTPException(403, 'Registrazione non ancora aperta. Usa un invito.')
        body = await _body(request)
        require_keys(body, ('handle', 'password'))
        account, recovery = public.register(body['handle'], body['password'])
        return signed_in(account, public.session(account), recovery_code=recovery)

    @app.post('/v1/auth/password')
    async def password_login(request: Request):
        if not public_workspace:
            raise HTTPException(403, 'Accesso con password non abilitato.')
        body = await _body(request)
        require_keys(body, ('handle', 'password'))
        account = public.authenticate(body['handle'], body['password'])
        return signed_in(account, public.session(account))

    @app.post('/v1/auth/recover')
    async def recover(request: Request):
        if not public_workspace:
            raise HTTPException(403, 'Recupero autonomo non abilitato.')
        body = await _body(request)
        require_keys(body, ('handle', 'recovery_code', 'password'))
        replacement = public.recover(body['handle'], body['recovery_code'], body['password'])
        return JSONResponse({'recovery_code': replacement}, headers={'Cache-Control': 'no-store'})

    @app.get('/v1/auth/me')
    async def me(request: Request):
        return {'account': request.state.account, 'csrf': request.state.csrf}

    @app.post('/v1/auth/logout')
    async def logout(request: Request):
        with repository._connect() as db:
            db.execute('DELETE FROM account_sessions WHERE hash=?', (hashed(request.cookies.get(cookie_name, '')),))
            store.audit(db, request.state.account['account_id'], 'logout', request.state.account['account_id'])
        response = JSONResponse({'logged_out': True})
        response.delete_cookie(cookie_name, path='/', secure=secure_cookies, httponly=True, samesite='strict')
        return response

    @app.get('/v1/my/sessions')
    async def my_sessions(request: Request, after: int = 0):
        if type(after) is not int or after < 0:
            raise ValidationError('Cursore non valido.')
        with repository._connect() as db:
            rows = db.execute('SELECT s.rowid,s.id,p.profile_json FROM sessions s JOIN session_owners o ON o.session_id=s.id '
                'JOIN session_profiles p ON p.session_id=s.id WHERE o.account_id=? AND s.rowid>? ORDER BY s.rowid LIMIT 100',
                (request.state.account['account_id'], after)).fetchall()
        import json
        return {'sessions': [{'session_id': row[1], 'mode': json.loads(row[2]).get('mode')} for row in rows],
                'next_after': rows[-1][0] if rows else after}

    @app.get('/v1/admin/accounts')
    async def accounts(after: int = 0):
        if type(after) is not int or after < 0:
            raise ValidationError('Cursore non valido.')
        with repository._connect() as db:
            rows = db.execute('SELECT rowid,id FROM accounts WHERE rowid>? ORDER BY rowid LIMIT 100', (after,)).fetchall()
            return {'accounts': [account_view(db, row[1]) for row in rows], 'next_after': rows[-1][0] if rows else after}

    @app.post('/v1/admin/accounts', status_code=201)
    async def create_account(request: Request):
        body = await _body(request)
        require_keys(body, ('handle', 'role'), ('quotas', 'ttl_seconds'))
        return store.create(body['handle'], body['role'], body.get('quotas', DEFAULT_QUOTAS),
                            body.get('ttl_seconds', 2592000), actor=request.state.account['account_id'])

    @app.post('/v1/admin/accounts/{account_id}')
    async def update_account(account_id: str, request: Request):
        return store.update(request.state.account['account_id'], account_id, await _body(request))

    @app.post('/v1/admin/accounts/{account_id}/rotate')
    async def rotate_key(account_id: str, request: Request):
        body = await _body(request)
        require_keys(body, ('ttl_seconds',))
        return store.rotate(request.state.account['account_id'], account_id, body['ttl_seconds'])

    @app.post('/v1/admin/accounts/{account_id}/arena/{agent_id}')
    async def bind_agent(account_id: str, agent_id: str, request: Request):
        require_keys(await _body(request), ())
        store.bind_agent(request.state.account['account_id'], account_id, agent_id)
        return {'account_id': account_id, 'agent_id': agent_id}

    @app.post('/v1/admin/sessions/{session_id}/assign')
    async def assign(session_id: str, request: Request):
        body = await _body(request)
        require_keys(body, ('account_id',))
        if not isinstance(body['account_id'], str) or not re.fullmatch(r'[0-9a-f]{32}', body['account_id']):
            raise ValidationError('ID account non valido.')
        with repository._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            account_view(db, body['account_id'])
            if not db.execute('SELECT 1 FROM sessions WHERE id=?', (session_id,)).fetchone():
                raise NotFoundError()
            if db.execute('SELECT 1 FROM session_owners WHERE session_id=?', (session_id,)).fetchone():
                raise ValidationError('Proprietà già assegnata; trasferimento non consentito.')
            if db.execute('SELECT 1 FROM matches WHERE human_id=? OR agent_id=?', (session_id, session_id)).fetchone() or db.execute(
                    'SELECT 1 FROM arena_trials WHERE session_id=?', (session_id,)).fetchone():
                raise ValidationError('Le sessioni storiche di confronti e Arena restano riservate allo staff.')
            from .identity_store import charge
            charge(db, body['account_id'], 'sessions')
            db.execute('INSERT INTO session_owners VALUES(?,?)', (session_id, body['account_id']))
            store.audit(db, request.state.account['account_id'], 'assign', session_id)
        return {'session_id': session_id, 'account_id': body['account_id']}

    @app.get('/v1/admin/audit')
    async def audit(after: int = 0):
        if type(after) is not int or after < 0:
            raise ValidationError('Cursore non valido.')
        with repository._connect() as db:
            rows = db.execute('SELECT seq,time,actor,action,target FROM account_audit WHERE seq>? ORDER BY seq LIMIT 100', (after,)).fetchall()
        return {'audit': [dict(zip(('seq', 'time', 'actor', 'action', 'target'), row)) for row in rows],
                'next_after': rows[-1][0] if rows else after}
