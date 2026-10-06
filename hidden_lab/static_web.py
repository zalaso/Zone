"""Serve esclusivamente un bundle compilato, mai directory di sviluppo o dati."""

from pathlib import Path

from .protocol import ValidationError

EXTENSIONS = frozenset((".html", ".css", ".js", ".svg", ".png", ".ico", ".woff", ".woff2"))


def mount_web(app, directory):
    from fastapi.staticfiles import StaticFiles
    directory = Path(directory)
    if directory.is_symlink() or not (directory / "index.html").is_file():
        raise ValidationError("Directory web compilata con index.html richiesta.")
    for path in directory.rglob("*"):
        if path.is_symlink() or path.is_file() and path.suffix.lower() not in EXTENSIONS:
            raise ValidationError("Directory web non valida: ammessi solo asset pubblici compilati.")
    app.mount("/", StaticFiles(directory=directory, html=True, follow_symlink=False), name="web")
