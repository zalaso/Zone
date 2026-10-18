"""Create a new deployment context without source trees, user data or credentials."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tarfile
import zipfile


def package(root, wheel, out):
    root, wheel, out = Path(root), Path(wheel), Path(out)
    if not wheel.is_file() or wheel.is_symlink():
        raise ValueError('A regular built wheel is required.')
    # Check the package content, not a source checkout or an arbitrary archive.
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        if not names or any(not (name.startswith('hidden_lab/') or
                name.startswith('hidden_physics_lab-') and '.dist-info/' in name) for name in names):
            raise ValueError('Unexpected wheel contents.')
        if any('..' in Path(name).parts or name.startswith('/') or '\\' in name for name in names):
            raise ValueError('Unsafe wheel member.')
    web = root / 'frontend/dist'
    if not (web / 'index.html').is_file():
        raise ValueError('Build and check the frontend before packaging.')
    allowed = {'.html', '.js', '.css', '.svg', '.png', '.ico', '.woff', '.woff2'}
    files = list(web.rglob('*'))
    if any(p.is_symlink() or (p.is_file() and p.suffix not in allowed) for p in files):
        raise ValueError('Unexpected static asset or symlink.')
    out.mkdir(parents=True, exist_ok=False)
    context = out / 'context'
    context.mkdir()
    (context / 'wheels').mkdir()
    shutil.copyfile(wheel, context / 'wheels' / wheel.name)
    shutil.copyfile(root / 'constraints-ci.txt', context / 'constraints-ci.txt')
    shutil.copyfile(root / 'deploy/Dockerfile.beta', context / 'Dockerfile')
    shutil.copytree(web, context / 'web')
    hashes = {p.relative_to(context).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted(context.rglob('*')) if p.is_file()}
    identity = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
    manifest = {'release_id': identity[:16], 'sha256': hashes, 'real_provider_enabled': False}
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    shutil.copyfile(root / 'deploy/compose.beta.yaml', out / 'compose.yaml')
    with tarfile.open(out / 'context.tar.gz', 'w:gz') as archive:
        for p in sorted(context.rglob('*')):
            if p.is_file():
                archive.add(p, arcname=p.relative_to(context).as_posix(), recursive=False)
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wheel', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(package(Path(__file__).resolve().parents[1], args.wheel, args.out), indent=2))
