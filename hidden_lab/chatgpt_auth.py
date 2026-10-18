"""Official local OAuth registration. Tokens never enter Session or model payloads.

One protected store, multiple registrations, a process lock across token rotation.
Windows uses user-bound DPAPI; Unix uses owner-only directories/files.
"""
import base64
from contextlib import contextmanager
import ctypes
from dataclasses import dataclass, field
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import re
import secrets
import time
from urllib.parse import parse_qs, urlencode, urlsplit
import uuid
import webbrowser

ISSUER = 'https://auth.openai.com'
AUTHORIZE = ISSUER + '/api/accounts/authorize'
TOKEN = ISSUER + '/api/accounts/oauth/token'
JWKS = ISSUER + '/.well-known/jwks.json'
RESOURCE = 'https://api.openai.com/v1'
DIRECT_SCOPE = 'chatgpt.tokens.use.direct'
SCOPES = 'openid profile email offline_access resource.invoke ' + DIRECT_SCOPE


class AuthError(ValueError):
    """Fixed, non-secret diagnostics only."""

    def __init__(self, message, code=None):
        self.code = code
        super().__init__(message)


def _dpapi(data, decrypt=False):
    from ctypes import wintypes
    class Blob(ctypes.Structure):
        _fields_ = [('cbData', wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_ubyte))]
    buffer = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    output = Blob()
    crypt = ctypes.WinDLL('crypt32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    if decrypt:
        operation = crypt.CryptUnprotectData
    else:
        operation = crypt.CryptProtectData
    operation.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p,
                          ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    operation.restype = wintypes.BOOL
    if not operation(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(output)):
        raise AuthError('Protezione credenziali Windows non disponibile.')
    try:
        return ctypes.string_at(output.pbData, output.cbData)
    finally:
        kernel.LocalFree(output.pbData)


class CredentialStore:
    def __init__(self, directory=None):
        if directory is None:
            directory = (Path(os.environ['LOCALAPPDATA']) / 'Zone' / 'chatgpt' if os.name == 'nt'
                         else Path.home() / '.config' / 'zone' / 'chatgpt')
        self.directory = Path(directory)
        self.path = self.directory / ('credentials.dpapi' if os.name == 'nt' else 'credentials.json')
        self._locked = False

    def _prepare(self):
        if any(p.is_symlink() for p in (self.directory, *self.directory.parents)):
            raise AuthError('Archivio credenziali: collegamenti simbolici non ammessi.')
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        if os.name != 'nt':
            stat = self.directory.stat()
            if stat.st_uid != os.getuid() or stat.st_mode & 0o077:
                raise AuthError('Archivio credenziali: occorrono proprietario corrente e permessi 0700.')

    @contextmanager
    def lock(self):
        self._prepare()
        path = self.directory / 'session.lock'
        try:
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            raise AuthError('Un altro processo usa il login ChatGPT. Chiudilo prima di continuare.') from None
        try:
            os.close(descriptor)
            self._locked = True
            yield self
        finally:
            self._locked = False
            path.unlink()

    def load(self):
        if not self._locked:
            raise AuthError('Archivio credenziali senza lock.')
        if not self.path.exists():
            return {'version': 1, 'host_id': 'urn:uuid:' + str(uuid.uuid4()), 'active': None, 'accounts': []}
        try:
            if self.path.is_symlink() or self.path.stat().st_size > 256000:
                raise ValueError()
            if os.name != 'nt' and (self.path.stat().st_uid != os.getuid() or self.path.stat().st_mode & 0o077):
                raise ValueError()
            raw = self.path.read_bytes()
            value = json.loads(_dpapi(raw, decrypt=True) if os.name == 'nt' else raw)
            if value['version'] != 1 or not isinstance(value['accounts'], list):
                raise ValueError()
            uuid.UUID(value['host_id'].removeprefix('urn:uuid:'))
            return value
        except Exception:
            raise AuthError('Archivio ChatGPT non valido o non accessibile a questo utente.') from None

    def save(self, value):
        if not self._locked:
            raise AuthError('Archivio credenziali senza lock.')
        raw = json.dumps(value, ensure_ascii=False, allow_nan=False).encode('utf-8')
        if os.name == 'nt':
            raw = _dpapi(raw)
        temporary = self.directory / ('write-' + secrets.token_hex(8))
        try:
            descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(descriptor, 'wb') as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)


