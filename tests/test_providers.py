import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

try:
    import httpx
except ImportError:
    httpx = None
try:
    import httpx2
    import anthropic
except ImportError:
    httpx2 = None
    anthropic = None
try:
    from google.genai import errors, types
except ImportError:
    errors = types = None

from hidden_lab.agent_contract import ModelRequest, build_request, openai_payload
from hidden_lab.anthropic_client import AnthropicClient, anthropic_payload
from hidden_lab.gemini_client import GeminiClient, gemini_payload
from hidden_lab.ollama_client import LOCAL_BASE, OllamaClient, ollama_payload
from hidden_lab.provider_base import AgentSettings, ProviderError
from hidden_lab.investigation import Investigation
from hidden_lab.session import Session
from hidden_lab.terminal import Terminal
from test_agent import conclusion
from test_lab import config

ROOT = Path(__file__).resolve().parents[1]


def sample_request(world="constant", gravity=7.654321):
    with tempfile.TemporaryDirectory() as temp:
        session = Session(Path(temp) / "session", config(world, gravity))
        return build_request(session.events, AgentSettings("offline-model"), "choose_next", 4, 3)


def sample_reply():
    return json.dumps({"message": conclusion()}, ensure_ascii=False)


def check_only_public(test, obj):
    raw = json.dumps(obj, ensure_ascii=False)
    for forbidden in ("7.654321", '"world"', '"gravity"', '"coefficient"', '"seed"',
                      "operator-world.json", "README.md", "manual-session.txt", "secret-marker"):
        test.assertNotIn(forbidden, raw)


class CanonicalRequestTests(unittest.TestCase):
    def test_same_canonical_request_translates_to_four_formats(self):
        request = sample_request()
        self.assertIsInstance(request, ModelRequest)
        native = {"openai": openai_payload(request), "anthropic": anthropic_payload(request),
                  "gemini": gemini_payload(request), "ollama": ollama_payload(request)}
        for provider, payload in native.items():
            with self.subTest(provider=provider):
                check_only_public(self, payload)
                if provider == "openai":
                    instructions, content, schema = payload["instructions"], payload["input"][0]["content"], payload["text"]["format"]["schema"]
                elif provider == "anthropic":
                    instructions, content, schema = payload["system"], payload["messages"][0]["content"], payload["output_config"]["format"]["schema"]
                elif provider == "gemini":
                    instructions, content, schema = payload["config"]["system_instruction"], payload["contents"], payload["config"]["response_json_schema"]
                else:
                    instructions, content, schema = payload["messages"][0]["content"], payload["messages"][1]["content"], payload["format"]
                self.assertEqual(instructions, request.instructions)
                self.assertEqual(content, request.user_content())
                self.assertEqual(schema, request.schema)
                self.assertEqual(payload["model"], request.model)
        self.assertEqual(native["anthropic"]["output_config"]["format"]["type"], "json_schema")
        self.assertEqual(native["gemini"]["config"]["response_mime_type"], "application/json")
        self.assertEqual(native["ollama"]["format"], request.schema)
        self.assertFalse(native["openai"]["store"])
        self.assertEqual(native["openai"]["tools"], [])
        self.assertNotIn("tools", native["anthropic"])
        self.assertEqual(native["gemini"]["config"]["tools"], [])
        self.assertNotIn("tools", native["ollama"])

    def test_contract_hashes_change_with_schema_and_instructions(self):
        request = sample_request()
        other = sample_request("height", 1.123456)
        self.assertEqual(request.contract_fingerprints(), other.contract_fingerprints())
        changed = ModelRequest(request.model, request.instructions + " nuovo", request.history, request.context,
                               request.allowed_types, request.schema, request.max_output_tokens)
        self.assertNotEqual(request.contract_fingerprints()["instructions_sha256"],
                            changed.contract_fingerprints()["instructions_sha256"])
        settings = AgentSettings("offline-model")
        with tempfile.TemporaryDirectory() as temp:
            session = Session(Path(temp) / "s", config())
            predict = build_request(session.events + [
                {"seq": 2, "actor": "agent", "message": {"type": "experiment_request", "request_id": "p", "purpose": "a", "experiment":
                 {"initial_position": {"x": 0, "y": 0}, "initial_velocity": {"x": 0, "y": 0}, "duration": 1, "observation_interval": 0.5}}},
                {"seq": 3, "actor": "operator", "message": {"type": "operator_decision", "request_id": "p", "action": "approve", "reason": "a"}}],
                settings, "predict", 4, 3)
        self.assertNotEqual(request.contract_fingerprints()["schema_sha256"], predict.contract_fingerprints()["schema_sha256"])


