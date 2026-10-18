"""Invited-host smoke. Reads only synthetic fixture keys over SSH; checks destination."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import time
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import build_opener, ProxyHandler, Request


def validate_origin(origin, *, public=False):
    target = urlsplit(origin)
    if (target.scheme != 'https' or not target.hostname
            or not (target.hostname.endswith('.ts.net') or public and target.hostname == 'zone.example.org')
            or target.username or target.password or target.path or target.query or target.fragment):
        raise ValueError('Explicit approved HTTPS origin required; public beta needs --public')
    _ = target.port


def verify(origin, out, *, public=False, ssh_host):
    validate_origin(origin, public=public)
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.@-]{0,250}', ssh_host):
        raise ValueError('Explicit SSH destination required')
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False, mode=0o700)
    root = Path(__file__).resolve().parents[1]
    remote_code = ("import json,pathlib; root=pathlib.Path('/opt/zone'); "
                   "origin=next(line.split('=',1)[1] for line in (root/'compose.env').read_text().splitlines() "
                   "if line.startswith('ZONE_PUBLIC_ORIGIN=')); "
                   "print(json.dumps({'origin':origin,'accounts':json.loads((root/'secrets/smoke-accounts.json').read_text())}))")
    result = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
                             '-o', 'ConnectTimeout=15', ssh_host,
                             'python3 -c ' + shlex.quote(remote_code)],
                            capture_output=True, text=True, timeout=25)
    if result.returncode:
        raise RuntimeError('Synthetic fixture unavailable; output withheld')
    fixture = json.loads(result.stdout)
    if fixture['origin'] != origin:
        raise ValueError('Refusing to send fixture keys to an origin different from VPS configuration')
    accounts = fixture['accounts']
    env = dict(os.environ)
    for key in list(env):
        if key.upper().endswith(('API_KEY', 'API_TOKEN')):
            env.pop(key)
    env.update(ZONE_SMOKE_BASE_URL=origin, ZONE_SMOKE_ACCOUNT_KEY=accounts['member']['login_key'],
               ZONE_SMOKE_OUTPUT=str(out), ZONE_SMOKE_PUBLIC='1' if public else '0')
    browser = subprocess.run(['node', 'scripts/smoke-beta.mjs'], cwd=root / 'frontend',
                             env=env, capture_output=True, text=True, timeout=150)
    if browser.returncode:
        stages = re.findall(r'zone-smoke-stage:([a-z]+)', browser.stderr)
        lines = re.findall(r'smoke-beta\.mjs:\d+:\d+', browser.stderr)
        raise RuntimeError('Hosted smoke failed; diagnostics withheld: stage=' +
                           (stages[-1] if stages else 'launch') + ', location=' +
                           (lines[-1] if lines else 'unknown'))
    report = {'browser': json.loads(browser.stdout.strip())}

    def request(path, account=None, body=None):
        headers = {} if account is None else {'Authorization': 'Bearer ' + accounts[account]['login_key']}
        payload = None
        if body is not None:
            headers['Content-Type'] = 'application/json'
            payload = json.dumps(body).encode()
        opener = build_opener(ProxyHandler({}))
        try:
            with opener.open(Request(origin + path, data=payload, headers=headers), timeout=30) as reply:
                return reply.status, json.load(reply)
        except HTTPError as error:
            return error.code, None

    # Browser mutations and this short cycle share the proxy's aggregate IP rate budget.
    # A new rate window avoids confusing intentional rate protection with test failure.
    time.sleep(60)
    assert request('/v1/worlds')[0] == 401
    status, modes = request('/v1/modes', 'member')
    assert status == 200 and modes['agent']['real_model'] is False
    status, worlds = request('/v1/worlds', 'member')
    assert status == 200
    status, state = request('/v1/sessions', 'member',
                            {'world_id': worlds['worlds'][0]['world_id'], 'mode': 'watch_agent'})
    assert status == 201
    sid = state['session_id']
    for _ in range(35):
        if state['status'] == 'scored':
            break
        body = {'expected_version': state['version']}
        phase, account = state['status'], 'member'
        if phase in ('discovering', 'awaiting_prediction', 'awaiting_submission'):
            action = 'agent/step'
        elif phase == 'awaiting_decision':
            account, action = 'admin', 'messages'
            body['message'] = {'type': 'operator_decision', 'request_id': state['pending_request_id'],
                               'action': 'approve', 'reason': 'Smoke HTTPS sintetico.'}
        elif phase == 'awaiting_mode':
            account, action = 'admin', 'messages'
            body['message'] = {'type': 'execution_mode', 'request_id': state['pending_request_id'],
                               'mode': 'exploration'}
        elif phase == 'ready_to_run':
            account, action = 'admin', 'run'
            body['request_id'] = state['pending_request_id']
        else:
            raise AssertionError('Unexpected hosted phase')
        status, state = request(f'/v1/sessions/{sid}/{action}', account, body)
        assert status == 200, f'Hosted action {action}: HTTP {status}'
    assert state['status'] == 'scored'
    assert request(f'/v1/sessions/{sid}', 'other')[0] == 404
    assert request('/v1/admin/accounts', 'member')[0] == 403
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=4) as pool:
        reads = list(pool.map(lambda _: request('/v1/worlds', 'other')[0], range(12)))
    assert reads == [200] * 12
    report.update(offline_cycle_scored=True, executed_experiments=state['executed_experiments'],
                  cross_account_denied=True, member_admin_denied=True,
                  concurrent_read_requests=12, concurrent_read_workers=4,
                  concurrent_read_seconds=round(time.monotonic() - started, 3), real_provider_calls=0)
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--origin', required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--ssh-host', required=True, help='Explicit host alias with synthetic smoke fixtures only')
    parser.add_argument('--public', action='store_true', help='Allow the configured invited-public-beta hostname')
    args = parser.parse_args()
    print(json.dumps(verify(args.origin, args.out, public=args.public, ssh_host=args.ssh_host), indent=2))
