"""Offline tests only: the launcher never contacts Google in this suite."""
from contextlib import redirect_stdout
import getpass
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import warnings

from hidden_lab.fake_client import SimulatedClient, demo_replies
from hidden_lab.provider_base import ModelReply, ProviderError
from hidden_lab.terminal import Terminal
from tools import free_gemini_pilot as pilot


class FreeGeminiPilotTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        previous = Path.cwd()
        os.chdir(directory.name)
        self.addCleanup(os.chdir, previous)
        self.addCleanup(patch.stopall)
        patch('tools.free_gemini_pilot.sys.stdin.isatty', return_value=True).start()
        patch('tools.free_gemini_pilot.importlib.util.find_spec', return_value=object()).start()
        self.output = io.StringIO()

    def test_blank_billing_confirmation_creates_nothing_and_never_reads_key(self):
        with patch('builtins.input', return_value=''), patch.object(pilot.getpass, 'getpass') as key, \
                patch.object(pilot, 'lab_main') as run, redirect_stdout(self.output):
            self.assertEqual(pilot.main(['--model', 'offline-model']), 2)
        key.assert_not_called()
        run.assert_not_called()
        self.assertEqual(list(Path.cwd().iterdir()), [])

    def test_noninteractive_input_is_refused_before_reading_or_calling(self):
        with patch('tools.free_gemini_pilot.sys.stdin.isatty', return_value=False), \
                patch('builtins.input') as answer, patch.object(pilot, 'lab_main') as run, redirect_stdout(self.output):
            self.assertEqual(pilot.main(['--model', 'offline-model']), 1)
        answer.assert_not_called()
        run.assert_not_called()

    def test_key_is_scoped_to_investigation_and_restored_even_on_failure(self):
        for previous in (None, 'previous-secret-marker'):
            for failure in (False, True):
                with self.subTest(previous=previous, failure=failure):
                    seen = []
                    def run(argv):
                        seen.append((argv, os.environ.get('GEMINI_API_KEY')))
                        if argv[0] == 'investigate' and failure:
                            raise RuntimeError('new-secret-marker')
                        return 0
                    env = {} if previous is None else {'GEMINI_API_KEY': previous}
                    with patch.dict(os.environ, env, clear=True), patch('builtins.input', return_value='free'), \
                            patch.object(pilot.getpass, 'getpass', return_value='new-secret-marker'), \
                            patch.object(pilot, 'lab_main', side_effect=run), redirect_stdout(self.output):
                        self.assertEqual(pilot.main(['--model', 'offline-model']), 1 if failure else 0)
                        self.assertEqual(os.environ.get('GEMINI_API_KEY'), previous)
                    self.assertEqual([row[0][0] for row in seen], ['forge', 'forge', 'investigate'])
                    self.assertEqual([row[1] for row in seen], [previous, previous, 'new-secret-marker'])
                    command = seen[-1][0]
                    self.assertNotIn('new-secret-marker', str(command))
                    self.assertEqual(command[command.index('--max-calls') + 1], '8')
                    self.assertEqual(command[command.index('--max-points') + 1], '3')
        self.assertNotIn('secret-marker', self.output.getvalue())
        self.assertTrue(all(path.name.startswith('pilot12-gemini-') for path in Path('benchmark_data').iterdir()))

    def test_getpass_echo_fallback_aborts_without_investigation(self):
        def unsafe_input(prompt):
            warnings.warn('Cannot hide input', getpass.GetPassWarning)
            self.fail('Echo fallback must never be reached')
        with patch('builtins.input', return_value='free'), \
                patch.object(pilot.getpass, 'getpass', side_effect=unsafe_input), \
                patch.object(pilot, 'lab_main', return_value=0) as run, redirect_stdout(self.output):
            self.assertEqual(pilot.main(['--model', 'offline-model']), 2)
        self.assertEqual([call.args[0][0] for call in run.call_args_list], ['forge', 'forge'])

    def test_full_launcher_cycle_with_distinct_simulated_client_and_fresh_world(self):
        replies = demo_replies()
        for index in (1, 3):
            replies[index]['experiment']['observation_interval'] = 0.5
        replies[4]['points'] = replies[4]['points'][::2]
        client = SimulatedClient(replies)
        answers = iter(['avvia', 'Iniziamo.', 'a', 'Misura esplorativa.', 'e', 'esegui',
                        'a', 'Verifica della previsione.', 'v', 'esegui'])
        terminal_output = []
        terminal = Terminal(lambda _: next(answers), terminal_output.append)
        with patch('builtins.input', return_value='free'), \
                patch.object(pilot.getpass, 'getpass', return_value='key-sentinel'), \
                patch('hidden_lab.provider_factory.create_real_client', return_value=client), \
                patch('hidden_lab.terminal.Terminal', return_value=terminal), \
                patch.dict(os.environ, {}, clear=True), redirect_stdout(self.output):
            self.assertEqual(pilot.main(['--model', 'offline-model']), 0, self.output.getvalue())
            self.assertNotIn('GEMINI_API_KEY', os.environ)
        session = next(Path('sessions').iterdir())
        events = [json.loads(line)['message'] for line in (session / 'public/events.jsonl').read_text().splitlines()]
        types = [message['type'] for message in events]
        self.assertEqual(types.count('observation'), 2)
        self.assertEqual(types[-1], 'conclusion')
        self.assertLess(types.index('prediction'), types.index('verification'))
        self.assertEqual(len(client.payloads), 6)
        self.assertIn('SIMULATO', '\n'.join(terminal_output))
        for path in Path.cwd().rglob('*'):
            if path.is_file():
                self.assertNotIn('key-sentinel', path.read_text(encoding='utf-8'))
        self.assertNotIn('key-sentinel', json.dumps(client.payloads))

    def test_diagnostic_is_single_call_without_world_and_preserves_error_category(self):
        cases = [('{"ok": true}', True, None),
                 (ProviderError('server_error'), False, 'server_error'),
                 ('raw-secret-canary', False, 'invalid_response'),
                 ('{"ok": 1}', False, 'invalid_response'),
                 (ModelReply('', {}, 'incomplete_response'), False, 'incomplete_response')]
        for reply, valid, error in cases:
            with self.subTest(error=error, valid=valid):
                client = SimulatedClient([reply])
                with patch('builtins.input', return_value='free'), \
                        patch.object(pilot.getpass, 'getpass', return_value='key-sentinel'), \
                        patch.object(pilot, 'create_real_client', return_value=client), \
                        patch.object(pilot, 'lab_main') as lab, \
                        patch.object(client, 'close') as close, \
                        patch.dict(os.environ, {}, clear=True), redirect_stdout(self.output):
                    self.assertEqual(pilot.main(['--model', 'offline-model', '--diagnostic']), 0 if valid else 2)
                    self.assertNotIn('GEMINI_API_KEY', os.environ)
                lab.assert_not_called()
                close.assert_called_once()
                self.assertEqual(len(client.payloads), 1)
                self.assertNotIn('apparatus', json.dumps(client.payloads))
        self.assertFalse(Path('sessions').exists())
        records = list(Path('benchmark_data').rglob('connectivity-result.json'))
        self.assertEqual(len(records), len(cases))
        for path, (_, valid, error) in zip(sorted(records, key=lambda p: p.stat().st_mtime_ns), cases):
            result = json.loads(path.read_text())
            self.assertEqual(result['provider'], 'simulated')
            self.assertEqual(result['valid'], valid)
            self.assertEqual(result['error_code'], error)
            self.assertTrue(result['diagnostic_only'])
            self.assertEqual(result['experiments'], 0)
            self.assertEqual(result['calls'], 1)
            self.assertNotIn('raw-secret-canary', path.read_text())
            self.assertNotIn('key-sentinel', path.read_text())
            self.assertEqual(sorted(item.name for item in path.parent.iterdir()), ['connectivity-result.json'])
        self.assertNotIn('key-sentinel', self.output.getvalue())


if __name__ == '__main__':
    unittest.main()
