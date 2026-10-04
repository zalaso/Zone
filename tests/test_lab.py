import contextlib
import copy
import io
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from hidden_lab.cli import execute_line
from hidden_lab.evaluation import compare_positions
from hidden_lab.plotting import plot_trajectory
from hidden_lab.protocol import (ValidationError, decode, observation_times, validate_experiment,
                                 validate_message, validate_observation)
from hidden_lab.session import Session
from hidden_lab.simulator import TrajectoryError, parse_config, simulate

ROOT = Path(__file__).resolve().parents[1]


def config(family="constant", gravity=8, coefficient=0, noise=0, budget=5, step=0.005):
    return parse_config({"world": {"family": family, "gravity": gravity, "coefficient": coefficient},
                         "integration_step": step, "noise_std": noise, "seed": 2026,
                         "experiment_budget": budget})


def experiment(x=0, y=0, vx=4, vy=6, duration=1, interval=0.25):
    return {"initial_position": {"x": x, "y": y}, "initial_velocity": {"x": vx, "y": vy},
            "duration": duration, "observation_interval": interval}


def request(request_id="e1", settings=None):
    return {"type": "experiment_request", "request_id": request_id, "purpose": "Misurare una traiettoria.",
            "experiment": settings or experiment()}


def decision(request_id="e1", action="approve", settings=None):
    message = {"type": "operator_decision", "request_id": request_id, "action": action,
               "reason": "Decisione manuale dell'operatore."}
    if settings is not None:
        message["modified_experiment"] = settings
    return message


def hypothesis(evidence=None):
    return {"type": "hypothesis", "hypothesis_id": "h1", "statement": "Accelerazione verticale costante.",
            "uncertainties": ["Dipendenza dall'altezza non esclusa."], "evidence": evidence or []}


def prediction(settings=None):
    return {"type": "prediction", "prediction_id": "p1", "hypothesis_id": "h1", "request_id": "e1",
            "points": [{"t": t, "x": 4*t, "y": 6*t - 4*t*t}
                       for t in observation_times(settings or experiment())]}


class DynamicsTests(unittest.TestCase):
    def test_constant_matches_analytic_solution_at_every_observation(self):
        points = simulate(config(), experiment(x=2, y=3), 1)
        for point in points:
            t = point["t"]
            self.assertAlmostEqual(point["x"], 2 + 4*t, places=11)
            self.assertAlmostEqual(point["y"], 3 + 6*t - 4*t*t, places=11)

    def test_height_matches_shifted_harmonic_solution(self):
        g, k = 8, 1.3
        for point in simulate(config("height", g, k), experiment(y=2), 1):
            t, omega = point["t"], math.sqrt(k)
            expected = (2 + g/k)*math.cos(omega*t) + 6/omega*math.sin(omega*t) - g/k
            self.assertAlmostEqual(point["y"], expected, places=8)
            self.assertAlmostEqual(point["x"], 4*t, places=10)

    def test_linear_drag_matches_analytic_solution(self):
        g, drag = 8, 0.4
        for point in simulate(config("linear_drag", g, drag), experiment(), 1):
            t = point["t"]
            factor = -math.expm1(-drag*t) / drag
            self.assertAlmostEqual(point["x"], 4*factor, places=9)
            self.assertAlmostEqual(point["y"], (6 + g/drag)*factor - g*t/drag, places=9)

    def test_quadratic_drag_matches_one_dimensional_solution(self):
        drag = 0.3
        for point in simulate(config("quadratic_drag", 0, drag), experiment(vx=5, vy=0), 1):
            self.assertAlmostEqual(point["x"], math.log1p(drag*5*point["t"])/drag, places=8)
            self.assertEqual(point["y"], 0)

    def test_quadratic_drag_converges_when_step_is_halved(self):
        exp = experiment(duration=2)
        def final(step):
            return simulate(config("quadratic_drag", 8, 0.8, step=step), exp, 1)[-1]
        reference, coarse, fine = final(0.0005), final(0.01), final(0.005)
        coarse_error = math.hypot(coarse["x"]-reference["x"], coarse["y"]-reference["y"])
        fine_error = math.hypot(fine["x"]-reference["x"], fine["y"]-reference["y"])
        self.assertLess(fine_error, coarse_error / 8)

    def test_sampling_and_integration_have_separate_grids(self):
        points = simulate(config(step=0.007), experiment(duration=0.9, interval=0.3), 1)
        self.assertEqual(len(points), 4)
        self.assertAlmostEqual(points[-1]["t"], 0.9)
        self.assertAlmostEqual(points[-1]["y"], 6*0.9 - 4*0.9**2, places=10)

    def test_out_of_domain_trajectory_is_stopped(self):
        with self.assertRaises(TrajectoryError):
            simulate(config(), experiment(y=-20, vy=-20, duration=5), 1)

    def test_noise_is_reproducible_per_execution_index(self):
        cfg, exp = config(noise=0.1), experiment()
        self.assertEqual(simulate(cfg, exp, 1), simulate(cfg, exp, 1))
        self.assertNotEqual(simulate(cfg, exp, 1), simulate(cfg, exp, 2))
        self.assertEqual(simulate(config(), exp, 1), simulate(config(), exp, 2))


