import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from hidden_lab.agent_contract import build_payload, response_schema
from hidden_lab.fake_client import SimulatedClient, demo_replies
from hidden_lab.investigation import Investigation
from hidden_lab.llm import AgentSettings, ModelReply, OpenAIClient, ProviderError
from hidden_lab.protocol import ValidationError, validate_message
from hidden_lab.session import Session
from hidden_lab.terminal import Terminal
from test_lab import config, decision, experiment, hypothesis, prediction, request

try:
    import httpx
    import openai
except ImportError:
    httpx = openai = None

ROOT = Path(__file__).resolve().parents[1]


def conclusion(hypothesis_id=None, evidence=None):
    return {"type": "conclusion", "final_hypothesis_id": hypothesis_id, "summary": "Le informazioni restano insufficienti.",
            "evidence": evidence or [], "limits": ["Campione limitato."], "alternatives": ["Altre dipendenze non escluse."]}


class AgentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.session = Session(Path(self.temp.name) / "private-name-canary", config("constant", 7.123456789))
        self.settings = AgentSettings(model="test-model")
        self.output = []

    def run_agent(self, replies, inputs, settings=None):
        iterator = iter(inputs)
        def read(prompt):
            self.output.append(prompt)
            try:
                return next(iterator)
            except StopIteration:
                raise EOFError()
        client = SimulatedClient(replies)
        runner = Investigation(self.session, client, settings or self.settings, Terminal(read, self.output.append))
        # Ogni tentativo involontario di accesso alla rete fallisce nei test del ciclo.
        with patch.object(socket.socket, "connect", side_effect=AssertionError("Rete vietata nel test")):
            runner.run()
        return runner, client

    def messages(self, kind):
        return [e["message"] for e in self.session.events if e["message"]["type"] == kind]

    def test_complete_cycle_question_modification_prediction_and_conclusion(self):
        replies = demo_replies()
        # La richiesta originale differisce dalla modifica umana: il client deve vederla.
        replies[3]["experiment"]["duration"] = 0.5
        inputs = ["avvia", "Un lancio breve va bene.", "a", "Prima esplorazione.", "e", "esegui",
                  "m", "", "", "", "", "1", "", "conferma", "Allungo la durata.", "v", "esegui"]
        runner, client = self.run_agent(replies, inputs)
        self.assertEqual(self.session.executed_count, 2)
        self.assertEqual(runner.calls, 6)
        self.assertIsNotNone(self.session.conclusion)
        self.assertEqual(len(self.messages("operator_answer")), 1)
        request_context = json.loads(client.payloads[4]["input"][0]["content"])
        self.assertEqual(request_context["next_action"]["approved_experiment"]["duration"], 1)
        self.assertEqual(request_context["next_action"]["prediction_times"], [0, 0.25, 0.5, 0.75, 1])
        kinds = [e["message"]["type"] for e in self.session.events]
        self.assertLess(kinds.index("prediction"), kinds.index("verification"))
        self.assertEqual([m["mode"] for m in self.messages("execution_mode")], ["exploration", "verification"])
        self.assertIn("Conclusione", "\n".join(self.output))

    def test_rejected_request_reaches_agent_without_execution(self):
        _, client = self.run_agent([request(), conclusion()], ["avvia", "r", "Preferisco un altro lancio."])
        self.assertEqual(self.session.executed_count, 0)
        history = json.loads(client.payloads[1]["input"][0]["content"])["history"]
        self.assertEqual(history[-1]["message"]["action"], "reject")

    def test_malformed_response_gets_bounded_correction_and_no_raw_echo(self):
        runner, client = self.run_agent(["malformed-private-canary", conclusion()], ["avvia"])
        self.assertEqual(runner.calls, 2)
        self.assertEqual(runner.turns, 1)
        self.assertEqual(len(self.messages("protocol_error")), 1)
        self.assertIn("protocol_error", client.payloads[1]["input"][0]["content"])
        self.assertNotIn("malformed-private-canary", json.dumps(client.payloads))
        for path in self.session.directory.rglob("*.jsonl"):
            self.assertNotIn("malformed-private-canary", path.read_text(encoding="utf-8"))

    def test_invalid_correction_limit_stops(self):
        runner, _ = self.run_agent(["bad", "bad", conclusion()], ["avvia"], AgentSettings("test", max_corrections=1))
        self.assertEqual(runner.calls, 2)
        self.assertEqual(self.messages("investigation_stopped")[-1]["reason"], "invalid_response_limit")

    def test_call_budget_counts_invalid_and_network_attempts(self):
        runner, _ = self.run_agent(["bad", conclusion()], ["avvia"], AgentSettings("test", max_calls=1))
        self.assertEqual(runner.calls, 1)
        self.assertEqual(self.session.executed_count, 0)
        self.assertEqual(self.messages("investigation_stopped")[-1]["reason"], "call_budget")

    def test_turn_limit_counts_accepted_messages(self):
        runner, _ = self.run_agent([hypothesis(), conclusion()], ["avvia"], AgentSettings("test", max_turns=1))
        self.assertEqual(runner.turns, 1)
        self.assertEqual(self.messages("investigation_stopped")[-1]["reason"], "turn_limit")

    def test_input_limit_stops_before_call(self):
        runner, _ = self.run_agent([conclusion()], ["avvia"], AgentSettings("test", max_input_bytes=1000))
        self.assertEqual(runner.calls, 0)
        self.assertEqual(self.messages("investigation_stopped")[-1]["reason"], "input_limit")

    def test_empty_input_and_eof_never_approve(self):
        runner, _ = self.run_agent([request()], ["avvia", "", ""])
        self.assertEqual(self.session.executed_count, 0)
        self.assertEqual(len(self.messages("operator_decision")), 0)
        self.assertEqual(runner.calls, 1)

    def test_empty_final_confirmation_never_executes(self):
        self.run_agent([request()], ["avvia", "a", "Va bene.", "e", ""])
        self.assertEqual(self.session.executed_count, 0)
        self.assertEqual(self.messages("investigation_stopped")[-1]["reason"], "operator_stop")

    def test_no_start_confirmation_means_no_model_calls(self):
        runner, _ = self.run_agent([conclusion()], [""])
        self.assertEqual(runner.calls, 0)

    def test_network_error_after_observation_does_not_repeat_experiment(self):
        runner, _ = self.run_agent([request(), ProviderError("timeout"), request("e2")],
                                   ["avvia", "a", "Va bene.", "e", "esegui"])
        self.assertEqual(self.session.executed_count, 1)
        self.assertEqual(runner.calls, 2)
        self.assertEqual(len(self.messages("execution_started")), 1)
        self.assertEqual(self.messages("investigation_stopped")[-1]["reason"], "provider_error")

    def test_model_cannot_send_operator_decision_or_execute(self):
        runner, _ = self.run_agent([decision(), {"type": "run", "request_id": "e1"}, conclusion()], ["avvia"])
        self.assertEqual(runner.calls, 3)
        self.assertEqual(self.session.executed_count, 0)
        self.assertFalse(self.messages("operator_decision"))

    def test_verification_needs_prediction_and_can_end_insufficient(self):
        self.run_agent([request(), conclusion()], ["avvia", "a", "Verifichiamo.", "v"])
        self.assertEqual(self.session.executed_count, 0)
        self.assertIsNone(self.session.conclusion["final_hypothesis_id"])
        self.assertEqual(self.session.requests["e1"]["status"], "cancelled")

    def test_invalid_prediction_cannot_trigger_execution(self):
        bad_prediction = prediction()
        bad_prediction["points"] = bad_prediction["points"][:-1]
        self.run_agent([hypothesis(), request(), bad_prediction, conclusion()],
                       ["avvia", "a", "Verifichiamo.", "v"])
        self.assertEqual(self.session.executed_count, 0)
        self.assertFalse(self.messages("prediction"))

    def test_point_limit_is_applied_before_operator_approval(self):
        self.run_agent([request(settings=experiment(duration=1, interval=0.05)), conclusion()], ["avvia"])
        self.assertFalse(self.messages("experiment_request"))
        self.assertEqual(self.session.executed_count, 0)

    def test_usage_is_logged_even_for_invalid_response(self):
        reply = ModelReply("bad", {"response_id": "test-response", "returned_model": "test-snapshot",
                                   "status": "completed", "usage": {"input_tokens": 100, "output_tokens": 2, "total_tokens": 102}})
        self.run_agent([reply, conclusion()], ["avvia"])
        logs = [json.loads(line) for line in (self.session.directory / "private/model_calls.jsonl").read_text().splitlines()]
        invalid = next(item for item in logs if item["outcome"] == "invalid_response")
        self.assertEqual(invalid["usage"]["total_tokens"], 102)
        self.assertEqual(invalid["returned_model"], "test-snapshot")

    def test_payload_omits_private_files_environment_and_recursive_metadata(self):
        self.session.events[0]["message"]["private_extra"] = "hidden-metadata-canary"
        self.session.events[0]["message"]["limits"]["secret"] = "nested-private-canary"
        self.session.events[0]["trace"] = "trace-canary"
        self.session.events.append({"seq": 2, "actor": "apparatus", "message": {"type": "private_evaluation", "world": "private-event-canary"}})
        with patch.dict(os.environ, {"OPENAI_API_KEY": "credential-canary", "OTHER_SECRET": "environment-canary"}):
            payload = build_payload(self.session.events, self.settings, "choose_next", 20, 15)
        encoded = json.dumps(payload)
        for secret in ("7.123456789", "hidden-metadata-canary", "nested-private-canary", "trace-canary",
                       "private-event-canary", "credential-canary", "environment-canary", "private-name-canary",
                       "README", "manual-session", "linear_drag", "quadratic_drag", '"gravity"', '"world"', '"seed"'):
            self.assertNotIn(secret, encoded)
        self.assertEqual(payload["tools"], [])
        self.assertFalse(payload["store"])
        self.assertEqual(set(payload), {"model", "instructions", "input", "text", "max_output_tokens", "store", "tools", "truncation"})
        self.assertNotIn("previous_response_id", payload)

    def test_public_payload_is_equal_for_different_hidden_worlds_before_measurement(self):
        other = Session(Path(self.temp.name) / "other", config("quadratic_drag", 17.345, 0.7123))
        self.assertEqual(build_payload(self.session.events, self.settings, "choose_next", 20, 15),
                         build_payload(other.events, self.settings, "choose_next", 20, 15))

    def test_question_and_conclusion_references_are_validated(self):
        with self.assertRaises(ValidationError):
            self.session.submit({"type": "operator_answer", "question_id": "missing", "answer": "Test"}, actor="operator")
        with self.assertRaises(ValidationError):
            self.session.submit(conclusion("missing"))
        with self.assertRaises(ValidationError):
            self.session.submit(conclusion(evidence=["future"]))
        self.session.submit(conclusion())
        with self.assertRaises(ValidationError):
            self.session.submit(request())

    def test_manual_mode_cannot_run_verification_without_prediction(self):
        self.session.submit(request())
        self.session.submit(decision(), actor="operator")
        self.session.submit({"type": "execution_mode", "request_id": "e1", "mode": "verification"}, actor="operator")
        with self.assertRaises(ValidationError):
            self.session.run("e1")

    def test_provider_schema_has_strict_objects_and_supported_root(self):
        schema = response_schema(["experiment_request", "hypothesis", "prediction", "operator_question", "conclusion"])
        self.assertEqual(schema["type"], "object")
        self.assertNotIn("anyOf", schema)
        def check(value):
            if isinstance(value, dict):
                if value.get("type") == "object":
                    self.assertFalse(value["additionalProperties"])
                    self.assertEqual(set(value["required"]), set(value["properties"]))
                for item in value.values():
                    check(item)
            elif isinstance(value, list):
                for item in value:
                    check(item)
        check(schema)

    def test_numeric_settings_require_valid_bounds(self):
        for settings in ({"model": ""}, {"model": "test", "max_calls": 0}, {"model": "test", "timeout": float("nan")},
                         {"model": "test", "max_turns": True}, {"model": "test", "max_corrections": 6}):
            with self.subTest(settings=settings), self.assertRaises(ValidationError):
                AgentSettings(**settings)


