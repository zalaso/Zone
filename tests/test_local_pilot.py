"""Regressions from the real CPU pilot; no real inference in the test suite."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from hidden_lab.agent_contract import build_request
from hidden_lab.anthropic_client import AnthropicClient
from hidden_lab.gemini_client import GeminiClient
from hidden_lab.llm import OpenAIClient
from hidden_lab.provider_base import AgentSettings
from hidden_lab.provider_factory import create_real_client
from hidden_lab.protocol import ValidationError
from hidden_lab.session import Session
from test_lab import config


class LocalPilotTests(unittest.TestCase):
    @unittest.skipUnless(importlib.util.find_spec('httpx'), 'richiede extra ollama')
    def test_extended_local_timeout_is_explicit_and_reaches_http_client(self):
        settings = AgentSettings('local-model', timeout=300)
        with patch('httpx.Client') as constructor:
            client = create_real_client('ollama', settings)
        self.assertEqual(constructor.call_args.kwargs['timeout'], 300)
        self.assertFalse(constructor.call_args.kwargs['trust_env'])
        self.assertEqual(client.generation_settings['timeout_seconds'], 300)
        self.assertEqual(client.generation_settings['retries'], 0)
        self.assertEqual(AgentSettings('local-model').timeout, 30)
        with self.assertRaises(ValidationError):
            AgentSettings('local-model', timeout=601)

    def test_remote_timeout_rejected_before_sdk_or_credentials(self):
        settings = AgentSettings('remote-model', timeout=300)
        with patch.dict('os.environ', {}, clear=True):
            for provider in ('openai', 'anthropic', 'gemini'):
                with self.subTest(provider=provider), self.assertRaisesRegex(ValidationError, '120'):
                    create_real_client(provider, settings)
            for constructor in (OpenAIClient, AnthropicClient, GeminiClient):
                with self.subTest(constructor=constructor), self.assertRaisesRegex(ValidationError, '120'):
                    constructor(settings)

    def test_sampling_constraint_comes_from_public_point_limit_only(self):
        with tempfile.TemporaryDirectory() as directory:
            session = Session(Path(directory) / 'session', config('constant', 7.654321))
            for limit in (2, 3, 9):
                request = build_request(session.events, AgentSettings('local-model', max_points=limit), 'choose_next', 8, 6)
                self.assertEqual(request.context['sampling_constraint'], {
                    'point_count': '1 + duration / observation_interval',
                    'max_duration_in_observation_intervals': limit - 1,
                    'duration_must_be_multiple_of_interval': True})
                raw = request.user_content()
                self.assertNotIn('7.654321', raw)
                self.assertNotIn('"seed"', raw)
                self.assertNotIn('"config"', raw)
                self.assertEqual(json.loads(raw)['next_action']['max_observation_points'], limit)
