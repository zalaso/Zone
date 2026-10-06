import unittest
from tools.check_release import archive_problems


class ReleaseTests(unittest.TestCase):
    def test_archive_projection_refuses_data_credentials_and_path_escape(self):
        for name in ('../hidden_lab/core.py', '/hidden_lab/core.py', 'benchmark_data/world.json', '.env', 'hidden_lab/world.private.json', 'hidden_lab/key.txt'):
            self.assertEqual(archive_problems([name]), [name])
        self.assertEqual(archive_problems(['hidden_lab/core.py', 'lab.dist-info/licenses/LICENSE']), [])
        self.assertEqual(archive_problems(['lab/hidden_lab/core.py', 'lab/tests/test_lab.py', 'lab/LICENSE'], source=True), [])
        self.assertTrue(archive_problems(['lab/benchmark_private/world.json'], source=True))
        self.assertEqual(archive_problems(['lab/examples/operator-world.json', 'lab/tools/check_release.py', 'lab/frontend/src/App.tsx'], source=True), [])
        self.assertTrue(archive_problems(['lab/examples/test.private.json', 'lab/frontend/dist/private.js'], source=True))