@unittest.skipUnless(httpx2 is not None and anthropic is not None, "richiede extra anthropic")
class AnthropicTests(unittest.TestCase):
    def client(self, handler):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "secret-marker"}):
            client = AnthropicClient(AgentSettings("offline-model", timeout=7), transport=httpx2.MockTransport(handler))
        self.addCleanup(client.close)
        return client

    def native(self, text=None, reason="end_turn"):
        return {"id": "msg_offline", "type": "message", "role": "assistant", "model": "claude-offline-snapshot",
                "content": [{"type": "text", "text": text or sample_reply()}],
                "stop_reason": reason, "stop_sequence": None,
                "usage": {"input_tokens": 30, "output_tokens": 11, "cache_read_input_tokens": 5,
                          "unknown_secret": "secret-marker"}}

    def test_actual_sdk_transport_translation_response_and_usage(self):
        seen = []
        def handler(req):
            seen.append(req)
            return httpx2.Response(200, json=self.native())
        client = self.client(handler)
        reply = client.complete(sample_request())
        self.assertEqual(len(seen), 1)
        self.assertEqual(str(seen[0].url), "https://api.anthropic.com/v1/messages")
        body = json.loads(seen[0].content)
        self.assertEqual(body, anthropic_payload(sample_request()))
        check_only_public(self, body)
        self.assertEqual(reply.text, sample_reply())
        self.assertEqual(reply.metadata["returned_model"], "claude-offline-snapshot")
        self.assertEqual(reply.metadata["usage"]["input_tokens"], 30)
        self.assertIsNone(reply.metadata["usage"]["total_tokens"])
        self.assertEqual(reply.metadata["provider_details"]["usage"]["cache_read_input_tokens"], 5)
        self.assertNotIn("secret-marker", json.dumps(reply.metadata))
        self.assertEqual(client.sdk.max_retries, 0)

    def test_status_errors_are_sanitized_and_not_retried(self):
        for status, expected in ((400, "request_rejected"), (401, "authentication"), (429, "rate_limit"), (500, "server_error")):
            requests = []
            def handler(req):
                requests.append(req)
                return httpx2.Response(status, json={"error": {"type": "api_error", "message": "secret-marker"}})
            with self.subTest(status=status):
                client = self.client(handler)
                with self.assertRaises(ProviderError) as error:
                    client.complete(sample_request())
                self.assertEqual(error.exception.code, expected)
                self.assertEqual(len(requests), 1)
                self.assertNotIn("secret-marker", str(error.exception))

    def test_timeout_and_incomplete(self):
        def timeout(req):
            raise httpx2.ReadTimeout("secret-marker", request=req)
        with self.assertRaises(ProviderError) as error:
            self.client(timeout).complete(sample_request())
        self.assertEqual(error.exception.code, "timeout")
        client = self.client(lambda req: httpx2.Response(200, json=self.native(reason="max_tokens")))
        reply = client.complete(sample_request())
        self.assertEqual(reply.issue, "incomplete_response")
        self.assertEqual(reply.text, "")

    def test_native_response_still_uses_zone_validation(self):
        bad = json.dumps({"message": {"type": "experiment_request", "request_id": "bad", "purpose": "Test",
                                      "experiment": {"initial_position": {"x": 99, "y": 0},
                                                     "initial_velocity": {"x": 0, "y": 0},
                                                     "duration": 1, "observation_interval": 0.5}}})
        texts = iter((bad, sample_reply()))
        client = self.client(lambda req: httpx2.Response(200, json=self.native(text=next(texts))))
        with tempfile.TemporaryDirectory() as temp:
            session = Session(Path(temp) / "s", config())
            run = Investigation(session, client, AgentSettings("offline-model"), Terminal(lambda _: "avvia", lambda _: None))
            self.assertTrue(run.run())
            self.assertEqual(run.calls, 2)
            self.assertEqual(session.executed_count, 0)
            self.assertEqual(sum(e["message"]["type"] == "protocol_error" for e in session.events), 1)
            self.assertNotIn("secret-marker", (session.directory / "private/model_calls.jsonl").read_text(encoding="utf-8"))


