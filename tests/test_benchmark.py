import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from hidden_lab.benchmark_contract import build_benchmark_request
from hidden_lab.benchmark_baselines import BaselineClient, baseline_seed, predict_affine
from hidden_lab.benchmark_fake import BenchmarkFixtureClient
from hidden_lab.benchmark_metrics import acceleration_metrics
from hidden_lab.benchmark_report import aggregate_trials, paired_bootstrap, render_report, verify_saved_trial
from hidden_lab.benchmark_suite import digest, make_suite, manifest, read_suite, save_new, validate_suite
from hidden_lab.benchmark_trial import BenchmarkTrial, NEUTRAL_ANSWER
from hidden_lab.protocol import ValidationError
from hidden_lab.provider_base import AgentSettings, ModelReply, ProviderError, metadata
from hidden_lab.simulator import parse_config

ROOT = Path(__file__).resolve().parents[1]


class SuiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.suite = make_suite(9876543210123456789, 3)

    def test_manifest_contains_only_opaque_ids_limits_versions_and_hash(self):
        sentinel = copy.deepcopy(self.suite)
        sentinel["worlds"][0]["config"]["world"]["gravity"] = 7.654321
        sentinel["worlds"][0]["config"]["world"]["coefficient"] = 0.123456
        sentinel["worlds"][0]["config"]["seed"] = 42424242
        sentinel["generator_seed"] = 9876543210123456788
        sentinel["sha256"] = digest({key: value for key, value in sentinel.items() if key != "sha256"})
        public = manifest(sentinel)
        raw = json.dumps(public, ensure_ascii=False)
        for forbidden in ("family", "gravity", "coefficient", "generator_seed", "passive_schedule",
                          "probe_id", "7.654321", "0.123456", "42424242", str(sentinel["generator_seed"])):
            self.assertNotIn(forbidden, raw)
        self.assertNotIn("ax", public["limits"])
        self.assertNotIn("ay", public["limits"])
        self.assertEqual(public["case_count"], 8)
        self.assertEqual(len(public["world_ids"]), 8)
        self.assertTrue(all(value.startswith("w") and len(value) == 17 for value in public["world_ids"]))
        self.assertEqual(public["sha256"], digest({key: value for key, value in sentinel.items() if key != "sha256"}))

    def test_tamper_and_degenerate_world_are_rejected(self):
        changed = copy.deepcopy(self.suite)
        changed["worlds"][0]["config"]["world"]["gravity"] = 0
        with self.assertRaises(ValidationError):
            validate_suite(changed)
        changed["sha256"] = digest({key: value for key, value in changed.items() if key != "sha256"})
        with self.assertRaises(ValidationError):
            validate_suite(changed)

    def test_generation_is_reproducible_and_schedule_is_common(self):
        self.assertEqual(self.suite, make_suite(9876543210123456789, 3))
        schedules = {json.dumps(item["passive_schedule"], sort_keys=True) for item in self.suite["worlds"]}
        self.assertEqual(len(schedules), 1)
        self.assertEqual({item["config"]["experiment_budget"] for item in self.suite["worlds"]}, {3})
        with tempfile.TemporaryDirectory() as temp:
            private, public = Path(temp) / "suite.json", Path(temp) / "manifest.json"
            save_new(private, self.suite)
            save_new(public, manifest(self.suite))
            self.assertEqual(read_suite(private), self.suite)

    def test_near_zero_normalization_is_defined(self):
        metrics = acceleration_metrics([{"probe_id": "p1", "ax": 1, "ay": 0}],
                                       [{"probe_id": "p1", "ax": 0, "ay": 0}])
        self.assertEqual(metrics["acceleration_rmse"], 1)
        self.assertEqual(metrics["normalization_scale"], 1)
        self.assertEqual(metrics["normalized_error"], 1)

    def test_probe_categories_have_separate_errors_and_legacy_suite_still_loads(self):
        probes = self.suite["worlds"][0]["probes"]
        self.assertEqual({probe["category"] for probe in probes}, {"interpolation", "extrapolation"})
        self.assertTrue(all(all(abs(probe[key]) <= 20 for key in ("x", "y", "vx", "vy"))
                            for probe in probes if probe["category"] == "interpolation"))
        self.assertTrue(all(any(abs(probe[key]) > 20 for key in ("x", "y", "vx", "vy"))
                            for probe in probes if probe["category"] == "extrapolation"))
        truth = [{"probe_id": "p1", "ax": 0, "ay": 0, "category": "interpolation"},
                 {"probe_id": "p2", "ax": 0, "ay": 0, "category": "extrapolation"}]
        prediction = [{"probe_id": "p1", "ax": 1, "ay": 0}, {"probe_id": "p2", "ax": 0, "ay": 2}]
        metrics = acceleration_metrics(prediction, truth)
        self.assertAlmostEqual(metrics["acceleration_rmse"], (2.5) ** 0.5)
        self.assertEqual(metrics["by_category"]["interpolation"]["acceleration_rmse"], 1)
        self.assertEqual(metrics["by_category"]["extrapolation"]["max_acceleration_error"], 2)
        self.assertEqual(metrics["by_category"]["extrapolation"]["normalized_error"], 2)
        legacy = make_suite(9876543210123456789, 3, "0.1")
        self.assertEqual(validate_suite(legacy)["suite_version"], "0.1")
        self.assertNotIn("category", legacy["worlds"][0]["probes"][0])
        previous = make_suite(9876543210123456789, 3, "0.2")
        self.assertEqual(validate_suite(previous)["suite_version"], "0.2")
        self.assertIn("category", previous["worlds"][0]["probes"][0])

    def test_public_request_projects_nested_private_sentinels(self):
        settings = AgentSettings("offline-model")
        event = {"seq": 1, "actor": "apparatus", "message": {
            "type": "apparatus", "protocol_version": 2, "coordinates": "x,y", "units": {"time": "s", "position": "m", "velocity": "m/s", "secret": "SECRET_SENTINEL"},
            "controls": [], "limits": {key: [0, 1] for key in
                ("initial_position_per_axis", "initial_velocity_per_axis", "duration", "observation_interval", "position_per_axis", "speed")},
            "sampling": "public", "experiment_budget": 3, "budget_policy": "public",
            "world": {"family": "SECRET_SENTINEL", "gravity": 7.654321}}}
        request = build_benchmark_request([event], settings, "discovery", "prior_only", 20, 15, 3)
        self.assertNotIn("SECRET_SENTINEL", request.user_content())
        self.assertNotIn("7.654321", request.user_content())


class TrialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.suite = make_suite(9876543210123456789, 3)
        cls.world = cls.suite["worlds"][0]

    def run_fixture(self, root, condition, scenario="correct", *, contaminated=False,
                    max_calls=20, max_turns=15, max_corrections=2, repetition=0, trial_seed=3):
        client = BenchmarkFixtureClient(parse_config(self.world["config"]).world, scenario)
        trial = BenchmarkTrial(Path(root) / (condition + "-" + scenario + ("-contaminated" if contaminated else "")),
                               self.suite, self.world["id"], condition, client,
                               AgentSettings("benchmark-fixture-v1", max_calls=max_calls, max_turns=max_turns,
                                             max_corrections=max_corrections),
                               contaminated=contaminated, repetition=repetition, trial_seed=trial_seed)
        return trial, trial.run(), client

    def test_four_conditions_freeze_probe_order_and_private_truth(self):
        with tempfile.TemporaryDirectory() as temp:
            runs = [self.run_fixture(temp, condition) for condition in ("prior_only", "passive_fixed", "passive_sequential", "active")]
            self.assertEqual([r[1]["executed_experiments"] for r in runs], [0, 3, 3, 3])
            self.assertEqual([r[1]["requested_experiments"] for r in runs], [0, 0, 0, 3])
            self.assertEqual({r[1]["status"] for r in runs}, {"completed"})
            self.assertEqual({r[1]["probe_hash"] for r in runs}, {runs[0][1]["probe_hash"]})
            self.assertTrue(all(0 <= r[1]["metrics"]["acceleration_rmse"] < 0.01 for r in runs))
            for trial, result, client in runs:
                events = [event["message"] for event in trial.events]
                kinds = [message["type"] for message in events]
                self.assertLess(kinds.index("conclusion"), kinds.index("probe_challenge"))
                self.assertLess(kinds.index("probe_challenge"), kinds.index("benchmark_submission"))
                self.assertFalse(any(kind in ("experiment_request", "passive_experiment", "execution_started")
                                     for kind in kinds[kinds.index("discovery_closed") + 1:]))
                self.assertFalse(any("probe_challenge" in [event["message"]["type"] for event in req.history]
                                     for req in client.payloads if req.context["phase"] == "discovery"))
                for req in client.payloads:
                    payload = req.user_content()
                    self.assertNotIn('"family"', payload)
                    self.assertNotIn('"gravity"', payload)
                    self.assertNotIn('"coefficient"', payload)
                    self.assertNotIn('"seed"', payload)
                    self.assertNotIn("probe_truth", payload)
                challenge = next(item for item in events if item["type"] == "probe_challenge")
                self.assertEqual(set(challenge), {"type", "probes"})
                self.assertEqual(set(challenge["probes"][0]), {"probe_id", "x", "y", "vx", "vy", "category"})
                self.assertEqual(verify_saved_trial(trial.directory)["metrics"], result["metrics"])
                self.assertTrue((trial.directory / "public/submission.json").exists())
                self.assertTrue((trial.directory / "private/probe_truth.json").exists())
            prior = runs[0][0]
            self.assertFalse(any(e["message"]["type"] == "observation" for e in prior.events))
            passive = runs[1][0]
            self.assertEqual([e["message"]["experiment"] for e in passive.events
                              if e["message"]["type"] == "passive_experiment"], self.world["passive_schedule"])
            active = runs[3][0]
            answers = [e["message"]["answer"] for e in active.events if e["message"]["type"] == "operator_answer"]
            self.assertTrue(all(answer == NEUTRAL_ANSWER for answer in answers))
            report = aggregate_trials(temp)
            self.assertEqual(len(report["paired"]), 1)
            self.assertIn("Accuratezza per esperimenti", render_report(report))

    def test_bad_prediction_insufficient_malformed_budget_provider_and_contamination(self):
        with tempfile.TemporaryDirectory() as temp:
            _, wrong, _ = self.run_fixture(temp, "prior_only", "wrong")
            self.assertAlmostEqual(wrong["metrics"]["acceleration_rmse"], 13**0.5, delta=0.01)
            _, insufficient, _ = self.run_fixture(temp, "passive_fixed", "insufficient")
            self.assertEqual(insufficient["status"], "insufficient")
            self.assertEqual(insufficient["executed_experiments"], 3)
            _, malformed, _ = self.run_fixture(temp, "active", "malformed")
            self.assertEqual(malformed["status"], "completed")
            self.assertEqual((malformed["invalid_responses"], malformed["corrections"]), (1, 1))
            budget_trial, budget, _ = self.run_fixture(temp, "active", "budget", max_calls=3)
            self.assertEqual((budget["status"], budget["stop_reason"], budget["model_calls"]),
                             ("limit_reached", "call_budget", 3))
            answers = [e["message"]["answer"] for e in budget_trial.events if e["message"]["type"] == "operator_answer"]
            self.assertEqual(answers, [NEUTRAL_ANSWER] * 3)
            _, provider, _ = self.run_fixture(temp, "prior_only", "provider_error")
            self.assertEqual((provider["status"], provider["stop_reason"]), ("provider_error", "provider_error"))
            _, contaminated, _ = self.run_fixture(temp, "active", "correct", contaminated=True)
            self.assertTrue(contaminated["contaminated"])
            report = aggregate_trials(temp)
            self.assertEqual(report["excluded_contaminated"], 1)
            self.assertEqual(report["included_count"], 5)
            self.assertEqual(aggregate_trials(temp, include_contaminated=True)["included_count"], 6)

    def test_saved_metrics_recompute_without_simulator_and_tamper_detected(self):
        with tempfile.TemporaryDirectory() as temp:
            trial, _, _ = self.run_fixture(temp, "active")
            with patch("hidden_lab.simulator.simulate", side_effect=AssertionError("No simulation")):
                self.assertEqual(aggregate_trials(temp)["included_count"], 1)
            truth_path = trial.directory / "private/probe_truth.json"
            truth = json.loads(truth_path.read_text(encoding="utf-8"))
            truth[0]["ax"] += 1
            truth_path.write_text(json.dumps(truth), encoding="utf-8")
            with self.assertRaises(ValidationError):
                verify_saved_trial(trial.directory)

    def test_saved_probe_category_must_match_public_challenge(self):
        with tempfile.TemporaryDirectory() as temp:
            trial, _, _ = self.run_fixture(temp, "passive_sequential")
            truth_path = trial.directory / "private/probe_truth.json"
            truth = json.loads(truth_path.read_text(encoding="utf-8"))
            truth[0]["category"] = ("extrapolation" if truth[0]["category"] == "interpolation"
                                     else "interpolation")
            truth_path.write_text(json.dumps(truth), encoding="utf-8")
            with self.assertRaises(ValidationError):
                verify_saved_trial(trial.directory)

    def test_no_trial_directory_reuse(self):
        with tempfile.TemporaryDirectory() as temp:
            self.run_fixture(temp, "prior_only")
            with self.assertRaises(FileExistsError):
                self.run_fixture(temp, "prior_only")

    def test_same_world_and_repetition_keep_probe_order_across_trial_seeds(self):
        with tempfile.TemporaryDirectory() as temp:
            trials = []
            for index, condition in enumerate(("prior_only", "passive_fixed", "active")):
                client = BenchmarkFixtureClient(parse_config(self.world["config"]).world)
                trials.append(BenchmarkTrial(Path(temp) / condition, self.suite, self.world["id"],
                                              condition, client, AgentSettings("benchmark-fixture-v1"),
                                              repetition=4, trial_seed=index + 1))
            self.assertEqual(len({trial.probe_hash for trial in trials}), 1)
            self.assertEqual({trial.config.experiment_budget for trial in trials}, {3})

    def test_sequential_schedule_and_reasoning_order_match_active_budget(self):
        with tempfile.TemporaryDirectory() as temp:
            sequential, result, client = self.run_fixture(temp, "passive_sequential")
            active, active_result, active_client = self.run_fixture(temp, "active")
            self.assertEqual(result["executed_experiments"], active_result["executed_experiments"])
            self.assertEqual(result["experiment_budget"], active_result["experiment_budget"])
            self.assertEqual(result["limits"], active_result["limits"])
            self.assertEqual([event["message"]["experiment"] for event in sequential.events
                              if event["message"]["type"] == "passive_experiment"], self.world["passive_schedule"])
            kinds = [event["message"]["type"] for event in sequential.events]
            for index in range(1, 4):
                start = kinds.index("passive_experiment", 0 if index == 1 else kinds.index("passive_experiment", start + 1))
                self.assertEqual(kinds[start:start + 4], ["passive_experiment", "execution_started", "observation", "hypothesis"])
            self.assertEqual([request.context["phase"] for request in client.payloads],
                             ["post_observation"] * 3 + ["discovery", "submission"])
            self.assertEqual([request.context["phase"] for request in active_client.payloads].count("post_observation"), 3)
            self.assertTrue(all("hypothesis" not in request.allowed_types for request in active_client.payloads
                                if request.context["phase"] == "discovery"))
            self.assertEqual(result["model_calls"], 5)
            self.assertEqual(active_result["model_calls"], 8)
            self.assertTrue(all("experiment_request" not in request.allowed_types for request in client.payloads))
            self.assertTrue(all("experiment_request" not in json.dumps(request.schema) for request in client.payloads))

    def test_passive_request_is_rejected_and_cannot_change_schedule(self):
        class RequestingClient(BenchmarkFixtureClient):
            def complete(self, request):
                self.calls += 1
                self.payloads.append(request)
                message = {"type": "experiment_request", "request_id": "steal", "purpose": "Cambiare il lancio.",
                           "experiment": self_experiment}
                return ModelReply(json.dumps({"message": message}), metadata())
        self_experiment = self.world["passive_schedule"][0]
        with tempfile.TemporaryDirectory() as temp:
            client = RequestingClient(parse_config(self.world["config"]).world)
            trial = BenchmarkTrial(Path(temp) / "passive", self.suite, self.world["id"],
                                   "passive_sequential", client, AgentSettings("fixture", max_corrections=0))
            result = trial.run()
            self.assertEqual((result["status"], result["stop_reason"]), ("limit_reached", "invalid_response_limit"))
            self.assertEqual(result["requested_experiments"], 0)
            self.assertEqual(result["executed_experiments"], 1)
            self.assertEqual(trial.events[1]["message"]["experiment"], self.world["passive_schedule"][0])
            self.assertEqual(result["invalid_responses"], 1)

    def test_malformed_sequential_response_corrects_without_repeating_experiment(self):
        with tempfile.TemporaryDirectory() as temp:
            trial, result, _ = self.run_fixture(temp, "passive_sequential", "malformed")
            self.assertEqual(result["status"], "completed")
            self.assertEqual((result["invalid_responses"], result["corrections"]), (1, 1))
            self.assertEqual(result["executed_experiments"], 3)
            self.assertEqual(sum(event["message"]["type"] == "execution_started" for event in trial.events), 3)
            self.assertEqual(result["model_calls"], 6)

    def test_pairing_rejects_budget_probe_limits_and_config_mismatch(self):
        with tempfile.TemporaryDirectory() as temp:
            runs = [self.run_fixture(temp, condition) for condition in ("prior_only", "passive_fixed", "passive_sequential", "active")]
            self.assertEqual(len(aggregate_trials(temp)["paired"]), 1)
            path = runs[-1][0].directory / "result.json"
            original = json.loads(path.read_text(encoding="utf-8"))
            for field, replacement in (("experiment_budget", 2), ("probe_hash", "different"),
                                       ("limits", {**original["limits"], "max_calls": 19}),
                                       ("world_config_hash", "different"),
                                       ("provider_config_hash", "different"),
                                       ("code_version", "different"), ("code_hash", "different")):
                changed = copy.deepcopy(original)
                changed[field] = replacement
                path.write_text(json.dumps(changed), encoding="utf-8")
                aggregate = aggregate_trials(temp)
                self.assertEqual(aggregate["paired"], [])
                self.assertIn(field, aggregate["rejected_pair_groups"][0]["mismatches"])
            path.write_text(json.dumps(original), encoding="utf-8")

    def test_provider_payloads_exclude_private_truth_in_all_four_conditions(self):
        with tempfile.TemporaryDirectory() as temp:
            for condition in ("prior_only", "passive_fixed", "passive_sequential", "active"):
                trial, _, client = self.run_fixture(temp, condition)
                config = trial.world["config"]["world"]
                for request in client.payloads:
                    payload = request.user_content() + json.dumps(request.schema) + request.instructions
                    for forbidden in ("probe_truth", '"family"', '"gravity"', '"coefficient"',
                                      '"generator_seed"', '"passive_schedule"'):
                        self.assertNotIn(forbidden, payload)
                    self.assertNotIn(str(config["gravity"]), payload)
                    if request.context["phase"] != "submission":
                        self.assertNotIn("probe_challenge", request.user_content())
                self.assertTrue((trial.directory / "private/probe_truth.json").exists())

    def test_active_and_sequential_pair_without_batch_diagnostics(self):
        with tempfile.TemporaryDirectory() as temp:
            self.run_fixture(temp, "passive_sequential")
            self.run_fixture(temp, "active")
            aggregate = aggregate_trials(temp)
            self.assertEqual(len(aggregate["paired"]), 1)
            self.assertEqual(set(aggregate["paired"][0]["conditions"]), {"passive_sequential", "active"})
            self.assertIn("Passive sequential RMSE", render_report(aggregate))

    def test_existing_v01_results_can_still_be_aggregated(self):
        legacy = ROOT / "benchmark_data" / "example" / "runs"
        if not legacy.exists():
            self.skipTest("Esempio v0.1 non presente")
        result = aggregate_trials(legacy)
        self.assertEqual(result["included_count"], 3)
        self.assertEqual(len(result["paired"]), 1)
        self.assertEqual(result["by_condition"]["passive_sequential"]["n"], 0)
        self.assertIsNone(result["by_condition"]["active"]["by_category"]["interpolation"]["acceleration_rmse"]["mean"])

    def test_v02_trial_remains_aggregatable(self):
        suite = make_suite(9876543210123456789, 3, "0.2")
        world = suite["worlds"][0]
        with tempfile.TemporaryDirectory() as temp:
            client = BenchmarkFixtureClient(parse_config(world["config"]).world)
            trial = BenchmarkTrial(Path(temp) / "v02", suite, world["id"], "passive_sequential",
                                   client, AgentSettings("benchmark-fixture-v1"))
            self.assertEqual(trial.run()["benchmark_version"], "0.2")
            aggregate = aggregate_trials(temp)
            self.assertEqual(aggregate["included_count"], 1)
            self.assertEqual(aggregate["by_condition"]["passive_sequential"]["n"], 1)

    def test_mixed_benchmark_versions_are_not_pooled(self):
        with tempfile.TemporaryDirectory() as temp:
            self.run_fixture(temp, "prior_only")
            legacy = make_suite(9876543210123456789, 3, "0.1")
            world = legacy["worlds"][0]
            client = BenchmarkFixtureClient(parse_config(world["config"]).world)
            trial = BenchmarkTrial(Path(temp) / "legacy", legacy, world["id"], "prior_only",
                                   client, AgentSettings("benchmark-fixture-v1"))
            self.assertEqual(trial.run()["benchmark_version"], "0.1")
            with self.assertRaises(ValidationError):
                aggregate_trials(temp)

    def test_probe_phase_rejects_new_experiment_and_preserves_freeze(self):
        class BadSubmissionClient(BenchmarkFixtureClient):
            def complete(self, request):
                if request.context["phase"] == "submission":
                    self.calls += 1
                    self.payloads.append(request)
                    message = {"type": "experiment_request", "request_id": "late", "purpose": "Troppo tardi",
                               "experiment": {"initial_position": {"x": 0, "y": 0},
                                              "initial_velocity": {"x": 0, "y": 0},
                                              "duration": 1, "observation_interval": 0.25}}
                    return ModelReply(json.dumps({"message": message}), metadata())
                return super().complete(request)
        with tempfile.TemporaryDirectory() as temp:
            client = BadSubmissionClient(parse_config(self.world["config"]).world)
            trial = BenchmarkTrial(Path(temp) / "s", self.suite, self.world["id"], "active", client,
                                   AgentSettings("benchmark-fixture-v1", max_corrections=1))
            result = trial.run()
            self.assertEqual(result["status"], "limit_reached")
            self.assertEqual(result["stop_reason"], "invalid_response_limit")
            self.assertEqual(result["executed_experiments"], 3)
            self.assertFalse((trial.directory / "public/submission.json").exists())

    def test_invalid_trajectory_consumes_budget_and_later_provider_error_does_not_rerun(self):
        class InvalidTrajectoryClient(BenchmarkFixtureClient):
            def complete(self, request):
                if request.context["phase"] == "discovery" and not any(
                        e["message"]["type"] == "experiment_request" for e in request.history):
                    self.calls += 1
                    self.payloads.append(request)
                    message = {"type": "experiment_request", "request_id": "badpath", "purpose": "Prova ai limiti.",
                               "experiment": {"initial_position": {"x": 20, "y": -20},
                                              "initial_velocity": {"x": 20, "y": -20},
                                              "duration": 5, "observation_interval": 1}}
                    return ModelReply(json.dumps({"message": message}), metadata())
                if any(e["message"]["type"] == "observation" for e in request.history):
                    raise ProviderError("connection")
                return super().complete(request)
        with tempfile.TemporaryDirectory() as temp:
            client = InvalidTrajectoryClient(parse_config(self.world["config"]).world)
            trial = BenchmarkTrial(Path(temp) / "s", self.suite, self.world["id"], "active", client,
                                   AgentSettings("benchmark-fixture-v1"))
            result = trial.run()
            self.assertEqual((result["status"], result["executed_experiments"]), ("provider_error", 1))
            self.assertEqual(result["failed_experiments"], 1)
            self.assertEqual(sum(e["message"]["type"] == "execution_started" for e in trial.events), 1)
            self.assertEqual(trial.observations["badpath"]["remaining_budget"], 2)


