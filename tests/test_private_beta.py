"""Deployment packaging and limits must not include unrelated local state."""
from pathlib import Path
import tempfile
import unittest
import zipfile

from tools.package_beta import package
from tools.check_release import archive_problems


class PrivateBetaTests(unittest.TestCase):
    def fixture(self, root):
        for name, text in {'frontend/dist/index.html': '<html></html>',
                           'frontend/dist/assets/app.js': 'console.log("ok")',
                           'deploy/Dockerfile.beta': 'FROM scratch',
                           'deploy/compose.beta.yaml': 'services: {}',
                           'constraints-ci.txt': '', '.env': 'SECRET=do-not-upload',
                           'benchmark_data/private.json': 'private truth'}.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        wheel = root / 'app.whl'
        with zipfile.ZipFile(wheel, 'w') as archive:
            archive.writestr('hidden_lab/__init__.py', '')
            archive.writestr('hidden_physics_lab-0.11.0.dist-info/METADATA', '')
        return wheel

    def test_only_built_package_and_static_assets_are_exported(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            wheel = self.fixture(root)
            manifest = package(root, wheel, root / 'release')
            self.assertEqual(set(manifest['sha256']), {'wheels/app.whl', 'constraints-ci.txt',
                             'Dockerfile', 'web/index.html', 'web/assets/app.js'})
            self.assertFalse(manifest['real_provider_enabled'])
            with self.assertRaises(FileExistsError):
                package(root, wheel, root / 'release')

    def test_unknown_static_assets_and_foreign_wheel_members_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            wheel = self.fixture(root)
            unexpected = root / 'frontend/dist/secrets.json'
            unexpected.write_text('secret')
            with self.assertRaises(ValueError):
                package(root, wheel, root / 'bad-static')
            unexpected.unlink()
            with zipfile.ZipFile(wheel, 'a') as archive:
                archive.writestr('benchmark_data/world.json', 'truth')
            with self.assertRaises(ValueError):
                package(root, wheel, root / 'bad-wheel')

    def test_private_beta_is_bounded_and_has_no_real_provider(self):
        import yaml
        root = Path(__file__).resolve().parents[1]
        service = yaml.safe_load((root / 'deploy/compose.beta.yaml').read_text())['services']['zone']
        self.assertEqual(service['ports'], ['127.0.0.1:8876:8765'])
        self.assertEqual(service['mem_limit'], service['memswap_limit'])
        self.assertLessEqual(service['cpus'], .5)
        self.assertLessEqual(service['pids_limit'], 64)
        self.assertTrue(service['read_only'])
        self.assertIn('accounts', service['command'])
        self.assertNotIn('--local-cookies', service['command'])
        self.assertNotIn('--allow-real-agent', service['command'])
        self.assertNotIn('environment', service)

    def test_source_release_accepts_only_named_deployment_files(self):
        self.assertEqual(archive_problems(['zone/deploy/Dockerfile.beta',
                         'zone/deploy/zone-backup.timer'], source=True), [])
        for name in ('zone/deploy/compose.env', 'zone/deploy/admin-initial.key',
                     'zone/deploy/smoke-accounts.json', 'zone/deploy/data/zone.sqlite3'):
            self.assertEqual(archive_problems([name], source=True), [name])