class FakeGeminiSDK:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []
        self.models = SimpleNamespace(generate_content=self.generate)

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        item = next(self.responses)
        if isinstance(item, Exception):
            raise item
        return item


def gemini_response(text=None, reason="STOP"):
    return types.GenerateContentResponse.model_validate({
        "response_id": "gemini-offline-id", "model_version": "gemini-offline-snapshot",
        "candidates": [{"finish_reason": reason, "content": {"parts": [{"text": text or sample_reply()}], "role": "model"}}],
        "usage_metadata": {"prompt_token_count": 17, "candidates_token_count": 8,
                           "total_token_count": 29, "thoughts_token_count": 4},
    })


@unittest.skipUnless(errors is not None and httpx is not None, "richiede extra gemini")
class GeminiTests(unittest.TestCase):
    def client(self, responses):
        sdk = FakeGeminiSDK(responses)
        with patch.dict(os.environ, {"GEMINI_API_KEY": "secret-marker"}):
            client = GeminiClient(AgentSettings("offline-model", timeout=7), sdk=sdk)
        return client, sdk

    def test_sdk_boundary_translation_usage_and_retry_settings(self):
        client, sdk = self.client([gemini_response()])
        reply = client.complete(sample_request())
        self.assertEqual(sdk.calls, [gemini_payload(sample_request())])
        check_only_public(self, sdk.calls)
        self.assertEqual(reply.text, sample_reply())
        self.assertEqual(reply.metadata["returned_model"], "gemini-offline-snapshot")
        self.assertIsNone(reply.metadata["usage"])
        self.assertEqual(reply.metadata["provider_details"]["usage"]["prompt_token_count"], 17)
        self.assertEqual(reply.metadata["provider_details"]["usage"]["thoughts_token_count"], 4)
        self.assertNotIn("secret-marker", json.dumps(reply.metadata))
        self.assertEqual(client.http_options.timeout, 7000)
        self.assertEqual(client.http_options.retry_options.attempts, 1)

    def test_error_codes_timeout_and_single_attempt(self):
        for status, expected in ((400, "request_rejected"), (401, "authentication"), (429, "rate_limit"), (500, "server_error")):
            with self.subTest(status=status):
                client, sdk = self.client([errors.APIError(status, {"error": "secret-marker"})])
                with self.assertRaises(ProviderError) as error:
                    client.complete(sample_request())
                self.assertEqual(error.exception.code, expected)
                self.assertEqual(len(sdk.calls), 1)
                self.assertNotIn("secret-marker", str(error.exception))
        client, sdk = self.client([httpx.ReadTimeout("secret-marker")])
        with self.assertRaises(ProviderError) as error:
            client.complete(sample_request())
        self.assertEqual(error.exception.code, "timeout")
        self.assertEqual(len(sdk.calls), 1)

    def test_nonstop_output_is_incomplete(self):
        client, _ = self.client([gemini_response(reason="MAX_TOKENS")])
        reply = client.complete(sample_request())
        self.assertEqual(reply.issue, "incomplete_response")
        self.assertEqual(reply.metadata["status"], "incomplete")

    def test_same_canonical_validation_after_gemini_response(self):
        bad = json.dumps({"message": {"type": "experiment_request", "request_id": "bad", "purpose": "Test",
                                      "experiment": {"initial_position": {"x": 99, "y": 0},
                                                     "initial_velocity": {"x": 0, "y": 0},
                                                     "duration": 1, "observation_interval": 0.5}}})
        sdk = FakeGeminiSDK([gemini_response(text=bad), gemini_response(text=sample_reply())])
        with patch.dict(os.environ, {"GEMINI_API_KEY": "secret-marker"}):
            client = GeminiClient(AgentSettings("offline-model"), sdk=sdk)
        output = []
        with tempfile.TemporaryDirectory() as temp:
            session = Session(Path(temp) / "s", config())
            run = Investigation(session, client, AgentSettings("offline-model"), Terminal(lambda _: "avvia", output.append))
            self.assertTrue(run.run())
            self.assertEqual(run.calls, 2)
            self.assertEqual(session.executed_count, 0)
            self.assertEqual(sum(e["message"]["type"] == "protocol_error" for e in session.events), 1)
            records = (session.directory / "private/model_calls.jsonl").read_text(encoding="utf-8")
            self.assertNotIn("secret-marker", records)
            self.assertEqual(sdk.calls[0]["config"]["response_json_schema"],
                             build_request(session.events[:1], AgentSettings("offline-model"), "choose_next", 9, 0).schema)