def auth_http():
    import httpx
    return httpx.Client(timeout=30, trust_env=False, follow_redirects=False)


def _json_request(http, method, url, **kwargs):
    try:
        response = http.request(method, url, **kwargs)
        if response.status_code != 200 or len(response.content) > 256000:
            code = None
            try:
                error = response.json()
                candidate = error.get('error')
                if isinstance(candidate, dict):
                    candidate = candidate.get('code')
                if candidate in ('invalid_grant', 'invalid_refresh_token', 'token_expired', 'refresh_token_expired',
                                  'refresh_token_invalidated', 'refresh_token_reused', 'invalid_client'):
                    code = candidate
            except Exception:
                pass
            raise AuthError(f'Accesso ChatGPT non completato (HTTP {response.status_code}). Nessun retry automatico.', code)
        value = response.json()
        if not isinstance(value, dict):
            raise ValueError()
        return value
    except AuthError:
        raise
    except Exception:
        raise AuthError('Rete o risposta non valida durante il login ChatGPT; nessun retry automatico.') from None


@dataclass(repr=False)
class LoginAttempt:
    host_id: str
    redirect_uri: str
    client_id: str | None = None
    state: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    nonce: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    verifier: str = field(default_factory=lambda: secrets.token_urlsafe(64))
    deadline: float = field(default_factory=lambda: time.monotonic() + 180)
    consumed: bool = False

    def url(self):
        parameters = {'client_id': self.client_id or 'dynamic_agent_client',
                      'ext_agent_host_id': self.host_id, 'response_type': 'code',
                      'redirect_uri': self.redirect_uri, 'scope': SCOPES, 'resource': RESOURCE,
                      'state': self.state, 'nonce': self.nonce, 'code_challenge_method': 'S256',
                      'code_challenge': base64.urlsafe_b64encode(hashlib.sha256(self.verifier.encode()).digest()).decode().rstrip('=')}
        if self.client_id is None:
            parameters['agent_name_hint'] = 'Zone'
        # No id_token_hint, email or credentials in the URL or terminal output.
        return AUTHORIZE + '?' + urlencode(parameters)

    def callback(self, path):
        if self.consumed or time.monotonic() >= self.deadline:
            raise AuthError('Login scaduto o callback già consumato.')
        self.consumed = True
        try:
            parts = urlsplit(path)
            if parts.path != '/auth/callback' or len(path) > 16384:
                raise ValueError()
            values = parse_qs(parts.query, keep_blank_values=True, max_num_fields=20)
            if any(len(value) != 1 for value in values.values()):
                raise ValueError()
            if not secrets.compare_digest(values.get('state', [''])[0], self.state):
                raise ValueError()
            if 'error' in values:
                raise AuthError('Accesso o consenso ChatGPT rifiutato.')
            code = values.get('code', [''])[0]
            client_id = values.get('client_id', [self.client_id])[0]
            if not code or not isinstance(client_id, str) or not re.fullmatch(r'oaiapp_[A-Za-z0-9_-]{1,200}', client_id):
                raise ValueError()
            if self.client_id is not None and client_id != self.client_id:
                raise ValueError()
            return code, client_id
        except AuthError:
            raise
        except Exception:
            raise AuthError('Callback ChatGPT non verificato. Nessun codice scambiato.') from None


