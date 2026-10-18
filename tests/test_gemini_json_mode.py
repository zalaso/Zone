"""Explicit JSON mode compatibility: offline only, never an automatic fallback."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from hidden_lab.agent_contract import build_request
from hidden_lab.fake_client import demo_replies
from hidden_lab.gemini_client import GeminiClient, gemini_payload
from hidden_lab.investigation import Investigation
from hidden_lab.provider_base import AgentSettings
from hidden_lab.protocol import ValidationError
from hidden_lab.session import Session
from hidden_lab.terminal import Terminal
from test_agent import conclusion
from test_lab import config
from test_providers import FakeGeminiSDK, errors, gemini_response, httpx, sample_reply


class GeminiJsonPayloadTests(unittest.TestCase):
    def test_json_mode_delivers_same_public_contract_without_schema_constraint(self):
        with tempfile.TemporaryDirectory() as directory:
            request = build_request(Session(Path(directory) / 's', config('constant', 7.654321)).events,
                                    AgentSettings('offline-model'), 'choose_next', 8, 8)
        constrained = gemini_payload(request)
        payload = gemini_payload(request, output_mode='json')
        self.assertNotIn('response_json_schema', payload['config'])
        self.assertEqual(payload['config']['response_mime_type'], 'application/json')
        self.assertEqual(payload['config']['tools'], [])
        self.assertEqual(payload['config']['automatic_function_calling'], {'disable': True})
        content = json.loads(payload['contents'])
        self.assertEqual(content.pop('message_contract'), request.schema)
        self.assertEqual(content, json.loads(request.user_content()))
        self.assertEqual(payload['config']['system_instruction'], request.instructions)
        self.assertEqual(constrained['config']['response_json_schema'], request.schema)
        self.assertEqual(constrained['contents'], request.user_content())
        self.assertNotIn('7.654321', json.dumps(payload))
        self.assertNotIn('"seed"', json.dumps(payload))
        self.assertEqual(request.schema, constrained['config']['response_json_schema'])
        with self.assertRaises(ValidationError):
            gemini_payload(request, output_mode='automatic')

    def test_cli_refuses_json_mode_for_other_providers_before_network(self):
        command = [sys.executable, '-m', 'hidden_lab', 'investigate', '--provider', 'simulated',
                   '--config', 'examples/operator-world.json', '--session', 'sessions/unused-json-mode',
                   '--gemini-output-mode', 'json']
        result = subprocess.run(command, input='', text=True, capture_output=True,
                                env={**os.environ, 'PYTHONUTF8': '1'}, timeout=30)
        self.assertEqual(result.returncode, 1)
        self.assertIn('solo con Gemini', result.stderr)


@unittest.skipUnless(errors is not None, 'richiede extra gemini')
class GeminiJsonClientTests(unittest.TestCase):
    def test_real_sdk_serializes_json_mode_to_mock_http_without_schema_parameter(self):
        if httpx is None:
            self.skipTest('richiede HTTPX')
        from google import genai
        from google.genai import types
        seen = []
        def handler(request):
            self.assertEqual(request.url.host, 'generativelanguage.googleapis.com')
            body = json.loads(request.content)
            self.assertNotIn('responseJsonSchema', body['generationConfig'])
            self.assertNotIn('responseSchema', body['generationConfig'])
            self.assertEqual(body['generationConfig']['responseMimeType'], 'application/json')
            self.assertNotIn('secret-marker', request.content.decode())
            content = json.loads(body['contents'][0]['parts'][0]['text'])
            self.assertIn('message_contract', content)
            seen.append(body)
            return httpx.Response(200, json={'candidates': [{'finishReason': 'STOP',
                        'content': {'role': 'model', 'parts': [{'text': sample_reply()}]}}]})
        sdk = genai.Client(api_key='secret-marker', vertexai=False,
                           http_options=types.HttpOptions(timeout=7000,
                           retry_options=types.HttpRetryOptions(attempts=1),
                           client_args={'transport': httpx.MockTransport(handler), 'trust_env': False}))
        self.addCleanup(sdk.close)
        with patch.dict(os.environ, {'GEMINI_API_KEY': 'secret-marker'}):
            client = GeminiClient(AgentSettings('offline-model'), sdk=sdk, output_mode='json')
        with tempfile.TemporaryDirectory() as directory:
            request = build_request(Session(Path(directory) / 's', config()).events,
                                    AgentSettings('offline-model'), 'choose_next', 8, 8)
        self.assertEqual(client.complete(request).text, sample_reply())
        self.assertEqual(len(seen), 1)

    def test_complete_json_mode_cycle_with_modified_verification(self):
        replies = demo_replies()
        for index in (1, 3):
            replies[index]['experiment']['observation_interval'] = 0.5
        replies[3]['experiment']['duration'] = 0.5
        replies[4]['points'] = replies[4]['points'][::2]
        sdk = FakeGeminiSDK([gemini_response(text=json.dumps({'message': reply})) for reply in replies])
        with patch.dict(os.environ, {'GEMINI_API_KEY': 'secret-marker'}):
            client = GeminiClient(AgentSettings('offline-model'), sdk=sdk, output_mode='json')
        inputs = iter(['avvia', 'Iniziamo.', 'a', 'Esplorazione.', 'e', 'esegui',
                       'm', '', '', '', '', '1', '', 'conferma', 'Allungo la durata.', 'v', 'esegui'])
        with tempfile.TemporaryDirectory() as directory:
            session = Session(Path(directory) / 's', config())
            runner = Investigation(session, client, AgentSettings('offline-model', max_points=3),
                                   Terminal(lambda _: next(inputs), lambda _: None))
            self.assertTrue(runner.run())
            self.assertEqual(runner.calls, 6)
            self.assertEqual(session.executed_count, 2)
            context = json.loads(sdk.calls[4]['contents'])['next_action']
            self.assertEqual(context['approved_experiment']['duration'], 1)
            self.assertEqual(context['prediction_times'], [0, 0.5, 1])
            kinds = [event['message']['type'] for event in session.events]
            self.assertEqual(kinds.count('verification'), 1)
            self.assertEqual(kinds[-1], 'conclusion')
            for call in sdk.calls:
                self.assertNotIn('response_json_schema', call['config'])
                self.assertNotIn('secret-marker', json.dumps(call))

    def test_invalid_physical_request_is_still_rejected_and_mode_audited(self):
        invalid = {'message': {'type': 'experiment_request', 'request_id': 'bad', 'purpose': 'Misurare.',
                              'experiment': {'initial_position': {'x': 99, 'y': 0},
                                             'initial_velocity': {'x': 0, 'y': 0},
                                             'duration': 1, 'observation_interval': 0.5}}}
        sdk = FakeGeminiSDK([gemini_response(text=json.dumps(invalid)), gemini_response()])
        with patch.dict(os.environ, {'GEMINI_API_KEY': 'secret-marker'}):
            client = GeminiClient(AgentSettings('offline-model'), sdk=sdk, output_mode='json')
        with tempfile.TemporaryDirectory() as directory:
            session = Session(Path(directory) / 's', config())
            output = []
            runner = Investigation(session, client, AgentSettings('offline-model'), Terminal(lambda _: 'avvia', output.append))
            self.assertTrue(runner.run())
            self.assertEqual(runner.calls, 2)
            self.assertEqual(session.executed_count, 0)
            self.assertEqual(session.conclusion['summary'], conclusion()['summary'])
            for call in sdk.calls:
                self.assertNotIn('response_json_schema', call['config'])
                self.assertIn('message_contract', json.loads(call['contents']))
            settings = json.loads((session.directory / 'private/agent_settings.jsonl').read_text())
            self.assertEqual(settings['generation_settings']['output_mode'], 'json')
            self.assertFalse(settings['generation_settings']['response_json_schema'])
            for path in session.directory.rglob('*.jsonl'):
                self.assertNotIn('secret-marker', path.read_text(encoding='utf-8'))
