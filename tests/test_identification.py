import copy
import json
from pathlib import Path
from types import SimpleNamespace
import subprocess
import sys
import tempfile
import unittest

from hidden_lab.benchmark_contract import (benchmark_schema, build_benchmark_request,
                                           validate_benchmark_message)
from hidden_lab.benchmark_fake import BenchmarkFixtureClient
from hidden_lab.benchmark_report import aggregate_trials, render_report, verify_saved_trial
from hidden_lab.benchmark_suite import make_suite
from hidden_lab.benchmark_trial import BenchmarkTrial
from hidden_lab.identification import (score_scientific_submission, secret_grid,
                                       validate_scientific_submission)
from hidden_lab.identify_cli import run_command
from hidden_lab.protocol import ValidationError
from hidden_lab.provider_base import AgentSettings, ModelReply
from hidden_lab.session import Session
from hidden_lab.simulator import acceleration_at, parse_config
from hidden_lab.world_forge import generate_world


class IdentificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.record = generate_world(123456789, 1)

    def _submission(self):
        record = self.record
        world = parse_config(record["config"]).world
        predictions = []
        for probe in record["probes"]:
            ax, ay = acceleration_at(world, tuple(probe[key] for key in ("x", "y", "vx", "vy")))
            predictions.append({"probe_id": probe["probe_id"], "ax": ax, "ay": ay})
        true_law = record["config"]["world"]["law"]
        alternative = {"level": 2,
                       "ax": {"op": "add", "args": [true_law["ax"], {"op": "const", "value": 0}]},
                       "ay": {"op": "add", "args": [true_law["ay"], {"op": "const", "value": 0}]}}
        return {"predictions": predictions, "law_ast_json": json.dumps(alternative),
                "uncertainty_sigma": [0.5] * len(predictions)}

    def test_functional_equivalence_is_not_textual_equality_and_scores_are_separate(self):
        record = self.record
        submission = self._submission()
        scores, audit = score_scientific_submission(submission, record["probes"],
            parse_config(record["config"]).world, "private-material")
        self.assertEqual(scores["prediction"]["acceleration_rmse"], 0)
        self.assertTrue(scores["functional"]["empirically_equivalent"])
        self.assertEqual(scores["functional"]["metrics"]["acceleration_rmse"], 0)
        self.assertEqual(scores["functional"]["metrics"]["by_category"]["interpolation"]["valid_probe_count"], 64)
        self.assertEqual(scores["functional"]["metrics"]["by_category"]["extrapolation"]["valid_probe_count"], 64)
        self.assertTrue(scores["dependencies"]["exact_match"])
        self.assertGreater(scores["complexity"]["node_count"], 2)
        self.assertEqual(scores["calibration"]["coverage_68"], 1)
        self.assertEqual(len(audit["secret_grid"]), 128)
        self.assertNotEqual(secret_grid("private-material"), secret_grid("other-material"))
        wrong = copy.deepcopy(submission)
        wrong["law_ast_json"] = json.dumps({"level": 1, "ax": {"op": "const", "value": 0},
                                             "ay": {"op": "const", "value": 0}})
        wrong_scores, _ = score_scientific_submission(wrong, record["probes"],
            parse_config(record["config"]).world, "private-material")
        self.assertEqual(wrong_scores["prediction"]["acceleration_rmse"], 0)
        self.assertFalse(wrong_scores["functional"]["empirically_equivalent"])
        self.assertGreater(wrong_scores["functional"]["metrics"]["acceleration_rmse"], 1)
        self.assertGreater(wrong_scores["complexity"]["node_count"], 0)

    def test_invalid_ast_and_uncertainty_are_rejected_without_execution(self):
        submission = self._submission()
        ids = tuple(probe["probe_id"] for probe in self.record["probes"])
        for bad_law in ('__import__("os").system("echo BAD")', '{"level":1,"level":2}', '{}'):
            with self.subTest(bad_law=bad_law), self.assertRaises(ValidationError):
                validate_scientific_submission({**submission, "law_ast_json": bad_law}, ids)
        with self.assertRaises(ValidationError):
            validate_scientific_submission({**submission, "uncertainty_sigma": [0] * len(ids)}, ids)
        with self.assertRaises(ValidationError):
            validate_scientific_submission({**submission, "uncertainty_sigma": [1]}, ids)
        with self.assertRaises(ValidationError):
            validate_scientific_submission({**submission, "predictions": list(reversed(submission["predictions"]))}, ids)

    def test_dependency_metric_detects_missing_state_variable(self):
        record = generate_world(123456789, 2)
        predictions = [{"probe_id": probe["probe_id"], "ax": 0, "ay": 0} for probe in record["probes"]]
        submission = {"predictions": predictions, "law_ast_json": json.dumps({"level": 1,
            "ax": {"op": "const", "value": 0}, "ay": {"op": "const", "value": 0}})}
        scores, _ = score_scientific_submission(submission, record["probes"],
            parse_config(record["config"]).world, "private-material")
        self.assertFalse(scores["dependencies"]["exact_match"])
        self.assertEqual(scores["dependencies"]["missed_count"], 1)

    def test_human_challenge_requires_closed_session_and_scores_offline(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            world_path, challenge_path, submission_path = (root / name for name in
                ("world.json", "challenge.json", "submission.json"))
            world_path.write_text(json.dumps(self.record), encoding="utf-8")
            session = Session(root / "session", parse_config(self.record["config"]))
            challenge_args = SimpleNamespace(identify_command="challenge", world=world_path,
                                             session=session.directory, out=challenge_path)
            with self.assertRaises(ValidationError):
                run_command(challenge_args)
            self.assertFalse(challenge_path.exists())
            session.submit({"type": "conclusion", "final_hypothesis_id": None,
                            "summary": "Evidenza insufficiente", "evidence": [],
                            "limits": ["Nessuna misura"], "alternatives": ["Legge costante"]})
            self.assertEqual(run_command(challenge_args), 0)
            public_challenge = json.loads(challenge_path.read_text(encoding="utf-8"))
            self.assertNotIn("law", json.dumps(public_challenge))
            self.assertNotIn("seed", json.dumps(public_challenge))
            submission_path.write_text(json.dumps(self._submission()), encoding="utf-8")
            checked = subprocess.run([sys.executable, "-m", "hidden_lab", "identify", "check",
                "--challenge", str(challenge_path), "--submission", str(submission_path)],
                capture_output=True, text=True)
            self.assertEqual(checked.returncode, 0, checked.stderr)
            output = root / "score"
            scored = subprocess.run([sys.executable, "-m", "hidden_lab", "identify", "score",
                "--world", str(world_path), "--session", str(session.directory),
                "--challenge", str(challenge_path), "--submission", str(submission_path),
                "--out", str(output)], capture_output=True, text=True)
            self.assertEqual(scored.returncode, 0, scored.stderr)
            result = json.loads((output / "result.json").read_text(encoding="utf-8"))
            self.assertTrue(result["scores"]["functional"]["empirically_equivalent"])
            self.assertTrue((output / "public" / "submission.json").exists())
            self.assertTrue((output / "private" / "identification_grid.json").exists())
            self.assertFalse((output / "public" / "identification_grid.json").exists())


class ASTFixtureClient(BenchmarkFixtureClient):
    def __init__(self, world, bad_first=False):
        super().__init__(world)
        self.bad_first = bad_first
        self.submission_attempts = 0

    def complete(self, request):
        reply = super().complete(request)
        if request.context["phase"] != "submission":
            return reply
        envelope = json.loads(reply.text)
        self.submission_attempts += 1
        law = {"level": 1, "ax": {"op": "const", "value": 0},
               "ay": {"op": "const", "value": 0}}
        envelope["message"]["law_ast_json"] = ('__import__("os")' if self.bad_first and
            self.submission_attempts == 1 else json.dumps(law))
        envelope["message"]["uncertainty_sigma"] = [1.0] * len(envelope["message"]["predictions"])
        return ModelReply(json.dumps(envelope), reply.metadata)


class BenchmarkIdentificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.suite = make_suite(9876543210123456789, 3)

    def test_optional_ast_calibration_audit_and_aggregation(self):
        world = self.suite["worlds"][0]
        client = ASTFixtureClient(parse_config(world["config"]).world)
        with tempfile.TemporaryDirectory() as temp:
            trial = BenchmarkTrial(Path(temp) / "trial", self.suite, world["id"], "prior_only", client,
                                   AgentSettings("fixture-v1"))
            result = trial.run()
            self.assertEqual(result["status"], "completed")
            self.assertIsNotNone(result["identification"]["functional"])
            self.assertIsNotNone(result["identification"]["calibration"])
            self.assertEqual(verify_saved_trial(trial.directory)["identification"], result["identification"])
            report = aggregate_trials(temp)
            self.assertEqual(report["by_condition"]["prior_only"]["identification"]["functional_rmse"]["n"], 1)
            self.assertIn("Identificazione AST", render_report(report))
            for payload in client.payloads:
                body = payload.user_content()
                self.assertNotIn("secret_grid", body)
                self.assertNotIn("probe_truth", body)
                self.assertNotIn('"seed"', body)
            result_path = trial.directory / "result.json"
            changed = json.loads(result_path.read_text(encoding="utf-8"))
            changed["identification"]["functional"]["empirically_equivalent"] = True
            result_path.write_text(json.dumps(changed), encoding="utf-8")
            with self.assertRaises(ValidationError):
                verify_saved_trial(trial.directory)

    def test_v03_schema_has_optional_variants_but_legacy_rejects_extensions(self):
        modern = benchmark_schema(("benchmark_submission",), "0.3")
        old = benchmark_schema(("benchmark_submission",), "0.2")
        self.assertEqual(len(modern["properties"]["message"]["anyOf"]), 4)
        self.assertEqual(len(old["properties"]["message"]["anyOf"]), 1)
        request = build_benchmark_request([], AgentSettings("fixture-v1"), "submission",
                                          "prior_only", 2, 2, 0, "0.3")
        self.assertIn('"op":"const"', request.instructions)
        self.assertNotIn("private", request.user_content())
        message = {"type": "benchmark_submission", "final_hypothesis_id": None,
                   "law_description": "costante", "limits": ["poche misure"], "alternatives": [],
                   "predictions": [{"probe_id": "p1", "ax": 0, "ay": 0}],
                   "uncertainty_sigma": [1]}
        self.assertIn("uncertainty_sigma", validate_benchmark_message(message, ("benchmark_submission",),
                      ("p1",), None, "0.3"))
        with self.assertRaises(ValidationError):
            validate_benchmark_message(message, ("benchmark_submission",), ("p1",), None, "0.2")

    def test_malformed_ast_gets_one_correction_without_repeating_experiment(self):
        world = self.suite["worlds"][0]
        client = ASTFixtureClient(parse_config(world["config"]).world, bad_first=True)
        with tempfile.TemporaryDirectory() as temp:
            trial = BenchmarkTrial(Path(temp) / "trial", self.suite, world["id"], "active", client,
                                   AgentSettings("fixture-v1", max_corrections=1))
            result = trial.run()
            self.assertEqual(result["status"], "completed")
            self.assertEqual(result["invalid_responses"], 1)
            self.assertEqual(result["corrections"], 1)
            self.assertEqual(result["executed_experiments"], world["config"]["experiment_budget"])
            self.assertEqual(sum(event["message"]["type"] == "execution_started" for event in trial.events),
                             result["executed_experiments"])