class ProtocolTests(unittest.TestCase):
    def test_reject_invalid_numbers_and_extra_fields(self):
        for invalid in (True, float("nan"), float("inf"), "1", -1, 6, 10**500):
            exp = experiment()
            exp["duration"] = invalid
            with self.subTest(invalid=repr(invalid)), self.assertRaises(ValidationError):
                validate_experiment(exp)
        msg = request()
        msg["world"] = "secret"
        with self.assertRaises(ValidationError):
            validate_message(msg)

    def test_invalid_experiment_limits_and_grid(self):
        for exp in (experiment(vx=21), experiment(y=-21), experiment(interval=0.01),
                    experiment(duration=0.1, interval=0.25), experiment(duration=1, interval=0.3)):
            with self.subTest(exp=exp), self.assertRaises(ValidationError):
                validate_experiment(exp)

    def test_json_duplicate_nonfinite_and_oversize_are_rejected(self):
        for raw in ('{"type":1,"type":2}', '{"x":NaN}', '{"x":Infinity}', 'x'*64001, '{'):
            with self.subTest(raw=raw[:30]), self.assertRaises(ValidationError):
                decode(raw)

    def test_modification_requires_full_replacement_only_for_modify(self):
        for msg in (decision(action="modify"), decision(settings=experiment())):
            with self.assertRaises(ValidationError):
                validate_message(msg)

    def test_configuration_limits_are_validated(self):
        for change in ({"integration_step": 0}, {"noise_std": -1}, {"seed": True},
                       {"experiment_budget": 0}, {"unexpected": "secret"}):
            value = config().to_dict()
            value.update(change)
            with self.subTest(change=change), self.assertRaises(ValidationError):
                parse_config(value)
        with self.assertRaises(ValidationError):
            config("unknown")
        with self.assertRaises(ValidationError):
            config("constant", coefficient=1)

    def test_position_metric_has_expected_units_and_definition(self):
        points = [{"t": 0, "x": 0, "y": 0}, {"t": 1, "x": 0, "y": 0}]
        observed = [{"t": 0, "x": 3, "y": 4}, {"t": 1, "x": 0, "y": 0}]
        result = compare_positions(points, observed)
        self.assertEqual(result["max_position_error"], 5)
        self.assertAlmostEqual(result["position_rmse"], math.sqrt(12.5))
        self.assertEqual(result["law_identification"], "not_assessed")


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name) / "session"
        self.session = Session(self.directory, config())

    def approve(self, settings=None):
        self.session.submit(request(settings=settings))
        self.session.submit(decision(), actor="operator")

    def test_full_discovery_then_preregistered_verification(self):
        self.session.submit(request("explore"))
        self.session.submit(decision("explore"), actor="operator")
        self.session.run("explore")
        self.session.submit(hypothesis(["explore"]))
        self.approve()
        self.session.submit(prediction())
        self.session.run("e1")
        events = self.session.events
        self.assertEqual(self.session.executed_count, 2)
        self.assertLess(events[-1]["message"]["metrics"]["position_rmse"], 1e-10)
        kinds = [item["message"]["type"] for item in events]
        self.assertLess(kinds.index("prediction"), len(kinds)-3)
        self.assertEqual([item["seq"] for item in events], list(range(1, len(events)+1)))

    def test_operator_modification_is_the_executed_experiment(self):
        changed = experiment(x=10, duration=0.5)
        self.session.submit(request())
        self.session.submit(decision(action="modify", settings=changed), actor="operator")
        self.session.submit(hypothesis())
        with self.assertRaises(ValidationError):
            self.session.submit(prediction())
        self.assertEqual(self.session.run("e1")["points"][0]["x"], 10)

    def test_rejection_and_invalid_messages_do_not_consume_budget(self):
        self.session.submit(request())
        self.session.submit(decision(action="reject"), actor="operator")
        with self.assertRaises(ValidationError):
            self.session.run("e1")
        with self.assertRaises(ValidationError):
            self.session.submit(request("invalid", experiment(vx=99)))
        self.assertEqual(self.session.executed_count, 0)
        self.session.submit(request("next"))

    def test_agent_cannot_approve_and_run_requires_approval(self):
        self.session.submit(request())
        with self.assertRaises(ValidationError):
            self.session.submit(decision(), actor="agent")
        with self.assertRaises(ValidationError):
            self.session.run("e1")

    def test_references_must_exist(self):
        with self.assertRaises(ValidationError):
            self.session.submit(hypothesis(["future"]))
        self.approve()
        with self.assertRaises(ValidationError):
            self.session.submit(prediction())

    def test_prediction_cannot_be_changed_or_submitted_after_execution(self):
        self.approve()
        self.session.submit(hypothesis())
        self.session.submit(prediction())
        with self.assertRaises(ValidationError):
            self.session.submit(prediction())
        with self.assertRaises(ValidationError):
            self.session.submit(decision(action="modify", settings=experiment(x=3)), actor="operator")
        self.session.run("e1")
        with self.assertRaises(ValidationError):
            self.session.submit(prediction())
        with self.assertRaises(ValidationError):
            self.session.run("e1")

    def test_prediction_requires_exact_ordered_sampling_grid(self):
        self.approve()
        self.session.submit(hypothesis())
        for transform in (lambda p: p.pop(), lambda p: p.reverse(), lambda p: p[1].update(t=0.26)):
            msg = prediction()
            transform(msg["points"])
            with self.assertRaises(ValidationError):
                self.session.submit(msg)

    def test_failed_execution_consumes_budget_and_has_no_partial_measures(self):
        session = Session(Path(self.temp.name) / "failure", config(budget=1))
        session.submit(request(settings=experiment(y=-20, vy=-20, duration=5)))
        session.submit(decision(), actor="operator")
        result = session.run("e1")
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["points"], [])
        self.assertEqual(result["remaining_budget"], 0)
        with self.assertRaises(ValidationError):
            session.submit(request("next"))

    def test_error_during_verification_does_not_produce_a_score(self):
        settings = experiment(y=-20, vy=-20, duration=5)
        self.approve(settings)
        self.session.submit(hypothesis())
        self.session.submit(prediction(settings))
        self.session.run("e1")
        verification = self.session.events[-1]["message"]
        self.assertEqual(verification["status"], "unavailable")
        self.assertIsNone(verification["metrics"])

    def test_public_information_contains_no_private_metadata(self):
        other = Session(Path(self.temp.name) / "other", config("linear_drag", 7.123456, 0.432198))
        self.assertEqual(self.session.events, other.events)
        other.submit(request())
        other.submit(decision(), actor="operator")
        other.run("e1")
        public = (other.directory / "public" / "events.jsonl").read_text(encoding="utf-8")
        for forbidden in ("linear_drag", "7.123456", "0.432198", '"world"', '"gravity"',
                          '"coefficient"', '"seed"', '"integration_step"', "reproducibility", str(other.directory)):
            self.assertNotIn(forbidden, public)
        private = (other.directory / "private" / "reproducibility.json").read_text(encoding="utf-8")
        self.assertIn("linear_drag", private)
        self.assertIn("7.123456", private)

    def test_private_config_and_order_reproduce_observations(self):
        self.approve()
        expected = self.session.run("e1")["points"]
        stored = json.loads((self.directory / "private" / "reproducibility.json").read_text())
        self.assertEqual(simulate(parse_config(stored["config"]), experiment(), 1), expected)

    def test_observation_contract_rejects_metadata_and_incomplete_results(self):
        self.approve()
        observation = self.session.run("e1")
        for mutate in (lambda m: m.update(world="secret"), lambda m: m["points"].pop(),
                       lambda m: m.update(remaining_budget=99)):
            malformed = copy.deepcopy(observation)
            mutate(malformed)
            with self.assertRaises(ValidationError):
                validate_observation(malformed, experiment(), 5)

    def test_session_cannot_overwrite_existing_directory(self):
        with self.assertRaises(FileExistsError):
            Session(self.directory, config())

    def test_invalid_json_logs_generic_error_without_echoing_payload(self):
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(ValidationError):
            execute_line(self.session, 'agent {private_secret_canary')
        public = (self.directory / "public" / "events.jsonl").read_text()
        self.assertNotIn("private_secret_canary", public)
        self.assertIn("protocol_error", public)

    def test_expressions_are_text_and_never_evaluated(self):
        msg = hypothesis()
        msg["statement"] = "__import__('builtins').print('DO_NOT_EXECUTE')"
        captured = io.StringIO()
        with contextlib.redirect_stdout(captured):
            self.session.submit(msg)
        self.assertEqual(captured.getvalue(), "")
        self.assertEqual(self.session.hypotheses["h1"]["statement"], msg["statement"])


class CliTests(unittest.TestCase):
    def test_demo_through_real_cli_and_plot_with_public_files_only(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / "demo"
            result = subprocess.run([sys.executable, "-m", "hidden_lab", "demo", "--config",
                                     str(ROOT / "examples/operator-world.json"), "--script",
                                     str(ROOT / "examples/manual-session.txt"), "--session", str(directory)],
                                    cwd=ROOT, text=True, encoding="utf-8", errors="replace", capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("2 esperimenti", result.stdout)
            events = [json.loads(line) for line in (directory / "public/events.jsonl").read_text(encoding="utf-8").splitlines()]
            verification = next(e["message"] for e in events if e["message"]["type"] == "verification")
            self.assertLess(verification["metrics"]["position_rmse"], 1e-10)
            self.assertEqual(sum(e["message"]["type"] == "observation" for e in events), 2)
            # Un grafico deve funzionare senza alcuna cartella privata vicina.
            public_only = Path(temp) / "public-only"
            public_only.mkdir()
            (public_only / "events.jsonl").write_bytes((directory / "public/events.jsonl").read_bytes())
            chart = plot_trajectory(public_only, "check-1")
            self.assertTrue(chart.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"))


if __name__ == "__main__":
    unittest.main()
