"""Personal Arena UI over the existing Arena state machine and idempotent receipts."""

import asyncio
from dataclasses import replace
import json
import secrets

from fastapi import HTTPException, Request

from .arena_contract import QUOTAS, label
from .arena_client import model_request
from .backend_store import ConflictError, NotFoundError
from .identity_store import account_view
from .protocol import ValidationError, observation_times, require_keys
from .provider_base import AgentSettings, ProviderError
from .web_agent import OfflineLabClient, decode_reply, safe_generation, safe_metadata


def install_public_arena(app, repository, store, mutate, snapshot, leaderboard_data):
    from .backend import MAX_MESSAGE_BYTES, OPERATOR_TYPES, _body, _version
    pending = {}

    def owned(db, account_id, *, sid=None, aid=None):
        if not account_view(db, account_id)['enabled']:
            raise HTTPException(401, 'Account disabilitato.')
        if sid:
            row = db.execute('SELECT t.agent_id FROM arena_trials t JOIN arena_owners o ON o.agent_id=t.agent_id '
                             'WHERE t.session_id=? AND o.account_id=?', (sid, account_id)).fetchone()
        else:
            row = db.execute('SELECT agent_id FROM arena_owners WHERE agent_id=? AND account_id=?', (aid, account_id)).fetchone()
        if row is None:
            raise NotFoundError()
        return row[0]

    def configured(owner, cid=None):
        value = app.state.connections.configured(owner, cid)
        return value or (OfflineLabClient(), AgentSettings('offline-affine-v1', max_calls=8, max_turns=8, max_corrections=0, max_points=3, timeout=110))

    def personal_snapshot(db, sid, aid, *, events=False):
        value = snapshot(db, sid, aid, events=events)
        stored = repository._read_session(db, sid)
        if stored['profile'].get('personal_ai'):
            value['resources']['managed_model_calls'] = len(stored['calls'])
            value['resources']['invalid_model_responses'] = sum(c['outcome'] == 'invalid' for c in stored['calls'])
            if events:
                value['agent_calls'] = stored['calls']
        return value

    @app.get('/v1/my/arena/leaderboards/{cid}')
    async def board(cid: str, request: Request):
        with repository._connect() as db:
            row = db.execute('SELECT closed FROM arena_challenges WHERE id=?', (cid,)).fetchone()
            if row is None:
                raise NotFoundError()
            if not row[0]:
                raise HTTPException(403, 'I confronti sono disponibili dopo la chiusura della challenge.')
            return leaderboard_data(db, 'operator', cid)

    @app.get('/v1/my/arena')
    async def listing(request: Request):
        owner = request.state.account['account_id']
        with repository._connect() as db:
            agents = [store.agent(db, row[0]) for row in db.execute('SELECT agent_id FROM arena_owners WHERE account_id=?', (owner,))]
            trials = [personal_snapshot(db, row[0], row[1]) for row in db.execute('SELECT t.session_id,t.agent_id FROM arena_trials t '
                'JOIN arena_owners o ON o.agent_id=t.agent_id WHERE o.account_id=? ORDER BY t.rowid', (owner,)).fetchall()]
        return {'agents': agents, 'trials': trials}

    @app.post('/v1/my/arena/agents', status_code=201)
    async def register(request: Request):
        body = await _body(request)
        require_keys(body, ('name',))
        owner = request.state.account['account_id']
        client, settings = configured(owner)
        aid = secrets.token_hex(16)
        with repository._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT COUNT(*) FROM arena_owners WHERE account_id=?', (owner,)).fetchone()[0] >= 5:
                raise HTTPException(429, 'Massimo cinque agenti personali Arena.')
            meta = {'name': label(body['name']), 'model': settings.model,
                    'kind': 'offline_baseline' if client.provider == 'offline_baseline' else 'external', 'model_verified': False}
            db.execute('INSERT INTO arena_agents(id,metadata_json,quotas_json) VALUES(?,?,?)', (aid, json.dumps(meta), json.dumps(QUOTAS)))
            db.execute('INSERT INTO arena_owners VALUES(?,?)', (aid, owner))
        return {'agent_id': aid, **meta}

    @app.post('/v1/my/arena/trials', status_code=201)
    async def new_trial(request: Request):
        body = await _body(request)
        require_keys(body, ('agent_id', 'challenge_id'))
        owner = request.state.account['account_id']
        client, settings = configured(owner)
        settings = replace(settings, max_corrections=0)
        with repository._connect() as db:
            aid = owned(db, owner, aid=body['agent_id'])
            registered_model = store.agent(db, aid)['model']
        if registered_model != settings.model:
            raise ValidationError('L’agente Arena è associato a un altro modello. Seleziona quel modello o crea un agente nuovo.')
        return await mutate(request, 'sessions', resolver=lambda db: owned(db, owner, aid=aid),
            body_override={'challenge_id': body['challenge_id']},
            personal_ai={'connection_id': getattr(client, 'connection_id', None),
                         'provider': client.provider, 'settings': settings.to_dict()})

    @app.get('/v1/my/arena/trials/{sid}')
    async def read_trial(sid: str, request: Request):
        with repository._connect() as db:
            aid = owned(db, request.state.account['account_id'], sid=sid)
            return personal_snapshot(db, sid, aid, events=True)

    @app.post('/v1/my/arena/trials/{sid}/step')
    async def step(sid: str, request: Request):
        body = await _body(request)
        require_keys(body, ('expected_version',))
        owner = request.state.account['account_id']
        with repository._connect() as db:
            aid = owned(db, owner, sid=sid)
            public = snapshot(db, sid, aid, events=True)
            profile = repository._read_session(db, sid)['profile'].get('personal_ai')
        if profile is None:
            raise ValidationError('Trial BYOA esterno: usa il client originale.')
        if public['version'] != _version(body['expected_version']):
            raise ConflictError()
        if public['status'] not in ('discovering', 'awaiting_submission'):
            raise ValidationError('Prima completa la decisione e il lancio.')
        if sid in pending and not pending[sid].done():
            raise ConflictError()
        client, _settings = configured(owner, profile['connection_id']) if profile['connection_id'] else (
            OfflineLabClient(), AgentSettings(**profile['settings']))
        settings = AgentSettings(**profile['settings'])
        if client.provider != profile['provider']:
            raise ValidationError('Profilo Arena cambiato; nessun fallback.')
        index = repository.reserve_call(sid, public['version'], settings.max_calls)
        audit = {'provider': client.provider, 'model': settings.model, 'settings': settings.to_dict(),
                 'sdk_version': getattr(client, 'sdk_version', None),
                 'generation_settings': safe_generation(client)}
        payload = model_request(public, settings, settings.max_calls - index)
        if payload.size_bytes() > settings.max_input_bytes:
            repository.finish_call(sid, index, 'invalid', audit)
            raise ValidationError('Storia pubblica oltre il limite di input.')
        audit.update(payload.contract_fingerprints())
        task = asyncio.create_task(asyncio.to_thread(client.complete, payload))
        pending[sid] = task
        try:
            reply = await asyncio.wait_for(asyncio.shield(task), settings.timeout)
            audit.update(safe_metadata(reply))
            if len(reply.text.encode('utf-8')) > MAX_MESSAGE_BYTES:
                raise ValidationError('Risposta agente troppo grande.')
            message = decode_reply(reply, payload.allowed_types)
            if message['type'] == 'experiment_request' and len(observation_times(message['experiment'])) > settings.max_points:
                raise ValidationError('Troppi punti per il budget di osservazione dell’agente personale.')
            kind = 'submission' if message['type'] == 'scientific_submission' else 'messages'
            field = 'submission' if kind == 'submission' else 'message'
            payload = {key: value for key, value in message.items() if key != 'type'} if kind == 'submission' else message
            result = await mutate(request, kind, sid, resolver=lambda db: owned(db, owner, sid=sid),
                                  body_override={'expected_version': public['version'], field: payload})
            repository.finish_call(sid, index, 'accepted' if result.status_code < 400 else 'invalid', audit)
            return result
        except (ProviderError, TimeoutError):
            repository.finish_call(sid, index, 'error', audit)
            raise HTTPException(503, 'Chiamata al modello fallita. Nessun lancio eseguito e nessun retry automatico.') from None
        except ValidationError:
            repository.finish_call(sid, index, 'invalid', audit)
            raise
        except Exception:
            repository.finish_call(sid, index, 'error', audit)
            raise HTTPException(503, 'Passo Arena interrotto; leggi il registro prima di proseguire.') from None
        finally:
            if task.done():
                pending.pop(sid, None)
            else:
                task.add_done_callback(lambda completed: completed.exception() if not completed.cancelled() else None)

    @app.post('/v1/my/arena/trials/{sid}/{kind}')
    async def operate(sid: str, kind: str, request: Request):
        if kind not in ('messages', 'run', 'stop', 'score'):
            raise NotFoundError()
        body = await _body(request)
        if kind == 'messages' and (not isinstance(body.get('message'), dict) or body['message'].get('type') not in OPERATOR_TYPES):
            raise ValidationError('Qui puoi soltanto decidere e scegliere la modalità. L’agente propone tramite il proprio passo.')
        owner = request.state.account['account_id']

        def resolver(db):
            owned(db, owner, sid=sid)
            return 'operator'

        return await mutate(request, kind, sid, resolver=resolver, body_override=body)