class BenchmarkCliTests(unittest.TestCase):
    def invoke(self, args, *, input_text=None):
        return subprocess.run([sys.executable, "-m", "hidden_lab", "benchmark", *args],
                              cwd=ROOT, input=input_text, capture_output=True, text=True,
                              encoding="utf-8", env={**os.environ, "PYTHONUTF8": "1"}, timeout=60)

    def test_cli_prepare_check_four_simulated_trials_aggregate_and_report(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            private, public, runs = root / "suite.json", root / "manifest.json", root / "runs"
            result = self.invoke(["prepare", "--private", str(private), "--manifest", str(public),
                                  "--seed", "9876543210123456789"])
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(self.invoke(["check", "--private", str(private), "--manifest", str(public)]).returncode, 0)
            world_id = json.loads(public.read_text(encoding="utf-8"))["world_ids"][0]
            for condition in ("prior_only", "passive_fixed", "passive_sequential", "active"):
                result = self.invoke(["trial", "--suite", str(private), "--world", world_id,
                                      "--condition", condition, "--provider", "simulated", "--yes",
                                      "--out", str(runs / condition)])
                self.assertEqual(result.returncode, 0, result.stderr)
            aggregate, report = root / "aggregate.json", root / "report.md"
            self.assertEqual(self.invoke(["aggregate", "--runs", str(runs), "--out", str(aggregate)]).returncode, 0)
            self.assertEqual(self.invoke(["report", "--aggregate", str(aggregate), "--out", str(report)]).returncode, 0)
            self.assertIn("Confronti appaiati", report.read_text(encoding="utf-8"))
            self.assertIn("Probe validi tot/int/ext", report.read_text(encoding="utf-8"))
            self.assertIn("Turni validi", report.read_text(encoding="utf-8"))
            self.assertEqual(len(json.loads(aggregate.read_text(encoding="utf-8"))["paired"]), 1)

    def test_real_trial_requires_explicit_start_before_client_or_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            suite = make_suite(12345)
            private = root / "suite.json"
            save_new(private, suite)
            out = root / "trial"
            result = self.invoke(["trial", "--suite", str(private), "--world", suite["worlds"][0]["id"],
                                  "--condition", "active", "--provider", "openai", "--model", "offline-model",
                                  "--out", str(out)], input_text="\n")
            self.assertEqual(result.returncode, 2)
            self.assertFalse(out.exists())
            self.assertIn("potenzialmente a pagamento", result.stdout)
            yes = self.invoke(["trial", "--suite", str(private), "--world", suite["worlds"][0]["id"],
                               "--condition", "active", "--provider", "openai", "--model", "offline-model",
                               "--out", str(out), "--yes"])
            self.assertEqual(yes.returncode, 1)
            self.assertFalse(out.exists())


class BaselineAndBootstrapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.suite = make_suite(9876543210123456789, 3)
        cls.world = cls.suite["worlds"][0]

    def test_finite_difference_affine_estimator_uses_public_positions(self):
        history = []
        for index, (x0, y0, vx0, vy0) in enumerate(((0, 0, 2, 3), (4, 5, -2, 1),
                                                     (-3, -4, 5, -2), (7, 2, -4, 4)), 1):
            experiment = {"initial_position": {"x": x0, "y": y0},
                          "initial_velocity": {"x": vx0, "y": vy0}, "duration": 1,
                          "observation_interval": 0.25}
            points = [{"t": t / 4, "x": x0 + vx0 * t / 4 + (t / 4) ** 2,
                       "y": y0 + vy0 * t / 4 - 1.5 * (t / 4) ** 2} for t in range(5)]
            history += [{"message": {"type": "execution_started", "request_id": f"e{index}",
                                     "experiment": experiment}},
                        {"message": {"type": "observation", "request_id": f"e{index}",
                                     "status": "ok", "points": points}}]
        predicted = predict_affine(history, [{"probe_id": "p1", "x": 9, "y": -8, "vx": 3, "vy": -7}])
        self.assertAlmostEqual(predicted[0]["ax"], 2, delta=0.01)
        self.assertAlmostEqual(predicted[0]["ay"], -3, delta=0.01)

    def test_two_baselines_complete_offline_and_random_policy_is_reproducible(self):
        with tempfile.TemporaryDirectory() as temp:
            runs = []
            seed = baseline_seed(self.suite["sha256"], self.world["id"], 0, 11)
            for label, kind, condition in (("random-a", "random_policy", "active"),
                                           ("random-b", "random_policy", "active"),
                                           ("affine", "affine_estimator", "passive_sequential")):
                client = BaselineClient(kind, seed)
                trial = BenchmarkTrial(Path(temp) / label, self.suite, self.world["id"], condition,
                                       client, AgentSettings(kind), trial_seed=11)
                result = trial.run()
                self.assertEqual(result["status"], "completed")
                self.assertEqual(result["api_cost_usd"], 0)
                self.assertEqual(result["executed_experiments"], 3)
                for request in client.payloads:
                    payload = request.user_content() + request.instructions + json.dumps(request.schema)
                    self.assertNotIn('"family"', payload)
                    self.assertNotIn('"gravity"', payload)
                    self.assertNotIn("probe_truth", payload)
                    if request.context["phase"] != "submission":
                        self.assertNotIn("probe_challenge", request.user_content())
                runs.append((trial, result))
            def chosen(trial):
                return [event["message"]["experiment"] for event in trial.events
                        if event["message"]["type"] == "experiment_request"]
            self.assertEqual(chosen(runs[0][0]), chosen(runs[1][0]))
            self.assertEqual(runs[0][1]["metrics"], runs[1][1]["metrics"])

    def test_bootstrap_requires_eight_distinct_worlds_and_is_deterministic(self):
        def pair(index):
            cell = lambda value: {"acceleration_rmse": value,
                                  "max_acceleration_error": value,
                                  "normalized_error": value,
                                  "by_category": {category: {name: value for name in
                                      ("acceleration_rmse", "max_acceleration_error", "normalized_error")}
                                      for category in ("interpolation", "extrapolation")}}
            return {"benchmark_version": "0.3", "suite_hash": "suite", "world_id": f"w{index}",
                    "provider": "baseline", "model": "same", "trial_seed": 0,
                    "experiment_budget": 3, "limits": {"max_calls": 20},
                    "provider_config_hash": "settings", "code_version": "0.4.0",
                    "conditions": {"active": cell(1), "passive_sequential": cell(2)}}
        short = paired_bootstrap([pair(i) for i in range(7)])
        self.assertEqual(short[0]["dimensions"]["overall"]["acceleration_rmse"]["status"], "insufficient_sample")
        self.assertIsNone(short[0]["dimensions"]["overall"]["acceleration_rmse"]["ci95"])
        complete = paired_bootstrap([pair(i) for i in range(8)])
        metric = complete[0]["dimensions"]["overall"]["acceleration_rmse"]
        self.assertEqual(metric["ci95"], [-1, -1])
        self.assertEqual(complete, paired_bootstrap([pair(i) for i in range(8)]))
        legacy = pair(9)
        legacy["provider_config_hash"] = None
        self.assertEqual(len(paired_bootstrap([pair(0), legacy])), 2)


if __name__ == "__main__":
    unittest.main()
