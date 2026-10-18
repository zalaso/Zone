"""Validate release versions and archive boundaries without reading private data."""
import argparse
import json
from pathlib import Path, PurePosixPath
import tarfile
import tomllib
import zipfile


def archive_problems(names, *, source=False):
    problems = []
    for name in names:
        path = PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts:
            problems.append(name)
            continue
        parts = path.parts[1:] if source else path.parts
        if not parts:
            continue
        if (len(parts) == 3 and parts[:2] == ('hidden_lab', 'web') and path.name == 'index.html'
                or len(parts) == 4 and parts[:3] == ('hidden_lab', 'web', 'assets')
                and path.suffix in ('.js', '.css', '.svg', '.png', '.ico', '.woff', '.woff2')):
            continue
        if parts[0] == 'hidden_lab' and path.suffix == '.py':
            continue
        if source and parts[0] in ('tests', 'tools') and path.suffix == '.py':
            continue
        if source and len(parts) == 1 and parts[0] in ('LICENSE', 'THIRD_PARTY_NOTICES.md', 'README.md', 'README.it.md', 'pyproject.toml', 'MANIFEST.in', 'PKG-INFO', 'setup.cfg', 'CONTRIBUTING.md', 'CODE_OF_CONDUCT.md', 'SECURITY.md', 'CHANGELOG.md', 'ROADMAP.md', 'PRODUCT.md', 'DESIGN.md', 'CITATION.cff', 'constraints-ci.txt', 'Dockerfile', 'compose.yaml', 'compose.api.yaml', '.dockerignore', '.gitignore'):
            continue
        if source and parts[0] == 'docs' and path.suffix == '.md':
            continue
        if source and parts == ('docs', 'assets', 'zone.png'):
            continue
        if source and len(parts) == 2 and parts[0] == 'deploy' and path.name in (
                'Dockerfile.beta', 'compose.beta.yaml', 'compose.public.yaml', 'compose.chatgpt.yaml', 'compose.oauth-ready.yaml', 'zone.caddy', 'zone-maintenance.py',
                'zone-backup.service', 'zone-backup.timer', 'zone-health.service', 'zone-health.timer'):
            continue
        if source and parts[0] == '.github' and path.suffix in ('.md', '.yml'):
            continue
        if source and parts == ('examples', path.name) and path.name in ('operator-world.json', 'request.json', 'manual-session.txt', 'simulated-operator-input.txt'):
            continue
        if source and parts[0] == 'frontend':
            if len(parts) == 2 and path.name in ('package.json', 'pnpm-lock.yaml', 'pnpm-workspace.yaml', 'index.html', 'tsconfig.json', 'vite.config.ts'):
                continue
            if len(parts) == 3 and (parts[1] == 'scripts' and path.suffix == '.mjs' or parts[1] == 'src' and path.suffix in ('.ts', '.tsx', '.css')):
                continue
        if source and parts[0].endswith('.egg-info') and path.suffix in ('.txt', ''):
            continue
        if not source and parts[0].endswith('.dist-info') and (path.name in ('METADATA', 'WHEEL', 'RECORD', 'entry_points.txt', 'top_level.txt', 'LICENSE') or parts[1:] in (('licenses', 'LICENSE'), ('licenses', 'THIRD_PARTY_NOTICES.md'))):
            continue
        problems.append(name)
    return problems


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--archives', type=Path)
    parser.add_argument('--require-web', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    project = tomllib.loads((root/'pyproject.toml').read_text(encoding='utf-8'))['project']
    frontend = json.loads((root/'frontend/package.json').read_text(encoding='utf-8'))
    from hidden_lab import __version__
    assert project['version'] == frontend['version'] == __version__
    assert project['license'] == 'MIT' and project['license-files'] == ['LICENSE', 'THIRD_PARTY_NOTICES.md']
    assert 'MIT License' in (root/'LICENSE').read_text(encoding='utf-8')
    if args.archives:
        files = list(args.archives.glob('*.whl')) + list(args.archives.glob('*.tar.gz'))
        assert any(p.suffix == '.whl' for p in files) and any(p.name.endswith('.tar.gz') for p in files), 'Wheel e sdist richiesti'
        for path in files:
            if path.suffix == '.whl':
                with zipfile.ZipFile(path) as archive:
                    names = archive.namelist()
            else:
                with tarfile.open(path) as archive:
                    assert not any(m.issym() or m.islnk() for m in archive.getmembers())
                    names = [m.name for m in archive.getmembers() if m.isfile()]
            assert not archive_problems(names, source=path.suffix != '.whl'), f'Contenuto archivio inatteso: {path}'
            assert any(PurePosixPath(n).name == 'LICENSE' for n in names), 'Licenza mancante'
            if args.require_web:
                assert any(n.endswith('hidden_lab/web/index.html') for n in names), 'Interfaccia assente dalla release'
                assert any('hidden_lab/web/assets/' in n and n.endswith('.js') for n in names), 'Bundle JavaScript assente'
    print(f'Release {__version__}: versioni, MIT e confini degli archivi verificati.')


if __name__ == '__main__':
    main()
