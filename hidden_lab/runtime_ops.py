"""Telemetria a lista positiva: nessun corpo, header, query o eccezione privata."""

import json
import logging
import secrets
import time

from fastapi.responses import JSONResponse

from . import __version__
from .backend_store import SQLiteRepository
from .migrations import SCHEMA_VERSION, connect_existing, schema_status
from .protocol import ValidationError
from contextlib import closing
import sqlite3

LOGGER = logging.getLogger("zone.operations")


def configure_logging():
    if not LOGGER.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        LOGGER.addHandler(handler)
    LOGGER.setLevel(logging.INFO)
    LOGGER.propagate = False


def install_operations(app, repository):
    @app.middleware("http")
    async def telemetry(request, call_next):
        request_id, started = secrets.token_hex(12), time.monotonic()
        try:
            response = await call_next(request)
        except Exception:
            # Exception text can contain credentials or physical truth. Never format it.
            response = JSONResponse({"detail": "Errore interno; rileggi lo stato prima di proseguire."}, status_code=500)
        route = request.scope.get("route")
        record = {"event": "http_request", "request_id": request_id, "method": request.method,
                  "route": getattr(route, "path", None) or "unmatched", "status": response.status_code,
                  "duration_ms": round((time.monotonic()-started)*1000, 3)}
        LOGGER.info(json.dumps(record, allow_nan=False))
        response.headers["X-Zone-Request-Id"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
            "font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; "
            "frame-ancestors 'none'; form-action 'self'")
        return response

    @app.get("/health/live")
    async def live():
        return {"status": "ok", "zone_version": __version__}

    @app.get("/health/ready")
    async def ready():
        try:
            if not isinstance(repository, SQLiteRepository):
                raise ValidationError("Readiness non disponibile per questo repository.")
            # Read-only: deleting a database must never recreate an empty ready database.
            with closing(connect_existing(repository.path)) as db:
                status = schema_status(db)
                if status["schema_version"] != SCHEMA_VERSION:
                    raise ValidationError("Migrazioni pendenti.")
                db.execute("SELECT id FROM worlds LIMIT 1").fetchone()
                db.execute("SELECT seq FROM events LIMIT 1").fetchone()
                db.execute("SELECT key_hash FROM arena_receipts LIMIT 1").fetchone()
                db.execute("SELECT id FROM integrity_cases LIMIT 1").fetchone()
        except (ValidationError, sqlite3.Error, OSError):
            return JSONResponse({"status": "unavailable"}, status_code=503)
        return {"status": "ready", "zone_version": __version__, "schema_version": SCHEMA_VERSION}
