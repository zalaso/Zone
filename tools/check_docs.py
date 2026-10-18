"""Check repository-local Markdown links without uploading docs or contacting sites."""
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


def problems(root=ROOT):
    errors = []
    files = [*root.glob('*.md'), *root.glob('docs/**/*.md'), *root.glob('.github/**/*.md')]
    for path in files:
        text = re.sub(r'```[\s\S]*?```', '', path.read_text(encoding='utf-8'))
        for raw in re.findall(r'!?\[[^\]]*\]\(([^\n]+?)\)', text):
            target = raw.strip().strip('<>')
            if urlsplit(target).scheme or target.startswith(('#', '/')):
                continue
            target = unquote(target.split('#', 1)[0])
            if target and not (path.parent / target).exists():
                errors.append(path.relative_to(root).as_posix() + ': ' + target)
    return errors


if __name__ == '__main__':
    errors = problems()
    if errors:
        print('\n'.join(errors))
        raise SystemExit(1)
    print('Repository-local documentation links verified.')
