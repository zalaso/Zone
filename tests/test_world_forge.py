import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from hidden_lab.agent_contract import build_request
from hidden_lab.benchmark_suite import digest, make_suite, validate_suite
from hidden_lab.protocol import ValidationError
from hidden_lab.provider_base import AgentSettings
from hidden_lab.session import Session
from hidden_lab.simulator import TrajectoryError, acceleration_at, parse_config, simulate
from hidden_lab.world_forge import (FORGE_VERSION, generate_world, level_spec,
                                    public_manifest, read_world, validate_generated_world)

ROOT = Path(__file__).resolve().parents[1]


class WorldForgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.worlds = {level: generate_world(123456789, level) for level in range(1, 6)}

    def test_levels_one_to_five_generate_reproducible_private_worlds(self):
        for level, record in self.worlds.items():
            with self.subTest(level=level):
                self.assertEqual(record, generate_world(123456789, level))
                self.assertEqual(record["forge_version"], FORGE_VERSION)
                self.assertEqual(record["level"], level)
                self.assertEqual(record["attempt"], 0)
                self.assertTrue(level_spec(level).implemented)
                difficulty = validate_generated_world(record)
                self.assertTrue(difficulty["heuristic_only"])
                self.assertGreater(difficulty["distance_from_simpler_probe_rmse"], 0.25)
                self.assertGreater(difficulty["sensitivity_observation_rmse"], 0.04)
                config = parse_config(record["config"])
                self.assertEqual(config.to_dict(), record["config"])
                self.assertEqual(config.world.law.canonical_json(),
                                 parse_config(config.to_dict()).world.law.canonical_json())
                self.assertEqual(len(simulate(config, record["schedule"][0], 1)), 5)
                self.assertEqual(len(record["probes"]), 6)
        self.assertNotEqual(self.worlds[1], generate_world(123456790, 1))

    def test_future_levels_have_explicit_interfaces_but_cannot_generate(self):
        expected = {6: "regions", 7: "latent", 8: "memory", 9: "nonstationary"}
        for level, name in expected.items():
            spec = level_spec(level)
            self.assertEqual(spec.name, name)
            self.assertFalse(spec.implemented)
            self.assertTrue(spec.required_validation)
            with self.assertRaises(ValidationError):
                generate_world(123, level)
        with self.assertRaises(ValidationError):
            generate_world(123, 10)

    def test_benchmark_v03_remains_legacy_only(self):
        suite = make_suite(9876543210123456789, 3)
        original_hash = suite["sha256"]
        self.assertEqual(validate_suite(suite)["suite_version"], "0.3")
        suite["worlds"][0]["config"] = copy.deepcopy(self.worlds[2]["config"])
        suite["sha256"] = digest({key: value for key, value in suite.items() if key != "sha256"})
        self.assertNotEqual(suite["sha256"], original_hash)
        with self.assertRaises(ValidationError):
            validate_suite(suite)

    def test_ast_simulation_keeps_legacy_config_and_failure_semantics(self):
        legacy = parse_config({"world": {"family": "constant", "gravity": 9, "coefficient": 0},
                               "integration_step": 0.005, "noise_std": 0, "seed": 1,
                               "experiment_budget": 3})
        self.assertEqual(legacy.to_dict()["world"],
                         {"family": "constant", "gravity": 9.0, "coefficient": 0.0})
        ast = parse_config(self.worlds[1]["config"])
        self.assertEqual(acceleration_at(ast.world, (0, 0, 0, 0))[0], 0.5)
        self.assertLess(acceleration_at(ast.world, (0, 0, 0, 0))[1], -6)
        with self.assertRaises(ValidationError):
            parse_config({**self.worlds[1]["config"],
                          "world": {**self.worlds[1]["config"]["world"], "gravity": 9}})
        unsafe = copy.deepcopy(self.worlds[1]["config"])
        unsafe["world"]["law"]["ax"] = {"op": "div", "args": [
            {"op": "const", "value": 2}, {"op": "const", "value": 0}]}
        unsafe["world"]["law"]["level"] = 5
        with self.assertRaises(TrajectoryError):
            acceleration_at(parse_config(unsafe).world, (0, 0, 0, 0))

    def test_tampering_and_unsafe_simulation_are_rejected(self):
        record = self.worlds[4]
        changed = copy.deepcopy(record)
        changed["config"]["world"]["law"]["ay"] = {"op": "const", "value": -8}
        with self.assertRaises(ValidationError):
            validate_generated_world(changed)
        changed = copy.deepcopy(record)
        changed["probes"][0]["category"] = "extrapolation"
        with self.assertRaises(ValidationError):
            validate_generated_world(changed)
        with patch("hidden_lab.world_forge.simulate", side_effect=TrajectoryError):
            with self.assertRaises(ValidationError):
                validate_generated_world(record)
        real_simulate = simulate
        calls = 0
        def coarse_disagreement(*args):
            nonlocal calls
            calls += 1
            points = real_simulate(*args)
            if calls % 4 == 0:
                points[-1]["x"] += 0.01
            return points
        with patch("hidden_lab.world_forge.simulate", side_effect=coarse_disagreement):
            with self.assertRaisesRegex(ValidationError, "instabile"):
                validate_generated_world(record)
        mutable = copy.deepcopy(self.worlds[1])
        mutable["schedule"][0]["initial_position"]["x"] = 999
        self.assertEqual(generate_world(123456789, 1), self.worlds[1])

    def test_public_manifest_and_provider_payload_exclude_private_truth(self):
        record = self.worlds[5]
        manifest = public_manifest(record)
        raw_manifest = json.dumps(manifest)
        for forbidden in ('"law"', '"generator_seed"', '"config"', '"schedule"',
                          '"probes"', '"seed"', '"ax"', '"ay"'):
            self.assertNotIn(forbidden, raw_manifest)
        self.assertNotIn(str(record["generator_seed"]), raw_manifest)
        with tempfile.TemporaryDirectory() as temp:
            session = Session(Path(temp) / "session", parse_config(record["config"]))
            request = build_request(session.events, AgentSettings("offline"), "choose_next", 10, 10)
            transmitted = request.user_content() + request.instructions + json.dumps(request.schema)
            for forbidden in ('"law"', '"generator_seed"', '"family"', '"quadratic_drag"'):
                self.assertNotIn(forbidden, transmitted)
            self.assertNotIn(str(record["config"]["seed"]), transmitted)
            session.submit({"type": "experiment_request", "request_id": "ast1",
                            "purpose": "Misura esplorativa", "experiment": record["schedule"][0]})
            session.submit({"type": "operator_decision", "request_id": "ast1",
                            "action": "approve", "reason": "Confermo"}, actor="operator")
            session.submit({"type": "execution_mode", "request_id": "ast1",
                            "mode": "exploration"}, actor="operator")
            self.assertEqual(session.run("ast1")["status"], "ok")
            request = build_request(session.events, AgentSettings("offline"), "choose_next", 9, 9)
            self.assertNotIn('"law"', request.user_content())
            self.assertNotIn('"family"', request.user_content())
            self.assertTrue((session.directory / "private" / "reproducibility.json").exists())
            self.assertNotIn('"law"', (session.directory / "public" / "events.jsonl").read_text(encoding="utf-8"))

    def test_cli_generate_check_and_config_are_offline_and_new_only(self):
        with tempfile.TemporaryDirectory() as temp:
            private = Path(temp) / "world.json"
            manifest = Path(temp) / "manifest.json"
            config = Path(temp) / "config.json"
            command = [sys.executable, "-m", "hidden_lab", "forge", "generate",
                       "--seed", "123456789", "--level", "3", "--private", str(private),
                       "--manifest", str(manifest), "--config-out", str(config)]
            first = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=60)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(parse_config(json.loads(config.read_text(encoding="utf-8"))).world.law.level, 3)
            checked = subprocess.run([sys.executable, "-m", "hidden_lab", "forge", "check",
                                      "--private", str(private), "--manifest", str(manifest)],
                                     cwd=ROOT, capture_output=True, text=True, timeout=60)
            self.assertEqual(checked.returncode, 0, checked.stderr)
            self.assertNotEqual(subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                                               timeout=60).returncode, 0)
            duplicate = Path(temp) / "duplicate.json"
            duplicate.write_text('{"forge_version":"1","forge_version":"1"}', encoding="utf-8")
            with self.assertRaises(ValidationError):
                read_world(duplicate)


if __name__ == "__main__":
    unittest.main()