@unittest.skipIf(httpx is None or openai is None, "Installa .[llm] per testare l'SDK con HTTP simulato")
class OpenAIAdapterTests(unittest.TestCase):
    def response(self, content=None, status="completed"):
        return {"id": "resp_test", "object": "response", "created_at": 0, "status": status, "model": "test-model-snapshot",
                "output": [{"type": "message", "id": "msg_test", "role": "assistant", "status": "completed",
                            "content": content if content is not None else [{"type": "output_text", "text": json.dumps({"message": conclusion()}), "annotations": []}]}],
                "usage": {"input_tokens": 120, "output_tokens": 40, "total_tokens": 160,
                          "input_tokens_details": {"cached_tokens": 0, "secret": "usage-canary"},
                          "output_tokens_details": {"reasoning_tokens": 12}, "unknown_secret": "usage-canary"}}

    def client(self, handler):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "fake-secret-only-for-offline-tests", "OPENAI_BASE_URL": "https://invalid.example"}):
            client = OpenAIClient(AgentSettings("test-model", timeout=7), transport=httpx.MockTransport(handler))
        self.addCleanup(client.close)
        return client

    def test_sdk_sends_expected_json_and_extracts_usage_without_network(self):
        seen = []
        def handler(req):
            seen.append(req)
            return httpx.Response(200, json=self.response())
        client = self.client(handler)
        from hidden_lab.protocol import apparatus
        payload = build_payload([{"seq": 1, "actor": "apparatus", "message": apparatus(5)}], AgentSettings("test-model"), "choose_next", 20, 15)
        reply = client.complete(payload)
        self.assertEqual(len(seen), 1)
        self.assertEqual(str(seen[0].url), "https://api.openai.com/v1/responses")
        self.assertEqual(json.loads(seen[0].content), payload)
        self.assertEqual(seen[0].headers["authorization"], "Bearer fake-secret-only-for-offline-tests")
        self.assertEqual(client.sdk.max_retries, 0)
        self.assertEqual(seen[0].extensions["timeout"]["read"], 7)
        self.assertEqual(reply.metadata["usage"]["total_tokens"], 160)
        self.assertEqual(reply.metadata["usage"]["output_tokens_details"]["reasoning_tokens"], 12)
        self.assertNotIn("usage-canary", json.dumps(reply.metadata))
        self.assertNotIn("fake-secret", json.dumps(payload) + json.dumps(reply.metadata))
        self.assertEqual(validate_message(json.loads(reply.text)["message"])["type"], "conclusion")

    def test_http_errors_are_redacted_and_never_retried(self):
        for status, expected in ((401, "authentication"), (429, "rate_limit"), (400, "request_rejected"), (500, "server_error")):
            calls = []
            def handler(req):
                calls.append(req)
                return httpx.Response(status, json={"error": {"message": "secret-error-body", "type": "test_error"}})
            with self.subTest(status=status):
                client = self.client(handler)
                with self.assertRaises(ProviderError) as error:
                    client.complete({"model": "test-model", "input": "test"})
                self.assertEqual(error.exception.code, expected)
                self.assertNotIn("secret-error-body", str(error.exception))
                self.assertEqual(len(calls), 1)

    def test_network_timeout_is_sanitized_with_no_retry(self):
        calls = []
        def handler(req):
            calls.append(req)
            raise httpx.ReadTimeout("secret-timeout-body", request=req)
        client = self.client(handler)
        with self.assertRaises(ProviderError) as error:
            client.complete({"model": "test-model", "input": "test"})
        self.assertEqual(error.exception.code, "timeout")
        self.assertEqual(len(calls), 1)

    def test_refusal_and_incomplete_output_are_not_accepted(self):
        for body, expected in ((self.response(status="incomplete"), "incomplete_response"),
                               (self.response(content=[{"type": "refusal", "refusal": "test"}]), "refusal")):
            client = self.client(lambda req: httpx.Response(200, json=body))
            reply = client.complete({"model": "test-model", "input": "test"})
            self.assertEqual(reply.issue, expected)
            self.assertEqual(reply.metadata["usage"]["total_tokens"], 160)
            self.assertEqual(reply.text, "")

    def test_missing_environment_key_fails_before_call(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}), self.assertRaises(ValidationError):
            OpenAIClient(AgentSettings("test-model"))

    def test_malformed_http_success_does_not_leak_raw_response(self):
        client = self.client(lambda req: httpx.Response(200, text="private-provider-body"))
        with self.assertRaises(ProviderError) as error:
            client.complete({"model": "test-model", "input": "test"})
        self.assertEqual(error.exception.code, "provider_error")
        self.assertNotIn("private-provider-body", str(error.exception))


class AgentCliTests(unittest.TestCase):
    def test_real_cli_with_simulated_client_and_human_input(self):
        with tempfile.TemporaryDirectory() as temp:
            session = Path(temp) / "demo"
            env = {**os.environ, "PYTHONUTF8": "1", "OPENAI_API_KEY": "must-not-be-used-or-logged"}
            result = subprocess.run([sys.executable, "-m", "hidden_lab", "investigate", "--client", "simulated",
                                     "--config", str(ROOT / "examples/operator-world.json"), "--session", str(session)],
                                    input=(ROOT / "examples/simulated-operator-input.txt").read_text(encoding="utf-8"),
                                    cwd=ROOT, env=env, text=True, encoding="utf-8", capture_output=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("CLIENT SIMULATO", result.stdout)
            self.assertIn("6 chiamate, 6 turni validi, 2 esperimenti", result.stdout)
            self.assertNotIn("must-not-be-used-or-logged", result.stdout + result.stderr)
            for path in session.rglob("*.jsonl"):
                self.assertNotIn("must-not-be-used-or-logged", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
