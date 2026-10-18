"""Root-owned VPS maintenance; operates only on the named Zone container/data."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
from urllib.request import build_opener, ProxyHandler
from urllib.parse import urlsplit

ROOT = Path('/opt/zone')
CONTAINER = 'zone-beta-zone-1'


def main(action):
    os.umask(0o077)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    if action == 'backup':
        destination = f'/data/backups/zone-{stamp}.sqlite3'
        result = subprocess.run(['docker', 'exec', CONTAINER, 'python', '-m', 'hidden_lab',
                                 'ops', 'backup', '--db', '/data/zone.sqlite3', '--out', destination],
                                capture_output=True, text=True, timeout=90)
        if result.returncode:
            raise RuntimeError('Zone backup failed; command output withheld')
        report = {'ok': True, 'action': action, 'utc': stamp, 'backup': destination,
                  'schema_version': json.loads(result.stdout)['schema_version']}
    else:
        opener = build_opener(ProxyHandler({}))
        with opener.open('http://127.0.0.1:8876/health/ready', timeout=5) as response:
            assert response.status == 200
        origin = next(line.split('=', 1)[1] for line in (ROOT / 'compose.env').read_text().splitlines()
                      if line.startswith('ZONE_PUBLIC_ORIGIN='))
        target = urlsplit(origin)
        assert target.scheme == 'https' and target.hostname and not target.username and not target.password
        assert not target.path and not target.query and not target.fragment
        with opener.open(origin + '/health/ready', timeout=10) as response:
            assert response.status == 200 and json.load(response)['status'] == 'ready'
        container = json.loads(subprocess.check_output(['docker', 'inspect', CONTAINER],
                                                       text=True, timeout=10))[0]
        assert container['State']['Running'] and container['State']['Health']['Status'] == 'healthy'
        free = shutil.disk_usage(ROOT).free
        assert free >= 2 * 1024**3, 'Zone host disk below 2 GiB free'
        backups = list((ROOT / 'data/backups').glob('zone-*.sqlite3.manifest.json'))
        assert backups and datetime.now(timezone.utc).timestamp() - max(
            p.stat().st_mtime for p in backups) < 36 * 3600, 'Zone backup stale or missing'
        report = {'ok': True, 'action': action, 'utc': stamp, 'ready': True,
                  'https_ready': True, 'disk_free_bytes': free, 'backup_recent': True,
                  'container_restarts': container['RestartCount']}
    (ROOT / 'ops' / f'{action}-latest.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('backup', 'check'))
    main(parser.parse_args().action)
