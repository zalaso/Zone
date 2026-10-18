"""The invited web deployment keeps credentials and application ports private."""
from pathlib import Path
import importlib.util
import unittest
from unittest.mock import patch

from tools.check_release import archive_problems
from tools.verify_hosted_beta import validate_origin, verify


class PublicBetaTests(unittest.TestCase):
    def test_smoke_requires_explicit_public_target_and_rejects_arbitrary_destinations(self):
        validate_origin('https://node.tail123.ts.net:8444')
        validate_origin('https://zone.example.org', public=True)
        for target in ('http://zone.example.org', 'https://other.example',
                       'https://zone.example.org@evil.example',
                       'https://zone.example.org/path',
                       'https://zone.example.org?key=secret'):
            with self.assertRaises(ValueError):
                validate_origin(target, public=True)
        with patch('tools.verify_hosted_beta.subprocess.run') as ssh:
            with self.assertRaises(ValueError):
                verify('https://zone.example.org', Path('unused'))
            ssh.assert_not_called()

    def test_fixture_credentials_never_leave_for_a_mismatched_server_origin(self):
        import json
        import tempfile
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as temp:
            with patch('tools.verify_hosted_beta.subprocess.run', return_value=SimpleNamespace(
                    returncode=0, stdout=json.dumps({'origin': 'https://different.example',
                        'accounts': {'member': {'login_key': 'PRIVATE_FIXTURE_SENTINEL'}}}))) as call:
                with self.assertRaisesRegex(ValueError, 'different from VPS') as raised:
                    verify('https://zone.example.org', Path(temp) / 'new', public=True)
                self.assertNotIn('PRIVATE_FIXTURE_SENTINEL', str(raised.exception))
                self.assertEqual(call.call_count, 1)  # SSH only; no browser or credentialed HTTP.

    @unittest.skipUnless(importlib.util.find_spec('yaml'), 'Installare extra dev')
    def test_public_proxy_has_private_upstream_bounded_runtime_and_no_provider(self):
        import yaml
        root = Path(__file__).resolve().parents[1]
        service = yaml.safe_load((root / 'deploy/compose.public.yaml').read_text())['services']['zone']
        self.assertEqual(service['ports'], ['127.0.0.1:8876:8765', '172.30.0.1:8877:8765'])
        self.assertTrue(service['read_only'])
        self.assertEqual(service['mem_limit'], '384m')
        self.assertEqual(service['memswap_limit'], '384m')
        self.assertEqual(service['cpus'], .5)
        self.assertIn('accounts', service['command'])
        self.assertNotIn('--local-cookies', service['command'])
        self.assertNotIn('--allow-real-agent', service['command'])
        self.assertNotIn('environment', service)
        caddy = (root / 'deploy/zone.caddy').read_text()
        for expected in ('zone.example.org', 'reverse_proxy 127.0.0.1:8767',
                         'max_size 64KB', 'max_conns_per_host 8'):
            self.assertIn(expected, caddy)
        self.assertNotIn('debug', caddy)
        self.assertNotIn('log {', caddy)

    def test_source_archive_keeps_only_public_proxy_configuration(self):
        self.assertEqual(archive_problems(['zone/deploy/zone.caddy',
                         'zone/deploy/compose.public.yaml'], source=True), [])
        self.assertTrue(archive_problems(['zone/deploy/compose.env'], source=True))
