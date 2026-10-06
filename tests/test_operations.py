"""Migrazioni, copie consistenti, recupero e osservabilità senza segreti o rete."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import importlib.util
import io
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from contextlib import redirect_stderr

from hidden_lab.backend_store import SQLiteRepository
from hidden_lab.migrations import (MIGRATIONS, SCHEMA_VERSION, check_database,
                                  connect_existing, migrate_connection)
from hidden_lab.operations import backup_database, restore_database, retention_status
from hidden_lab.protocol import ValidationError
from hidden_lab.schema_sql import CORE_SQL, ARENA_SQL, INTEGRITY_SQL


class OperationsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = self.root / "zone.sqlite3"

    def legacy(self):
        with closing(sqlite3.connect(self.db)) as db:
            db.executescript(CORE_SQL + ARENA_SQL + INTEGRITY_SQL)
            db.execute("INSERT INTO worlds VALUES(?,?,?)", ("wlegacy", '{"law":"PRIVATE_LAW_SENTINEL"}', '{}'))
            db.execute("INSERT INTO sessions(id,world_id,agent_token_hash) VALUES('slegacy','wlegacy','hash-only')")
            db.execute("INSERT INTO events VALUES('slegacy',1,'apparatus','{}')")
            db.execute("INSERT INTO integrity_packs VALUES('pack','{}','{}')")
            db.execute("INSERT INTO integrity_cases VALUES('wlegacy','pack','test','{}','{}',1)")
            db.execute("INSERT INTO integrity_flags VALUES('slegacy','known_law')")
            db.execute("INSERT INTO arena_agents(id,metadata_json,quotas_json,requests,invalid) VALUES('agent','{}','{}',7,2)")
            db.execute("INSERT INTO arena_tokens VALUES('token','agent','hashed-token',2000000000,1)")
            db.execute("INSERT INTO arena_rates VALUES('agent',0,15,9)")
            db.execute("INSERT INTO arena_receipts VALUES('agent','key-hash','route','body-hash',200,'{}')")
            db.commit()

    def rows(self, path):
        with closing(connect_existing(path)) as db:
            names = ('worlds','sessions','events','integrity_cases','integrity_flags','arena_tokens','arena_agents','arena_rates','arena_receipts')
            return {name: db.execute(f"SELECT * FROM {name}").fetchall() for name in names}

    def test_legacy_migration_preserves_every_record_and_restarts_idempotently(self):
        self.legacy()
        old = self.rows(self.db)
        self.assertEqual(check_database(self.db)["pending"], [1, 2])
        SQLiteRepository(self.db)
        self.assertEqual(self.rows(self.db), old)
        SQLiteRepository(self.db)
        self.assertEqual(self.rows(self.db), old)
        self.assertEqual(check_database(self.db)["schema_version"], SCHEMA_VERSION)
        with closing(connect_existing(self.db)) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0], 2)
            self.assertIsNotNone(db.execute("SELECT 1 FROM sqlite_master WHERE name='audit_by_principal'").fetchone())

    def test_core_only_legacy_and_concurrent_initialization(self):
        with closing(sqlite3.connect(self.db)) as db:
            db.executescript(CORE_SQL)
        with ThreadPoolExecutor(2) as pool:
            list(pool.map(lambda _: SQLiteRepository(self.db), range(2)))
        self.assertEqual(check_database(self.db)["pending"], [])

    def test_failed_migration_rolls_back_ddl_ledger_and_version(self):
        altered = MIGRATIONS[:1] + ((2, 'fail', 'CREATE TABLE temporary_change (id TEXT); SELECT * FROM missing_table;'),)
        with closing(sqlite3.connect(self.db)) as db:
            with patch('hidden_lab.migrations.MIGRATIONS', altered), self.assertRaises(sqlite3.Error):
                migrate_connection(db)
            self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall(), [])

    def test_foreign_key_failure_rolls_back_adoption(self):
        self.legacy()
        with closing(sqlite3.connect(self.db)) as db:
            db.execute("INSERT INTO events VALUES('orphan',1,'agent','{}')")
            db.commit()
        with self.assertRaises(ValidationError):
            SQLiteRepository(self.db)
        with closing(sqlite3.connect(self.db)) as db:
            self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT name FROM sqlite_master WHERE name='schema_migrations'").fetchall(), [])

    def test_future_schema_bad_columns_and_tampered_ledger_are_rejected(self):
        SQLiteRepository(self.db)
        with closing(sqlite3.connect(self.db)) as db:
            db.execute("PRAGMA user_version=999")
        with self.assertRaises(ValidationError):
            SQLiteRepository(self.db)
        with closing(sqlite3.connect(self.db)) as db:
            db.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
            db.execute("UPDATE schema_migrations SET checksum='altered' WHERE version=1")
            db.commit()
        with self.assertRaises(ValidationError):
            check_database(self.db)
        bad = self.root / 'unrelated.db'
        with closing(sqlite3.connect(bad)) as db:
            db.execute("CREATE TABLE worlds(id TEXT)")
        with self.assertRaises(ValidationError):
            SQLiteRepository(bad)

    def test_backup_includes_wal_and_restore_preserves_revocations_and_retirement(self):
        self.legacy()
        SQLiteRepository(self.db)
        with closing(sqlite3.connect(self.db)) as writer:
            writer.execute("PRAGMA journal_mode=WAL")
            writer.execute("UPDATE arena_agents SET requests=8 WHERE id='agent'")
            writer.commit()
            self.assertTrue(Path(str(self.db)+'-wal').exists())
            backup = self.root / 'backup.db'
            record = backup_database(self.db, backup)
            self.assertEqual(record['schema_version'], SCHEMA_VERSION)
            self.assertNotIn('PRIVATE_LAW_SENTINEL', json.dumps(record))
            restored = self.root / 'restored.db'
            restore_database(backup, restored)
            self.assertEqual(self.rows(self.db), self.rows(restored))
            self.assertEqual(self.rows(restored)['arena_agents'][0][4], 8)
            if os.name != 'nt':
                self.assertEqual(backup.stat().st_mode & 0o777, 0o600)

    def test_backup_omits_uncommitted_writes(self):
        self.legacy()
        SQLiteRepository(self.db)
        with closing(sqlite3.connect(self.db)) as writer:
            writer.execute("PRAGMA journal_mode=WAL")
            writer.execute("UPDATE arena_agents SET requests=99 WHERE id='agent'")
            backup = self.root / 'snapshot.db'
            backup_database(self.db, backup)
            self.assertEqual(self.rows(backup)['arena_agents'][0][4], 7)
            writer.rollback()

    def test_backup_timeout_and_failure_remove_only_new_outputs(self):
        SQLiteRepository(self.db)
        out = self.root / 'failed.db'
        with patch('hidden_lab.operations.time.monotonic', side_effect=[0,100]), self.assertRaises(ValidationError):
            backup_database(self.db, out, timeout=1)
        self.assertFalse(out.exists())
        self.assertFalse(Path(str(out)+'.manifest.json').exists())
        self.assertEqual(check_database(self.db)['pending'], [])

    def test_restore_tamper_overwrite_missing_and_manifest_guards(self):
        SQLiteRepository(self.db)
        backup = self.root / 'backup.db'
        backup_database(self.db, backup)
        existing = self.root / 'existing.db'
        existing.write_bytes(b'DO_NOT_OVERWRITE')
        with self.assertRaises(ValidationError):
            restore_database(backup, existing)
        self.assertEqual(existing.read_bytes(), b'DO_NOT_OVERWRITE')
        with self.assertRaises(ValidationError):
            backup_database(self.db, backup)
        with backup.open('ab') as stream:
            stream.write(b'tamper')
        with self.assertRaises(ValidationError):
            restore_database(backup, self.root/'new.db')
        self.assertFalse((self.root/'new.db').exists())
        missing = self.root/'missing.db'
        with self.assertRaises(ValidationError):
            check_database(missing)
        self.assertFalse(missing.exists())

    def test_retention_is_readonly_and_reports_usage_without_truth(self):
        self.legacy()
        SQLiteRepository(self.db)
        old = self.rows(self.db)
        report = retention_status(self.db)
        self.assertEqual(report['deleted'], 0)
        self.assertEqual(report['rows']['arena_receipts'], 1)
        self.assertEqual(self.rows(self.db), old)
        self.assertNotIn('PRIVATE_LAW_SENTINEL', json.dumps(report))

    def test_legacy_schema_with_removed_constraints_is_not_adopted(self):
        for altered in (CORE_SQL.replace('world_id TEXT NOT NULL REFERENCES worlds(id)', 'world_id TEXT NOT NULL') + ARENA_SQL,
                        CORE_SQL + ARENA_SQL.replace('hash TEXT NOT NULL UNIQUE', 'hash TEXT NOT NULL')):
            path = self.root/f'incompatible-{len(list(self.root.iterdir()))}.db'
            with closing(sqlite3.connect(path)) as db:
                db.executescript(altered + INTEGRITY_SQL)
            with self.assertRaises(ValidationError):
                SQLiteRepository(path)
            with closing(sqlite3.connect(path)) as db:
                self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], 0)
                self.assertIsNone(db.execute("SELECT 1 FROM sqlite_master WHERE name='schema_migrations'").fetchone())

    def test_manifest_types_and_cli_database_errors_are_rejected_safely(self):
        from hidden_lab.cli import main
        SQLiteRepository(self.db)
        backup = self.root/'backup.db'
        record = backup_database(self.db, backup)
        proof = Path(str(backup)+'.manifest.json')
        for field, value in (('backup_version', True), ('schema_version', True), ('created_at', '2026-10-06'), ('sha256', 3)):
            proof.write_text(json.dumps({**record, field:value}), encoding='utf-8')
            with self.assertRaises(ValidationError):
                restore_database(backup, self.root/'new.db')
            self.assertFalse((self.root/'new.db').exists())
        broken = self.root/'broken.db'
        broken.write_bytes(b'PRIVATE_SENTINEL_NOT_A_DATABASE')
        output = io.StringIO()
        with redirect_stderr(output):
            self.assertEqual(main(['ops', 'status', '--db', str(broken)]), 1)
        self.assertNotIn('PRIVATE_', output.getvalue())
        self.assertNotIn('Traceback', output.getvalue())

    def test_serve_requires_loopback_or_explicit_container_and_real_agent_optin(self):
        from hidden_lab.cli import main
        for flags in (['--host','0.0.0.0'], ['--agent-provider','openai'], ['--agent-model','unconfigured'], ['--allow-real-agent']):
            with patch.dict(os.environ, {'ZONE_OPERATOR_TOKEN':'operation-tests-token-long-enough-123'}), patch('hidden_lab.provider_factory.create_real_client') as provider, patch('uvicorn.run') as server, redirect_stderr(io.StringIO()):
                self.assertEqual(main(['serve','--db',str(self.db), *flags]), 1)
                provider.assert_not_called()
                server.assert_not_called()
        self.assertFalse(self.db.exists())


@unittest.skipUnless(importlib.util.find_spec('fastapi') is not None, 'Installare extra backend')
class RuntimeTests(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        from hidden_lab.backend import create_app
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = self.root/'zone.db'
        self.app = create_app(self.db, operator_token='offline-only-operation-tests-12345678')
        self.client = TestClient(self.app)
        self.addCleanup(self.client.close)

    def test_health_checks_are_public_readonly_and_never_call_a_model(self):
        with patch('hidden_lab.web_agent.OfflineLabClient.complete') as model:
            self.assertEqual(self.client.get('/health/live').status_code, 200)
            result = self.client.get('/health/ready')
            self.assertEqual(result.status_code, 200)
            self.assertEqual(set(result.json()), {'status','zone_version','schema_version'})
            model.assert_not_called()
        self.db.rename(self.root/'offline.db')
        self.assertEqual(self.client.get('/health/ready').status_code, 503)
        self.assertFalse(self.db.exists())
        self.assertEqual(self.client.get('/health/live').status_code, 200)

    def test_future_or_missing_schema_is_not_ready(self):
        with closing(sqlite3.connect(self.db)) as db:
            db.execute('PRAGMA user_version=999')
        self.assertEqual(self.client.get('/health/ready').json(), {'status':'unavailable'})

    def test_missing_arena_table_is_not_ready(self):
        with closing(sqlite3.connect(self.db)) as db:
            db.execute('DROP TABLE arena_receipts')
        self.assertEqual(self.client.get('/health/ready').status_code, 503)

    def test_logs_and_unhandled_errors_contain_only_positive_fields(self):
        @self.app.get('/test/error')
        async def error():
            raise RuntimeError('PRIVATE_LAW_AND_TOKEN_SENTINEL')
        with self.assertLogs('zone.operations', level='INFO') as captured:
            response = self.client.get('/test/error?secret=PRIVATE_QUERY_SENTINEL', headers={'X-Zone-Token':'PRIVATE_TOKEN_SENTINEL'})
            self.client.get('/PRIVATE_PATH_SENTINEL')
        self.assertEqual(response.status_code, 500)
        self.assertNotIn('PRIVATE_', response.text + '\n'.join(captured.output))
        self.assertEqual(len(response.headers['X-Zone-Request-Id']), 24)
        for record in captured.records:
            self.assertEqual(set(json.loads(record.getMessage())), {'event','request_id','method','route','status','duration_ms'})

    def test_rate_rejections_also_have_safe_log_and_security_headers(self):
        from fastapi.testclient import TestClient
        from hidden_lab.backend import RateLimiter, create_app
        client = TestClient(create_app(self.db, operator_token='offline-only-operation-tests-12345678', rate_limiter=RateLimiter(read=1)))
        self.addCleanup(client.close)
        with self.assertLogs('zone.operations',level='INFO') as captured:
            client.get('/health/live')
            response = client.get('/health/live')
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.headers['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(len(captured.records), 2)

    def test_built_web_and_api_share_origin_without_exposing_private_files(self):
        from fastapi.testclient import TestClient
        from hidden_lab.backend import create_app
        web = self.root/'web'
        web.mkdir()
        (web/'index.html').write_text('<!doctype html><title>Zone</title>',encoding='utf-8')
        (web/'public.js').write_text('console.log("Zone")',encoding='utf-8')
        (self.root/'private.json').write_text('PRIVATE_SENTINEL',encoding='utf-8')
        client = TestClient(create_app(self.db, operator_token='offline-only-operation-tests-12345678', static_dir=web))
        self.addCleanup(client.close)
        self.assertEqual(client.get('/').status_code,200)
        self.assertEqual(client.get('/public.js').status_code,200)
        self.assertEqual(client.get('/health/ready').status_code,200)
        self.assertEqual(client.get('/v1/unknown').status_code,404)
        self.assertEqual(client.get('/private.json').status_code,404)
        csp = client.get('/').headers['Content-Security-Policy']
        self.assertNotIn('unsafe-inline',csp)
        (web/'private.json').write_text('{}',encoding='utf-8')
        with self.assertRaises(ValidationError):
            create_app(self.db, operator_token='offline-only-operation-tests-12345678', static_dir=web)
