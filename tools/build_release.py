"""Build audited wheel and source archives, including the compiled public UI."""
import argparse
from hashlib import sha256
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
ASSETS = {'.js', '.css', '.svg', '.png', '.ico', '.woff', '.woff2'}


def copy_web(source, destination):
    source, destination = Path(source), Path(destination)
    files = [p for p in source.rglob('*') if p.is_file()]
    if not (source / 'index.html').is_file() or any(p.is_symlink() for p in source.rglob('*')):
        raise ValueError('A compiled public frontend is required')
    for path in files:
        relative = path.relative_to(source)
        if relative != Path('index.html') and (relative.parts[0] != 'assets' or path.suffix not in ASSETS):
            raise ValueError('Unexpected frontend asset: ' + relative.as_posix())
    if destination.exists():
        # No recursive deletion or unverified moves. Remove only the old known asset files.
        for path in destination.rglob('*'):
            relative = path.relative_to(destination)
            if path.is_symlink() or path.is_file() and relative != Path('index.html') and (relative.parts[0] != 'assets' or path.suffix not in ASSETS):
                raise ValueError('Unexpected package asset; inspect manually: ' + str(relative))
        for path in destination.rglob('*'):
            if path.is_file():
                path.unlink()
    for path in files:
        target = destination / path.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=ROOT / 'dist')
    parser.add_argument('--skip-web-build', action='store_true', help='Use an already compiled and audited frontend')
    args = parser.parse_args()
    if not args.skip_web_build:
        pnpm = shutil.which('pnpm.cmd' if os.name == 'nt' else 'pnpm')
        if not pnpm:
            parser.error('Install Node.js and pnpm 10.28.0, or use --skip-web-build after an audited build')
        subprocess.run([pnpm, 'run', 'build'], cwd=ROOT / 'frontend', check=True)
    subprocess.run([shutil.which('node') or 'node', 'scripts/check-bundle.mjs'], cwd=ROOT / 'frontend', check=True)
    copy_web(ROOT / 'frontend' / 'dist', ROOT / 'hidden_lab' / 'web')
    args.out.mkdir(parents=True, exist_ok=True)
    if any(args.out.glob('*.whl')) or any(args.out.glob('*.tar.gz')):
        parser.error('Output must not contain previous release archives')
    subprocess.run([sys.executable, '-m', 'build', '--no-isolation', '--outdir', str(args.out.resolve())], cwd=ROOT, check=True)
    subprocess.run([sys.executable, 'tools/check_release.py', '--archives', str(args.out.resolve()), '--require-web'], cwd=ROOT, check=True)
    subprocess.run([sys.executable, 'tools/check_publication.py', '--no-worktree', '--archives', str(args.out.resolve())], cwd=ROOT, check=True)
    paths = sorted([*args.out.glob('*.whl'), *args.out.glob('*.tar.gz')])
    (args.out / 'SHA256SUMS').write_text(''.join(f'{sha256(p.read_bytes()).hexdigest()}  {p.name}\n' for p in paths), encoding='utf-8')
    print('Audited release archives and SHA256SUMS:', args.out)


if __name__ == '__main__':
    main()
