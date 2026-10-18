"""Review publishable files and reachable Git blobs without printing matched secrets.

This is a local heuristic guard, not a credential-detection certification.
Ignored data is never read. Reports contain only paths, rule names and blob IDs.
"""
import argparse
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
RULES = {
    'private-key': re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----'),
    'github-token': re.compile(rb'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,})\b'),
    'provider-token': re.compile(rb'\bsk-(?:proj-|ant-api\d+-)?[A-Za-z0-9_-]{32,}\b'),
    'google-token': re.compile(rb'\bAIza[A-Za-z0-9_-]{35}\b'),
    'oauth-token': re.compile(rb'\bya29\.[A-Za-z0-9_-]{35,}'),
    'jwt-token': re.compile(rb'\beyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{20,}'),
    'zone-credential': re.compile(rb'\b(?:zk|za|zc)_[A-Za-z0-9_-]{40,}\b'),
}
PRIVATE_PARTS = {'benchmark_data', 'benchmark_private', 'benchmark_runs', 'sessions', '.venv', 'node_modules', 'zone-data'}
PRIVATE_NAMES = {'credentials.json', 'credentials.dpapi', 'connection.key', 'admin-key.txt', '.env'}
PERSONAL = re.compile(rb'(?:https?://[A-Za-z0-9.-]+\.duckdns\.org|C:[\\/]Users[\\/][^\\/\s]+)')


def git(*args):
    return subprocess.check_output(['git', '-c', 'safe.directory=' + ROOT.as_posix(), *args], cwd=ROOT)


def path_problems(name):
    path = PurePosixPath(name)
    return (any(p in PRIVATE_PARTS for p in path.parts) or path.name in PRIVATE_NAMES
            or path.name.startswith('.env.') and path.name != '.env.example' or path.suffix in ('.db', '.sqlite', '.sqlite3', '.log', '.dpapi')
            or name.endswith(('.private.json', '.bak')))


def content_problems(content):
    return [name for name, pattern in RULES.items() if pattern.search(content)]


def worktree():
    names = sorted(set(git('ls-files', '-z', '--cached', '--others', '--exclude-standard').decode().split('\0')) - {''})
    findings = []
    for name in names:
        path = ROOT / name
        if not path.exists():
            continue
        if path_problems(name) or path.is_symlink():
            findings.append({'path': name, 'rule': 'private-path-or-symlink'})
            continue
        data = path.read_bytes()
        findings.extend({'path': name, 'rule': rule} for rule in content_problems(data))
        if name.endswith(('.md', '.yaml', '.yml', '.caddy')) and PERSONAL.search(data):
            findings.append({'path': name, 'rule': 'personal-deployment-reference'})
    return len(names), findings


def history():
    objects = git('rev-list', '--objects', '--all').splitlines()
    names = {}
    for row in objects:
        oid, _, name = row.partition(b' ')
        names[oid.decode()] = name.decode('utf-8', errors='replace')
    findings, count = [], 0
    # Batch avoids one subprocess per historical file. Do not expose blob contents.
    process = subprocess.Popen(['git', '-c', 'safe.directory=' + ROOT.as_posix(), 'cat-file', '--batch'],
                               cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    try:
        for oid, name in names.items():
            process.stdin.write((oid + '\n').encode()); process.stdin.flush()
            header = process.stdout.readline().split()
            if len(header) != 3:
                raise RuntimeError('Git blob audit failed')
            size = int(header[2]); data = process.stdout.read(size); process.stdout.read(1)
            if header[1] != b'blob':
                continue
            count += 1
            rules = content_problems(data)
            if path_problems(name):
                rules.append('private-path')
            findings.extend({'path': name, 'blob': oid, 'rule': rule} for rule in rules)
    finally:
        process.stdin.close(); process.wait(timeout=15)
    return count, findings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--history', action='store_true')
    parser.add_argument('--out', type=Path)
    parser.add_argument('--archives', type=Path)
    parser.add_argument('--no-worktree', action='store_true')
    args = parser.parse_args()
    count, findings = (0, []) if args.no_worktree else worktree()
    report = {'files_checked': count, 'worktree_findings': findings}
    if args.history:
        count, findings = history()
        report.update(history_blobs_checked=count, history_findings=findings)
    if args.archives:
        findings = []
        for path in sorted(args.archives.iterdir()):
            if path.suffix == '.whl':
                with zipfile.ZipFile(path) as archive:
                    members = [(name, archive.read(name)) for name in archive.namelist() if not name.endswith('/')]
            elif path.name.endswith('.tar.gz'):
                with tarfile.open(path) as archive:
                    members = [(entry.name, archive.extractfile(entry).read()) for entry in archive.getmembers() if entry.isfile()]
            else:
                continue
            for name, data in members:
                rules = content_problems(data)
                if path_problems(name):
                    rules.append('private-path')
                findings.extend({'archive': path.name, 'path': name, 'rule': rule} for rule in rules)
        report['archive_findings'] = findings
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))
    return int(bool(report['worktree_findings'] or report.get('history_findings') or report.get('archive_findings')))


if __name__ == '__main__':
    raise SystemExit(main())
