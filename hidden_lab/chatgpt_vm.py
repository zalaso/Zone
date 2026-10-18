"""Explicit personal VM transfer over pinned SSH; no secret files or token output.

The VM becomes the refresh owner. A missing acknowledgement is indeterminate:
do not run either client until the same transfer is completed or reconciled.
"""
import copy
import json
import os
import re
import subprocess
import sys
import uuid

from .chatgpt_auth import AuthError, DIRECT_SCOPE, active_account

VM_STORE = '/auth/chatgpt'
def import_command(ssh_host, container):
    if (not isinstance(ssh_host, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.@-]{0,253}', ssh_host)
            or not isinstance(container, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', container)):
        raise AuthError('Specifica --ssh-host e --container validi; nessuna destinazione predefinita.')
    return ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=15', ssh_host,
            'docker exec -i --user 10001:10001 ' + container + ' python -m hidden_lab chatgpt vm-import']


TOKEN_FIELDS = ('access_token', 'refresh_token', 'id_token')


def import_registration(store, raw):
    """Private stdin only. Retain the VM host ID; never overwrite another registration."""
    try:
        if len(raw) > 256000:
            raise ValueError()
        value = json.loads(raw)
        if set(value) != {'transfer_id', 'account'}:
            raise ValueError()
        uuid.UUID(value['transfer_id'])
        account = value['account']
        required = {'client_id', 'subject', 'scopes', 'expires_at', *TOKEN_FIELDS}
        allowed = required | {'email', 'earliest_refresh_at', 'label'}
        if not isinstance(account, dict) or not required <= set(account) <= allowed:
            raise ValueError()
        if any(not isinstance(account[k], str) or not account[k] for k in (*TOKEN_FIELDS, 'client_id', 'subject')):
            raise ValueError()
        if not isinstance(account['scopes'], list) or DIRECT_SCOPE not in account['scopes']:
            raise ValueError()
        if type(account['expires_at']) not in (int, float):
            raise ValueError()
    except Exception:
        raise AuthError('Trasferimento OAuth non valido; nessun contenuto registrato.') from None
    with store.lock():
        state = store.load()
        # Persist the destination host BEFORE credentials are imported, even on conflict.
        store.save(state)
        if state.get('vm_transfer_id') == value['transfer_id'] and state['active'] == account['client_id']:
            return {'imported': True, 'transfer_id': value['transfer_id']}
        if state['accounts']:
            raise AuthError('Il VPS contiene già una registrazione. Riconciliala prima del trasferimento.')
        state['accounts'] = [account]
        state['active'] = account['client_id']
        state['vm_transfer_id'] = value['transfer_id']
        store.save(state)
    return {'imported': True, 'transfer_id': value['transfer_id']}


def transfer_to_vps(store, *, ssh_host=None, container=None, runner=subprocess.run):
    """Caller must explicitly authorize this credential move. No network inference."""
    command = import_command(ssh_host, container)
    destination = ssh_host + ":" + container
    with store.lock():
        state = store.load()
        account = active_account(state)
        if DIRECT_SCOPE not in account.get('scopes', []) or not all(account.get(k) for k in TOKEN_FIELDS):
            raise AuthError('Accedi prima con chatgpt login; nessuna credenziale trasferita.')
        # Persist the attempt before SSH so a lost acknowledgement can be retried idempotently.
        if account.get('pending_vm_transfer') and account.get('pending_vm_destination') != destination:
            raise AuthError('Trasferimento pendente: non cambiare destinazione; riconcilia prima lo stato.')
        transfer_id = account.setdefault('pending_vm_transfer', str(uuid.uuid4()))
        account['pending_vm_destination'] = destination
        store.save(state)
        exported = {k: v for k, v in account.items() if k not in ('pending_vm_transfer', 'pending_vm_destination')}
        raw = json.dumps({'transfer_id': transfer_id, 'account': exported}, allow_nan=False)
        try:
            result = runner(command, input=raw, text=True, capture_output=True, timeout=45, check=False)
            ack = json.loads(result.stdout)
            if result.returncode != 0 or ack != {'imported': True, 'transfer_id': transfer_id}:
                raise ValueError()
        except Exception:
            raise AuthError('Trasferimento non confermato. Non usare i client PC/VPS; ripeti lo stesso '
                            'comando o riconcilia lo stato. Nessun retry automatico.') from None
        replacement = copy.deepcopy(account)
        for field in (*TOKEN_FIELDS, 'pending_vm_transfer', 'pending_vm_destination'):
            replacement.pop(field, None)
        replacement['scopes'] = []
        state['accounts'][state['accounts'].index(account)] = replacement
        try:
            store.save(state)
        except Exception:
            raise AuthError('VPS importato, rimozione locale non confermata. Non usare il client PC; '
                            'riconcilia l’archivio prima di avviare il modello.') from None
    return {'transferred': True, 'local_tokens_removed': True, 'inferences': 0}


def receive_vm_registration():
    if os.name == 'nt' or sys.stdin.isatty():
        raise AuthError('vm-import richiede stdin protetto sul VPS Linux.')
    from .chatgpt_auth import CredentialStore
    raw = sys.stdin.buffer.read(256001)
    return import_registration(CredentialStore(VM_STORE), raw)
