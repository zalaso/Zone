"""Conservative defaults must survive future deployment configuration edits."""
from pathlib import Path
import importlib.util
import re
import unittest


@unittest.skipUnless(importlib.util.find_spec('yaml'), 'Installare extra dev per YAML')
class DeploymentTests(unittest.TestCase):
    def test_compose_keeps_loopback_private_volume_and_restricted_runtime(self):
        import yaml
        root = Path(__file__).resolve().parents[1]
        compose = yaml.load((root/'compose.yaml').read_text(), Loader=yaml.BaseLoader)
        service = compose['services']['zone']
        self.assertTrue(all(re.fullmatch(r'127\.0\.0\.1:\d+:\d+', p) for p in service['ports']))
        self.assertEqual(service['read_only'], 'true')
        self.assertEqual(service['cap_drop'], ['ALL'])
        self.assertIn('no-new-privileges:true', service['security_opt'])
        self.assertIn('${ZONE_OPERATOR_TOKEN:?', service['environment']['ZONE_OPERATOR_TOKEN'])
        self.assertFalse(any('API_KEY' in name for name in service['environment']))
        self.assertEqual(service['volumes'], ['zone-data:/data'])

    def test_ci_is_offline_readonly_and_actions_pinned(self):
        import yaml
        root = Path(__file__).resolve().parents[1]
        raw = (root/'.github/workflows/ci.yml').read_text()
        workflow = yaml.load(raw, Loader=yaml.BaseLoader)
        self.assertEqual(workflow['permissions'], {'contents':'read'})
        self.assertEqual(set(workflow['on']), {'push','pull_request','workflow_dispatch'})
        self.assertNotRegex(raw, r'\$\{\{\s*secrets\s*[.\[]')
        self.assertNotIn('--allow-real-agent', raw)
        for job in workflow['jobs'].values():
            self.assertLessEqual(int(job['timeout-minutes']), 20)
            for step in job['steps']:
                if 'uses' in step:
                    self.assertRegex(step['uses'], r'^actions/[\w-]+@[a-f0-9]{40}$')
