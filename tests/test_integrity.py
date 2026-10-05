"""Integrity: split, commitment, contaminazione e quote, nessun modello reale."""

import copy
from contextlib import closing
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from hidden_lab.benchmark_suite import digest
from hidden_lab.integrity_suite import (make_pack, manifest, records, reveal_proof, verify_reveal,
    validate_pack, physics_fingerprint, duplicate, benchmark_binding, read_json)
from hidden_lab.protocol import ValidationError


class PackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pack = make_pack(800123, levels=(1, 2), budget=3)

    def test_deterministic_disjoint_splits_and_salted_public_manifest(self):
        self.assertEqual(self.pack, make_pack(800123, levels=(1, 2), budget=3))
        ids = [r["world_id"] for split in ("train", "development", "test") for r in records(self.pack, split)]
        self.assertEqual(len(ids), len(set(ids)))
        public = manifest(self.pack)
        text = json.dumps(public)
        for forbidden in ('"seed"', '"law"', '"config"', '"generator_seed"', '"salt"', '"level"', '"probes"'):
            self.assertNotIn(forbidden, text)
        for record in records(self.pack, "test"):
            self.assertNotIn(record["sha256"], text)
            self.assertNotIn(self.pack["test_salts"][record["world_id"]], text)
        self.assertIn("config", records(self.pack, "train")[0])

    def test_reveal_requires_original_manifest_and_exact_record_and_nonce(self):
        public = manifest(self.pack)
        proof = reveal_proof(self.pack, records(self.pack, "test")[0]["world_id"])
        self.assertTrue(verify_reveal(public, proof, public["sha256"]))
        for key, value in (("salt", "0" * 64), ("manifest_hash", "0" * 64), ("world_id", "other")):
            with self.subTest(key=key), self.assertRaises(ValidationError):
                verify_reveal(public, {**proof, key: value}, public["sha256"])
        changed = copy.deepcopy(proof)
        record = json.loads(changed["record_json"])
        record["config"]["seed"] += 1
        changed["record_json"] = json.dumps(record)
        with self.assertRaises(ValidationError):
            verify_reveal(public, changed, public["sha256"])
        with self.assertRaises(ValidationError):
            verify_reveal(public, proof, "0" * 64)

    def test_reveal_cross_language_reserialization_preserves_record_exactly(self):
        # JS turns integral floats into ints; the canonical record remains opaque text.
        public = manifest(self.pack)
        proof = reveal_proof(self.pack, records(self.pack, "test")[0]["world_id"])
        def js_numbers(value):
            if isinstance(value, dict):
                return {k: js_numbers(v) for k, v in value.items()}
            if isinstance(value, list):
                return [js_numbers(v) for v in value]
            return int(value) if isinstance(value, float) and value.is_integer() else value
        transported = json.loads(json.dumps(js_numbers(proof)))
        self.assertTrue(verify_reveal(public, transported, public["sha256"]))
        self.assertEqual(json.loads(transported["record_json"]), records(self.pack, "test")[0])

    def test_duplicate_physics_ignores_identity_and_commutative_order(self):
        record = copy.deepcopy(records(self.pack, "test")[0])
        altered = copy.deepcopy(record)
        altered["world_id"] = "w0000000000000000"
        altered["config"]["seed"] += 1
        self.assertTrue(duplicate(physics_fingerprint(record), physics_fingerprint(altered)))
        def reverse(node):
            if "args" in node:
                if node["op"] in ("add", "mul", "norm"):
                    node["args"].reverse()
                for item in node["args"]:
                    reverse(item)
        for axis in ("ax", "ay"):
            reverse(altered["config"]["world"]["law"][axis])
        self.assertEqual(physics_fingerprint(record)["law_hash"], physics_fingerprint(altered)["law_hash"])
        changed = copy.deepcopy(self.pack)
        changed["splits"]["development"][0] = copy.deepcopy(changed["splits"]["train"][0])
        changed["sha256"] = digest({k: v for k, v in changed.items() if k != "sha256"})
        with self.assertRaises(ValidationError):
            validate_pack(changed)

    def test_json_duplicate_keys_nonfinite_and_size_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "bad.json"
            for text in ('{"a":1,"a":2}', '{"a":NaN}', '{'):
                path.write_text(text, encoding="utf-8")
                with self.assertRaises(ValidationError):
                    read_json(path)
            path.write_text(" " * 20, encoding="utf-8")
            with patch("hidden_lab.integrity_suite.MAX_PACK_BYTES", 10), self.assertRaises(ValidationError):
                read_json(path)

    def test_benchmark_v03_binding_and_four_condition_aggregate(self):
        from hidden_lab.benchmark_fake import BenchmarkFixtureClient
        from hidden_lab.benchmark_trial import BenchmarkTrial
        from hidden_lab.benchmark_report import aggregate_trials, render_report
        from hidden_lab.provider_base import AgentSettings
        from hidden_lab.simulator import parse_config
        pack = make_pack(810456, kind="benchmark", budget=1)
        suite, world = pack["splits"]["test"], records(pack, "test")[0]
        binding = benchmark_binding(pack, suite, world["id"])
        self.assertEqual(suite["suite_version"], "0.3")
        self.assertEqual(binding["split"], "test")
        with self.assertRaises(ValidationError):
            benchmark_binding(pack, pack["splits"]["train"], world["id"])
        with tempfile.TemporaryDirectory() as temp:
            for condition in ("prior_only", "passive_fixed", "passive_sequential", "active"):
                client = BenchmarkFixtureClient(parse_config(world["config"]).world, "correct")
                result = BenchmarkTrial(Path(temp) / condition, suite, world["id"], condition, client,
                    AgentSettings("fixture"), integrity=binding).run()
                self.assertTrue(result["integrity"]["oracle_fixture"])
            aggregate = aggregate_trials(temp)
            self.assertIn(manifest(pack)["sha256"], aggregate["integrity_scope"])
            self.assertIn("fixture oracolo", render_report(aggregate))
            # Validation of saved files still runs; only the test seam varies provenance.
            from hidden_lab.benchmark_report import verify_saved_trial
            def mixed(directory):
                result = verify_saved_trial(directory)
                if directory.name == "active":
                    result["integrity"]["split"] = "development"
                return result
            with patch("hidden_lab.benchmark_report.verify_saved_trial", side_effect=mixed), self.assertRaises(ValidationError):
                aggregate_trials(temp)