@unittest.skipUnless(httpx is not None, "richiede extra ollama")
class OllamaTests(unittest.TestCase):
    def client(self, handler):
        http = httpx.Client(transport=httpx.MockTransport(handler), trust_env=False)
        self.addCleanup(http.close)
        return OllamaClient(AgentSettings("local-model:latest", timeout=7), http_client=http)

    def test_local_preflight_translation_response_and_usage(self):
        seen = []
        def handler(req):
            seen.append(req)
            if req.url.path == "/api/tags":
                return httpx.Response(200, json={"models": [{"name": "local-model:latest"}]})
            return httpx.Response(200, json={"model": "local-model:latest", "done": True, "done_reason": "stop",
                                             "message": {"role": "assistant", "content": sample_reply()},
                                             "prompt_eval_count": 20, "eval_count": 7, "secret": "secret-marker"})
        client = self.client(handler)
        client.preflight("local-model:latest")
        request = sample_request()
        request = ModelRequest("local-model:latest", request.instructions, request.history, request.context,
                               request.allowed_types, request.schema, request.max_output_tokens)
        reply = client.complete(request)
        self.assertEqual([str(item.url) for item in seen], [LOCAL_BASE + "/api/tags", LOCAL_BASE + "/api/chat"])
        self.assertEqual(json.loads(seen[1].content), ollama_payload(request))
        check_only_public(self, json.loads(seen[1].content))
        self.assertEqual(reply.text, sample_reply())
        self.assertIsNone(reply.metadata["usage"])
        self.assertEqual(reply.metadata["provider_details"]["usage"]["eval_count"], 7)
        self.assertNotIn("secret-marker", json.dumps(reply.metadata))
        self.assertFalse(any("pull" in item.url.path for item in seen))

    def test_missing_service_or_model_stops_without_download(self):
        seen = []
        def offline(req):
            seen.append(req)
            raise httpx.ConnectError("secret-marker", request=req)
        client = self.client(offline)
        with self.assertRaises(ProviderError) as error:
            client.preflight("local-model:latest")
        self.assertEqual(error.exception.code, "service_unavailable")
        self.assertEqual(len(seen), 1)
        seen.clear()
        client = self.client(lambda req: (seen.append(req) or httpx.Response(200, json={"models": []})))
        with self.assertRaises(ProviderError) as error:
            client.preflight("local-model:latest")
        self.assertEqual(error.exception.code, "model_unavailable")
        self.assertEqual([req.url.path for req in seen], ["/api/tags"])

    def test_http_failures_timeout_and_incomplete(self):
        request = sample_request()
        for status, expected in ((400, "request_rejected"), (401, "authentication"), (429, "rate_limit"),
                                 (404, "model_unavailable"), (500, "server_error")):
            seen = []
            def handler(req):
                seen.append(req)
                return httpx.Response(status, text="secret-marker")
            with self.subTest(status=status):
                with self.assertRaises(ProviderError) as error:
                    self.client(handler).complete(request)
                self.assertEqual(error.exception.code, expected)
                self.assertNotIn("secret-marker", str(error.exception))
                self.assertEqual(len(seen), 1)
        def timeout(req):
            raise httpx.ReadTimeout("secret-marker", request=req)
        with self.assertRaises(ProviderError) as error:
            self.client(timeout).complete(request)
        self.assertEqual(error.exception.code, "timeout")
        reply = self.client(lambda req: httpx.Response(200, json={"model": "local-model:latest", "done": False})).complete(request)
        self.assertEqual(reply.issue, "incomplete_response")

    def test_cloud_model_is_rejected_before_service_access(self):
        with self.assertRaises(ValueError):
            OllamaClient(AgentSettings("remote:cloud"))

    def test_native_response_still_uses_zone_validation(self):
        bad = json.dumps({"message": {"type": "experiment_request", "request_id": "bad", "purpose": "Test",
                                      "experiment": {"initial_position": {"x": 99, "y": 0},
                                                     "initial_velocity": {"x": 0, "y": 0},
                                                     "duration": 1, "observation_interval": 0.5}}})
        texts = iter((bad, sample_reply()))
        def handler(req):
            if req.url.path == "/api/tags":
                return httpx.Response(200, json={"models": [{"name": "local-model:latest"}]})
            return httpx.Response(200, json={"model": "local-model:latest", "done": True,
                                             "message": {"content": next(texts)}, "secret": "secret-marker"})
        client = self.client(handler)
        with tempfile.TemporaryDirectory() as temp:
            session = Session(Path(temp) / "s", config())
            run = Investigation(session, client, AgentSettings("local-model:latest"), Terminal(lambda _: "avvia", lambda _: None))
            self.assertTrue(run.run())
            self.assertEqual(run.calls, 2)
            self.assertEqual(session.executed_count, 0)
            self.assertEqual(sum(e["message"]["type"] == "protocol_error" for e in session.events), 1)
            self.assertNotIn("secret-marker", (session.directory / "private/model_calls.jsonl").read_text(encoding="utf-8"))


