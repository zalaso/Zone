"""Start an isolated loopback server and browser with synthetic keys; no downloads."""

import argparse
import json
import re
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.request import build_opener, ProxyHandler

from hidden_lab.backend_store import SQLiteRepository
from hidden_lab.identity_store import IdentityStore
from hidden_lab.world_forge import generate_world
from tools.verify_distribution import clean_environment


def verify(out):
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False, mode=0o700)
    root = Path(__file__).resolve().parents[1]
    repo = SQLiteRepository(out / 'browser.db', [generate_world(130031, 1, 2)])
    identity = IdentityStore(repo)
    admin = identity.create('admin', 'admin', bootstrap=True)
    member = identity.create('alice', actor=admin['account_id'])
    other = identity.create('bob', actor=admin['account_id'])
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    origin = f'http://127.0.0.1:{port}'
    env = clean_environment()
    opener = build_opener(ProxyHandler({}))
    with (out / 'server.log').open('w', encoding='utf-8') as log:
        server = subprocess.Popen([sys.executable, '-m', 'hidden_lab', 'serve', '--db', str(repo.path),
            '--port', str(port), '--auth-mode', 'accounts', '--public-origin', origin, '--local-cookies',
            '--web-dir', str(root / 'frontend/dist')], cwd=root, env=env, stdout=log, stderr=log)
        try:
            deadline = time.monotonic() + 30
            while True:
                try:
                    with opener.open(origin + '/health/ready', timeout=1) as response:
                        if response.status == 200:
                            break
                except OSError:
                    if time.monotonic() >= deadline or server.poll() is not None:
                        raise RuntimeError('Offline server did not start; inspect private server.log') from None
                    time.sleep(.25)
            env.update(ZONE_SMOKE_BASE_URL=origin, ZONE_SMOKE_ACCOUNT_KEY=member['login_key'],
                       ZONE_SMOKE_OTHER_KEY=other['login_key'], ZONE_SMOKE_ADMIN_KEY=admin['login_key'],
                       ZONE_SMOKE_OUTPUT=str(out))
            result = subprocess.run(['node', 'scripts/smoke-identity.mjs'], cwd=root / 'frontend',
                                    env=env, capture_output=True, text=True, timeout=120)
            if result.returncode:
                # Playwright diagnostics may include filled input values: do not print or save them.
                stages = re.findall(r'zone-smoke-stage:([a-z]+)', result.stderr)
                lines = re.findall(r'smoke-identity\.mjs:\d+:\d+', result.stderr)
                raise RuntimeError('Browser smoke failed: stage=' + (stages[-1] if stages else 'launch') +
                                   ', location=' + (lines[-1] if lines else 'unavailable'))
            report = json.loads(result.stdout.strip())
            (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
            return report
        finally:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    print(json.dumps(verify(parser.parse_args().out), indent=2))
