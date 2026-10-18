"""Official installation bootstrap: persistent data, owner access, public boundaries."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


@unittest.skipUnless(importlib.util.find_spec('fastapi') and importlib.util.find_spec('cryptography'), 'Extra workspace')
class WorkspaceStartTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.data = Path(self.temp.name) / 'private'
        self.web = Path(self.temp.name) / 'web'
        self.web.mkdir(); (self.web / 'index.html').write_text('<!doctype html><title>Test</title>', encoding='utf-8')

    def prepare(self, **kwargs):
        from hidden_lab.workspace_cli import prepare
        return prepare(self.data, origin='http://127.0.0.1:8767', static_dir=self.web, **kwargs)

    def test_bootstrap_is_idempotent_and_admin_is_not_first_registered_user(self):
        from fastapi.testclient import TestClient
        from hidden_lab.backend_store import SQLiteRepository
        from hidden_lab.identity_store import IdentityStore
        app = self.prepare()
        key = (self.data / 'admin-key.txt').read_text().strip()
        repo = SQLiteRepository(self.data / 'workspace.db')
        self.assertEqual(IdentityStore(repo).authenticate(key)['role'], 'admin')
        self.prepare()
        self.assertEqual((self.data / 'admin-key.txt').read_text().strip(), key)
        with repo._connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM worlds').fetchone()[0], 1)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM arena_challenges').fetchone()[0], 1)
        with TestClient(app, base_url='http://127.0.0.1:8767') as http:
            user = http.post('/v1/auth/register', headers={'Origin': 'http://127.0.0.1:8767'},
                             json={'handle': 'alice', 'password': 'synthetic-password-123'})
            self.assertEqual(user.status_code, 200)
            self.assertEqual(user.json()['account']['role'], 'member')
            for path in ('/admin-key.txt', '/workspace.db', '/connection.key'):
                self.assertEqual(http.get(path).status_code, 404)
            public = json.dumps(http.get('/v1/worlds').json())
            self.assertNotIn(key, public)
            self.assertNotIn('generator_seed', public)

    def test_personal_api_is_opt_in_and_master_key_is_persistent(self):
        from hidden_lab.workspace_cli import connection_key
        self.prepare()
        self.assertFalse((self.data / 'connection.key').exists())
        with patch.dict('os.environ', {'ZONE_CONNECTION_KEY': ''}):
            first = connection_key(self.data, True)
            self.assertEqual(connection_key(self.data, True), first)
            self.assertIsNone(connection_key(self.data, False))
        with patch.dict('os.environ', {'ZONE_CONNECTION_KEY': 'synthetic-environment-value'}):
            self.assertEqual(connection_key(self.data, True), 'synthetic-environment-value')
        self.assertEqual((self.data / 'connection.key').read_text().strip(), first)

    def test_missing_web_and_external_http_fail_before_creating_data(self):
        from argparse import Namespace
        from hidden_lab.workspace_cli import run_command
        args = Namespace(data=self.data, port=8767, max_accounts=100, host='127.0.0.1', container_local=False,
                         origin='http://public.example.org', web_dir=self.web, open_registration=False,
                         enable_personal_api=False)
        with self.assertRaises(ValueError):
            run_command(args)
        self.assertFalse(self.data.exists())
        args.origin = 'https://public.example.org'; args.web_dir = self.web / 'missing'
        with self.assertRaises(ValueError):
            run_command(args)
        self.assertFalse(self.data.exists())

    def test_credential_file_is_never_overwritten(self):
        from hidden_lab.workspace_cli import private_file
        target = Path(self.temp.name) / 'key'
        private_file(target, 'synthetic-first')
        with self.assertRaises(FileExistsError):
            private_file(target, 'synthetic-second')
        self.assertEqual(target.read_text().strip(), 'synthetic-first')


class PublicationGuardTests(unittest.TestCase):
    def test_unrelated_commands_do_not_resolve_workspace_home(self):
        from argparse import ArgumentParser
        from hidden_lab.workspace_cli import add_parser
        parser = ArgumentParser()
        commands = parser.add_subparsers(dest='command')
        commands.add_parser('other')
        with patch('pathlib.Path.home', side_effect=RuntimeError('No home directory')):
            add_parser(commands)
            self.assertEqual(parser.parse_args(['other']).command, 'other')
            self.assertIsNone(parser.parse_args(['workspace']).data)

    def test_rules_redact_values_and_allow_explicit_env_template(self):
        from tools.check_publication import content_problems, path_problems
        self.assertEqual(content_problems(b'ghp_' + b'A' * 36), ['github-token'])
        self.assertEqual(content_problems(b'zc_' + b'x' * 43), ['zone-credential'])
        self.assertEqual(content_problems(b'OPENAI_API_KEY=replace-locally'), [])
        self.assertTrue(path_problems('zone-data/admin-key.txt'))
        self.assertTrue(path_problems('.env.production'))
        self.assertFalse(path_problems('.env.example'))