@unittest.skipUnless(importlib.util.find_spec("fastapi") is not None, "Installare l'extra backend")
class IntegrityArenaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pack = make_pack(800123, levels=(1,), budget=1)
        cls.world = records(cls.pack, "test")[0]
        cls.operator = "integrity-operator-offline-test-1234567890"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "arena.db"
        self.counter = 0
        self.client = self.restart()
        self.challenge = self.post("challenges", {"name": "Test cieco", "world_id": self.world["world_id"]}).json()
        self.agent = self.post("agents", {"name": "Agente", "model": "offline"}).json()
        self.token = self.agent["token"]
        self.session = self.post("sessions", {"challenge_id": self.challenge["challenge_id"]}, self.token).json()

    def restart(self):
        from fastapi.testclient import TestClient
        from hidden_lab.backend import RateLimiter, create_app
        client = TestClient(create_app(self.db, integrity_packs=[self.pack], operator_token=self.operator,
            rate_limiter=RateLimiter(read=10000, write=10000, run=10000)))
        self.addCleanup(client.close)
        return client

    # Shared protocol helpers, not shared tests.
    from tests.test_arena import ArenaTests
    headers = ArenaTests.headers
    post = ArenaTests.post
    get = ArenaTests.get
    state = ArenaTests.state
    message = ArenaTests.message
    prepare_run = ArenaTests.prepare_run
    conclude = ArenaTests.conclude

    def score(self):
        predictions = self.conclude()
        return self.post("sessions/" + self.session["session_id"] + "/submission",
            {"expected_version": self.state()["version"], "submission": predictions}, self.token).json()

    def test_manifest_and_private_payload_boundary(self):
        public = self.client.get("/v1/integrity/manifests").json()["manifests"][0]
        self.assertEqual(public, manifest(self.pack))
        pid = public["pack_id"]
        self.assertEqual(self.client.get(f"/v1/integrity/packs/{pid}/test").status_code, 404)
        self.assertEqual(self.client.get(f"/v1/integrity/packs/{pid}/train").json(), self.pack["splits"]["train"])
        worlds = self.client.get("/v1/worlds").json()["worlds"]
        case = next(w for w in worlds if w["world_id"] == self.world["world_id"])
        self.assertEqual(set(case), {"world_id", "experiment_budget", "integrity"})
        payload = json.dumps(self.state()) + self.client.get("/v1/arena/challenges").text + json.dumps(case)
        for forbidden in ('"seed"', '"config"', '"law"', '"salt"', '"probes_hash"', '"world_hash"', self.world["sha256"]):
            self.assertNotIn(forbidden, payload)
        from hidden_lab.arena_client import model_request
        from hidden_lab.agent_contract import openai_payload
        from hidden_lab.provider_base import AgentSettings
        snapshot = self.state()
        snapshot["integrity"]["private_pack"] = "PRIVATE_PACK_SENTINEL"
        snapshot["events"][0]["message"]["private_record"] = "PRIVATE_PACK_SENTINEL"
        text = json.dumps(openai_payload(model_request(snapshot, AgentSettings("offline"), 20)))
        self.assertNotIn("PRIVATE_PACK_SENTINEL", text)
        self.assertNotIn(self.pack["test_salts"][self.world["world_id"]], text)

    def test_test_cannot_be_used_in_legacy_modes_or_aliased(self):
        for path in ("/v1/sessions", "/v1/matches"):
            response = self.client.post(path, json={"world_id": self.world["world_id"]}, headers=self.headers())
            self.assertIn(response.status_code, (401, 422))
        repo = self.client.app.state.arena.repo
        from hidden_lab.local_worlds import build_world
        alias = build_world(self.world["config"]["world"]["law"], budget=1, seed=42)
        self.assertNotEqual(alias["world_id"], self.world["world_id"])
        self.assertTrue(duplicate(physics_fingerprint(alias), physics_fingerprint(self.world)))
        with self.assertRaises(ValidationError):
            repo.register_world(alias)
        with self.assertRaises(ValidationError):
            repo.daily_world("2099-01-01", lambda: self.world)
        from hidden_lab.backend_store import SQLiteRepository
        with self.assertRaises(ValidationError):
            SQLiteRepository(self.db, worlds=[alias])

    def test_public_splits_and_repeat_test_challenge_rejected(self):
        for split in ("train", "development", "test"):
            wid = records(self.pack, split)[0]["world_id"]
            response = self.client.post("/v1/arena/challenges", json={"name": "No", "world_id": wid}, headers=self.headers())
            self.assertEqual(response.status_code, 422, response.text)

    def test_score_embargo_receipt_and_replay_until_closed(self):
        scored = self.score()
        self.assertEqual(scored["status"], "scored")
        self.assertIsNone(scored["scores"])
        before = self.state()
        self.assertIsNone(before["scores"])
        self.assertIsNone(before["events"][-1]["message"]["scores"])
        self.assertIsNotNone(self.get("sessions/" + self.session["session_id"]).json()["scores"])
        self.post("challenges/" + self.challenge["challenge_id"] + "/close", {})
        self.assertIsNotNone(self.state()["scores"])
        board = self.get("challenges/" + self.challenge["challenge_id"] + "/leaderboard", self.token).json()
        self.assertEqual(board["comparison_scope"], "blind_test")
        self.assertTrue(board["trials"][0]["integrity"]["eligible"])

    def test_flag_operator_only_immutable_raw_results_retained(self):
        self.score()
        sid = self.session["session_id"]
        body = {"expected_version": self.state()["version"], "reason": "known_law"}
        self.post(f"sessions/{sid}/integrity", body, self.token, expected=401)
        self.post(f"sessions/{sid}/integrity", body)
        self.post(f"sessions/{sid}/integrity", {**body, "expected_version": self.state()["version"]}, expected=422)
        board = self.get("challenges/" + self.challenge["challenge_id"] + "/leaderboard").json()
        self.assertEqual(board["dimensions"]["acceleration_rmse"], [])
        self.assertIsNotNone(board["trials"][0]["scores"])
        self.assertFalse(board["trials"][0]["integrity"]["eligible"])
        self.client = self.restart()
        self.assertEqual(self.state()["integrity"]["flags"], ["known_law"])

    def test_reveal_closed_gate_proof_retirement_and_restart(self):
        self.score()
        sid = self.session["session_id"]
        body = {"expected_version": self.state()["version"], "confirm": "reveal"}
        self.post(f"sessions/{sid}/reveal", body, expected=422)
        self.post("challenges/" + self.challenge["challenge_id"] + "/close", {})
        self.post(f"sessions/{sid}/reveal", body)
        proof = self.get(f"sessions/{sid}/reveal").json()["integrity_proof"]
        self.assertTrue(verify_reveal(manifest(self.pack), proof, manifest(self.pack)["sha256"]))
        self.assertNotIn(records(self.pack, "train")[0]["world_id"], json.dumps(proof))
        self.client = self.restart()
        repo = self.client.app.state.arena.repo
        with repo._connect() as db:
            from hidden_lab.integrity_store import IntegrityCatalog
            self.assertEqual(IntegrityCatalog(repo).case(db, self.world["world_id"])["state"], "retired")
            with self.assertRaises(ValidationError):
                IntegrityCatalog(repo).session_admission(db, self.world["world_id"], {"mode": "arena"})
        self.assertTrue(self.state()["integrity"]["eligible"])  # Historical eligibility retained.

    def test_other_unfinished_trial_blocks_close_and_reveal(self):
        other = self.post("agents", {"name": "Other", "model": "offline"}).json()
        self.post("sessions", {"challenge_id": self.challenge["challenge_id"]}, other["token"])
        self.score()
        self.post("challenges/" + self.challenge["challenge_id"] + "/close", {}, expected=422)
        self.post("sessions/" + self.session["session_id"] + "/reveal",
            {"expected_version": self.state()["version"], "confirm": "reveal"}, expected=422)

    def test_persistent_rates_count_invalid_reads_and_cached_writes(self):
        sid = self.session["session_id"]
        # create-session already consumed one write; an identical receipt consumes rate, not quota.
        body = {"challenge_id": self.challenge["challenge_id"]}
        headers = self.headers(self.token, "cached-rate-admission")
        response = self.client.post("/v1/arena/sessions", json=body, headers=headers)
        self.assertEqual(response.status_code, 422)  # One trial/account/challenge.
        for _ in range(28):
            self.assertEqual(self.client.post("/v1/arena/sessions", json=body, headers=headers).status_code, 422)
        self.assertEqual(self.client.post("/v1/arena/sessions", json=body, headers=headers).status_code, 429)
        rotated = self.post("agents/" + self.agent["agent_id"] + "/tokens", {}, expected=201).json()
        self.client = self.restart()
        self.assertEqual(self.client.post("/v1/arena/sessions", json=body,
            headers=self.headers(rotated["token"])).status_code, 429)
        for _ in range(120):
            self.assertEqual(self.get("sessions/not-found", rotated["token"]).status_code, 404)
        self.assertEqual(self.get("sessions/" + sid, rotated["token"]).status_code, 429)
        store = self.client.app.state.arena
        now = store.clock()
        with patch.object(store, "clock", return_value=now+61):
            self.assertEqual(self.get("sessions/" + sid, rotated["token"]).status_code, 200)

    def test_twenty_invalid_mutations_block_new_keys_after_restart(self):
        sid = self.session["session_id"]
        for _ in range(20):
            self.post(f"sessions/{sid}/messages", {"expected_version": 1, "message": {"type": "unknown"}}, self.token, expected=422)
        self.client = self.restart()
        self.post(f"sessions/{sid}/messages", {"expected_version": 1, "message": {"type": "unknown"}}, self.token, expected=429)
        self.assertEqual(self.state()["account"]["usage"]["invalid"], 20)

    def test_import_duplicate_catalog_is_atomic(self):
        from hidden_lab.integrity_store import IntegrityCatalog
        other = copy.deepcopy(self.pack)
        other["generator_seed"] += 1
        other["sha256"] = digest({k: v for k, v in other.items() if k != "sha256"})
        catalog = IntegrityCatalog(self.client.app.state.arena.repo)
        with self.assertRaises(ValidationError):
            catalog.import_pack(other)
        with closing(sqlite3.connect(self.db)) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM integrity_packs").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM integrity_cases").fetchone()[0], 3)

    def test_import_rejects_preexisting_alias_or_unfinished_legacy_session(self):
        from hidden_lab.backend_store import SQLiteRepository
        from hidden_lab.integrity_store import IntegrityCatalog
        from hidden_lab.protocol import apparatus
        for alias in (True, False, None):
            with self.subTest(alias=alias):
                record = copy.deepcopy(self.world)
                if alias:
                    from hidden_lab.local_worlds import build_world
                    record = build_world(self.world["config"]["world"]["law"], budget=1, seed=42)
                    self.assertNotEqual(record["world_id"], self.world["world_id"])
                    self.assertTrue(duplicate(physics_fingerprint(record), physics_fingerprint(self.world)))
                repo = SQLiteRepository(Path(self.temp.name) / f"old-{alias}.db", worlds=[record])
                if alias is False:
                    repo.create_session(record["world_id"], "fake-hash", apparatus(1))
                with self.assertRaises(ValidationError):
                    IntegrityCatalog(repo).import_pack(self.pack)
                with repo._connect() as db:
                    self.assertEqual(db.execute("SELECT COUNT(*) FROM integrity_packs").fetchone()[0], 0)