def verify_identity(http, token, client_id, *, nonce=None, subject=None):
    import jwt
    try:
        header = jwt.get_unverified_header(token)
        keys = _json_request(http, 'GET', JWKS)['keys']
        matches = [key for key in keys if key.get('kid') == header.get('kid')]
        if header.get('alg') != 'RS256' or len(matches) != 1:
            raise ValueError()
        key = jwt.PyJWK.from_dict(matches[0], algorithm='RS256')
        claims = jwt.decode(token, key.key, algorithms=['RS256'], issuer=ISSUER, audience=client_id,
                            leeway=5, options={'require': ['sub', 'exp', 'iat', 'iss', 'aud']})
        if not isinstance(claims['sub'], str) or not claims['sub']:
            raise ValueError()
        if nonce is not None and claims.get('nonce') != nonce:
            raise ValueError()
        if subject is not None and claims['sub'] != subject:
            raise ValueError()
        return claims
    except Exception:
        raise AuthError('Identità ChatGPT non verificata: firma, account o claims non validi.') from None


def token_record(tokens, client_id, identity, *, previous=None):
    try:
        for name in ('access_token', 'refresh_token', 'id_token'):
            if not isinstance(tokens[name], str) or not 1 <= len(tokens[name]) <= 64000:
                raise ValueError()
        if tokens['token_type'].lower() != 'bearer' or type(tokens['expires_in']) is not int or not 1 <= tokens['expires_in'] <= 86400:
            raise ValueError()
        scopes = tokens['scope'].split()
        return {'client_id': client_id, 'subject': identity['sub'],
                'email': identity.get('email') if isinstance(identity.get('email'), str) else None,
                'access_token': tokens['access_token'], 'refresh_token': tokens['refresh_token'],
                'id_token': tokens['id_token'], 'scopes': scopes,
                'expires_at': time.time() + tokens['expires_in'],
                'earliest_refresh_at': tokens.get('earliest_refresh_at'),
                'label': previous.get('label') if previous else client_id}
    except Exception:
        raise AuthError('Risposta OAuth incompleta; credenziali precedenti conservate.') from None


def active_account(state):
    account = next((a for a in state['accounts'] if a['client_id'] == state['active']), None)
    if account is None:
        raise AuthError('Accedi prima con: python -m hidden_lab chatgpt login')
    return account


def access_token(store, http):
    state = store.load()
    account = active_account(state)
    if account.get('pending_vm_transfer'):
        raise AuthError('Trasferimento VPS pendente: completa o riconcilia il trasferimento prima di usare il piano.')
    if DIRECT_SCOPE not in account.get('scopes', []) or not account.get('access_token'):
        raise AuthError('Uso del piano ChatGPT non autorizzato; esegui nuovamente chatgpt login.')
    if account['expires_at'] <= time.time() + 30:
        earliest = account.get('earliest_refresh_at')
        if isinstance(earliest, (int, float)) and earliest > time.time():
            raise AuthError('Rinnovo ChatGPT non ancora consentito; riprova più tardi.')
        try:
            tokens = _json_request(http, 'POST', TOKEN, data={'grant_type': 'refresh_token',
                                   'client_id': account['client_id'], 'refresh_token': account['refresh_token'],
                                   'resource': RESOURCE})
        except AuthError as exc:
            if exc.code in ('invalid_grant', 'invalid_refresh_token', 'token_expired', 'refresh_token_expired',
                            'refresh_token_invalidated', 'refresh_token_reused'):
                for name in ('access_token', 'refresh_token', 'id_token'):
                    account.pop(name, None)
                account['scopes'] = []
                store.save(state)
                raise AuthError('Sessione ChatGPT revocata/scaduta. Esegui nuovamente chatgpt login.') from None
            raise
        identity = verify_identity(http, tokens.get('id_token'), account['client_id'], subject=account['subject'])
        replacement = token_record(tokens, account['client_id'], identity, previous=account)
        if DIRECT_SCOPE not in replacement['scopes']:
            raise AuthError('Rinnovo senza permesso di usare il piano; nessuna inferenza avviata.')
        state['accounts'][state['accounts'].index(account)] = replacement
        store.save(state)
        account = replacement
    return account['access_token']