class MultiProviderCliTests(unittest.TestCase):
    def test_primary_provider_flag_runs_simulated_cycle_and_writes_audit(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / "session"
            inputs = (ROOT / "examples/simulated-operator-input.txt").read_text(encoding="utf-8")
            result = subprocess.run([sys.executable, "-m", "hidden_lab", "investigate",
                                     "--provider", "simulated", "--config",
                                     str(ROOT / "examples/operator-world.json"), "--session", str(directory)],
                                    cwd=ROOT, input=inputs, capture_output=True, text=True,
                                    encoding="utf-8", env={**os.environ, "PYTHONUTF8": "1"}, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("CLIENT SIMULATO", result.stdout)
            self.assertIn("Fine: 6 chiamate, 6 turni validi, 2 esperimenti.", result.stdout)
            settings = json.loads((directory / "private/agent_settings.jsonl").read_text(encoding="utf-8"))
            self.assertEqual(settings["provider"], "simulated")
            calls = [json.loads(line) for line in (directory / "private/model_calls.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(calls), 12)
            self.assertTrue(all(item["provider"] == "simulated" for item in calls))
            self.assertTrue(all("schema_sha256" in item and "instructions_sha256" in item for item in calls))

    def test_provider_selection_and_missing_keys_do_not_create_session(self):
        for provider, key in (("openai", "OPENAI_API_KEY"), ("anthropic", "ANTHROPIC_API_KEY"),
                              ("gemini", "GEMINI_API_KEY")):
            if (provider == "openai" and httpx is None) or (provider == "anthropic" and anthropic is None) or (provider == "gemini" and errors is None):
                continue
            with tempfile.TemporaryDirectory() as temp, self.subTest(provider=provider):
                directory = Path(temp) / "session"
                env = {**os.environ, key: "", "PYTHONUTF8": "1"}
                result = subprocess.run([sys.executable, "-m", "hidden_lab", "investigate",
                                         "--provider", provider, "--model", "offline-model", "--config",
                                         str(ROOT / "examples/operator-world.json"), "--session", str(directory)],
                                        cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", timeout=30)
                self.assertEqual(result.returncode, 1)
                self.assertIn(key, result.stderr)
                self.assertFalse(directory.exists())

    def test_no_model_fails_before_session_or_calls(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / "s"
            env = {**os.environ, "ANTHROPIC_MODEL": "", "PYTHONUTF8": "1"}
            result = subprocess.run([sys.executable, "-m", "hidden_lab", "investigate", "--provider", "anthropic",
                                     "--config", str(ROOT / "examples/operator-world.json"), "--session", str(directory)],
                                    cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", timeout=30)
            self.assertEqual(result.returncode, 1)
            self.assertFalse(directory.exists())

    @unittest.skipUnless(httpx is not None, "richiede extra ollama")
    def test_ollama_preflight_failure_stays_local_and_does_not_change_public_protocol(self):
        output = []
        with tempfile.TemporaryDirectory() as temp:
            session = Session(Path(temp) / "s", config())
            client = self._unavailable_ollama()
            run = Investigation(session, client, AgentSettings("local-model:latest"), Terminal(lambda _: "avvia", output.append))
            self.assertFalse(run.run())
            self.assertEqual([e["message"]["type"] for e in session.events], ["apparatus"])
            self.assertIn("Errore locale Ollama", "\n".join(output))

    def _unavailable_ollama(self):
        def unavailable(req):
            raise httpx.ConnectError("secret-marker", request=req)
        client = OllamaClient(AgentSettings("local-model:latest"),
                              http_client=httpx.Client(transport=httpx.MockTransport(unavailable), trust_env=False))
        self.addCleanup(client.http.close)
        return client


if __name__ == "__main__":
    unittest.main()
