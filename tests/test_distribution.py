"""Distribution checks must detect state loss without exporting private state."""
from contextlib import closing, redirect_stdout
import io
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from hidden_lab.backend_store import SQLiteRepository
from tools.verify_distribution import SNAPSHOT, clean_environment, http_read, new_output, public_report


class DistributionTests(unittest.TestCase):
    def test_fingerprint_detects_changed_rows_even_when_counts_match(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "zone.sqlite3"
            SQLiteRepository(path)
            with closing(sqlite3.connect(path)) as db:
                db.execute("INSERT INTO worlds VALUES('world','PRIVATE_TRUTH_SENTINEL','{}')")
                db.commit()
            def snapshot():
                output = io.StringIO()
                with patch('sys.argv', ['inspect', str(path)]), redirect_stdout(output):
                    exec(SNAPSHOT, {})
                return json.loads(output.getvalue())
            first = snapshot()
            with closing(sqlite3.connect(path)) as db:
                db.execute("UPDATE worlds SET record_json='CHANGED_PRIVATE_TRUTH'")
                db.commit()
            second = snapshot()
            self.assertEqual(first['counts'], second['counts'])
            self.assertNotEqual(first['fingerprint'], second['fingerprint'])
            first['sessions'] = ['PRIVATE_SESSION_ID']
            report = public_report('wheel', {'version':'test','provider_sdks_absent':True}, first)
            text = json.dumps(report)
            for private in ('fingerprint', first['fingerprint'], 'PRIVATE_SESSION_ID', 'PRIVATE_TRUTH_SENTINEL'):
                self.assertNotIn(private, text)

    def test_output_refuses_existing_directory_without_touching_data(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'owned'
            new_output(path)
            marker = path / 'keep.txt'
            marker.write_text('keep')
            with self.assertRaises(FileExistsError):
                new_output(path)
            self.assertEqual(marker.read_text(), 'keep')

    def test_children_do_not_inherit_provider_credentials_or_pythonpath(self):
        with patch.dict(os.environ, {'OPENAI_API_KEY':'secret', 'GEMINI_API_KEY':'secret',
                                     'ZONE_OPERATOR_TOKEN':'secret', 'PYTHONPATH':'checkout'}):
            env = clean_environment()
        for key in ('OPENAI_API_KEY','GEMINI_API_KEY','ZONE_OPERATOR_TOKEN','PYTHONPATH'):
            self.assertNotIn(key, env)
        self.assertEqual(env['ZONE_ENV'], 'local')

    def test_http_helper_rejects_nonlocal_routes(self):
        for path in ('https://example.com', '//example.com', 'relative'):
            with self.assertRaises(ValueError):
                http_read(1234, path)