def login(store, *, new_account=False, open_browser=webbrowser.open, http=None):
    """Human browser consent; no inference, no callbacks or token values logged."""
    with store.lock():
        state = store.load()
        store.save(state)  # Persist host ID before the first registration, including failed login.
        previous = None if new_account or state['active'] is None else active_account(state)
        result = {}
        attempt = None
        class CallbackServer(HTTPServer):
            def get_request(self):
                connection, address = super().get_request()
                connection.settimeout(1)
                return connection, address
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                if urlsplit(self.path).path != '/auth/callback' or self.headers.get('Host') != urlsplit(attempt.redirect_uri).netloc:
                    self.send_error(404)
                    return
                try:
                    result['callback'] = attempt.callback(self.path)
                except AuthError as exc:
                    result['error'] = exc
                body = b'Zone: callback ricevuto. Torna al terminale per il risultato del login.'
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain; charset=utf-8')
                self.send_header('Content-Length', str(len(body)))
                self.send_header('Cache-Control', 'no-store')
                self.send_header('Referrer-Policy', 'no-referrer')
                self.send_header('Content-Security-Policy', "default-src 'none'")
                self.end_headers()
                self.wfile.write(body)
        with CallbackServer(('127.0.0.1', 0), Handler) as server:
            server.timeout = 0.5
            attempt = LoginAttempt(state['host_id'], f'http://127.0.0.1:{server.server_port}/auth/callback',
                                   previous['client_id'] if previous else None)
            print('Continue with ChatGPT: autorizza Zone e l’uso del piano nel browser. Attendo fino a 180 s; Ctrl+C annulla.')
            if not open_browser(attempt.url()):
                raise AuthError('Browser non aperto. Imposta il browser predefinito e ripeti chatgpt login.')
            while not result and time.monotonic() < attempt.deadline:
                server.handle_request()
        if not result:
            raise AuthError('Login ChatGPT scaduto; nessuna inferenza avviata.')
        if 'error' in result:
            raise result['error']
        code, client_id = result['callback']
        own_http = http is None
        http = http or auth_http()
        try:
            tokens = _json_request(http, 'POST', TOKEN, data={'grant_type': 'authorization_code',
                                   'client_id': client_id, 'code': code, 'code_verifier': attempt.verifier,
                                   'redirect_uri': attempt.redirect_uri, 'resource': RESOURCE})
            identity = verify_identity(http, tokens.get('id_token'), client_id, nonce=attempt.nonce,
                                       subject=previous['subject'] if previous else None)
            account = token_record(tokens, client_id, identity, previous=previous)
            existing = next((a for a in state['accounts'] if a['client_id'] == client_id), None)
            if existing is not None and existing['subject'] != account['subject']:
                raise AuthError('Account diverso dalla registrazione salvata; nessuna sostituzione.')
            if existing is not None:
                state['accounts'].remove(existing)
            state['accounts'].append(account)
            state['active'] = client_id
            store.save(state)
            print('Login verificato. Uso del piano: ' + ('autorizzato.' if DIRECT_SCOPE in account['scopes'] else 'NON autorizzato; nessuna inferenza consentita.'))
            return DIRECT_SCOPE in account['scopes']
        finally:
            if own_http:
                http.close()


def logout(store, http):
    state = store.load()
    account = active_account(state)
    confirmed = False
    try:
        if account.get('refresh_token'):
            discovery = _json_request(http, 'GET', ISSUER + '/.well-known/openid-configuration')
            endpoint = discovery['revocation_endpoint']
            url = urlsplit(endpoint)
            if url.scheme != 'https' or url.netloc != 'auth.openai.com':
                raise ValueError()
            confirmed = http.post(endpoint, data={'token': account['refresh_token'], 'token_type_hint': 'refresh_token',
                                                 'client_id': account['client_id']}).status_code == 200
    except Exception:
        pass
    for field_name in ('access_token', 'refresh_token', 'id_token'):
        account.pop(field_name, None)
    account['scopes'] = []
    store.save(state)  # Keep host and account/client identity for later explicit reauthorization.
    return confirmed
