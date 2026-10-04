"""Contratto Arena, concorrenza persistente e confine pubblico/privato, senza provider."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
from threading import Event
import unittest
from unittest.mock import patch

if importlib.util.find_spec("fastapi") is not None:
    from fastapi.testclient import TestClient
    from hidden_lab.backend import RateLimiter, create_app
    from hidden_lab.world_forge import generate_world


@unittest.skipUnless(importlib.util.find_spec("fastapi") is not None, "Installare l'extra backend")
class ArenaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.world = generate_world(87523, 1, 2)
        cls.operator = "arena-local-test-operator-no-real-secrets-1234"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "arena.db"
        self.counter = 0
        self.client = self.restart()
        self.challenge = self.post("challenges", {"name": "Challenge offline", "world_id": self.world["world_id"]}).json()
        self.agent = self.post("agents", {"name": "Baseline", "model": "offline-test", "kind": "offline_baseline"}).json()
        self.token = self.agent["token"]
        self.session = self.post("sessions", {"challenge_id": self.challenge["challenge_id"]}, self.token).json()

    def restart(self):
        client = TestClient(create_app(self.db, worlds=[self.world], operator_token=self.operator,
            rate_limiter=RateLimiter(read=10000, write=10000, run=10000)))
        self.addCleanup(client.close)
        return client

    def headers(self, token=None, key=None):
        self.counter += 1
        return {"X-Zone-Token": token or self.operator, "X-Zone-Arena-Version": "1",
                "Idempotency-Key": key or f"offline-test-{self.counter:05d}"}

    def post(self, path, body, token=None, key=None, expected=200):
        response = self.client.post("/v1/arena/" + path, json=body, headers=self.headers(token, key))
        self.assertEqual(response.status_code, 201 if path in ("challenges", "agents", "sessions") else expected, response.text)
        return response

    def get(self, path, token=None):
        return self.client.get("/v1/arena/" + path, headers=self.headers(token))

    def state(self):
        response = self.get("sessions/" + self.session["session_id"], self.token)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def message(self, value, operator=False, expected=200):
        return self.post("sessions/" + self.session["session_id"] + "/messages",
                         {"expected_version": self.state()["version"], "message": value},
                         self.operator if operator else self.token, expected=expected).json()

    def prepare_run(self):
        self.message({"type": "experiment_request", "request_id": "e1", "purpose": "Osservare.",
            "experiment": {"initial_position": {"x": 0, "y": 0}, "initial_velocity": {"x": 2, "y": 3},
                           "duration": .5, "observation_interval": .25}})
        self.message({"type": "operator_decision", "request_id": "e1", "action": "approve", "reason": "ok"}, True)
        self.message({"type": "execution_mode", "request_id": "e1", "mode": "exploration"}, True)
        return "sessions/" + self.session["session_id"] + "/run", {"expected_version": self.state()["version"], "request_id": "e1"}

    def conclude(self):
        self.message({"type": "conclusion", "final_hypothesis_id": None, "summary": "Dati insufficienti.",
                      "evidence": [], "limits": ["Pochi dati"], "alternatives": ["Altre leggi"]})
        return {"predictions": [{"probe_id": p["probe_id"], "ax": 0, "ay": 0}
                for p in self.state()["events"][-1]["message"]["probes"]]}

    def test_full_cycle_freeze_separate_metrics_audit_and_reveal(self):
        path, body = self.prepare_run()
        with patch("hidden_lab.arena.finish_run", wraps=__import__("hidden_lab.backend_state", fromlist=["finish_run"]).finish_run) as simulate:
            first = self.post(path, body, key="exactly-once-run").json()
            replay = self.post(path, body, key="exactly-once-run").json()
            self.assertEqual(first, replay)
            self.assertEqual(simulate.call_count, 1)
        self.assertEqual(first["executed_experiments"], 1)
        self.message({"type": "hypothesis", "hypothesis_id": "h1", "statement": "Moto regolare", "uncertainties": ["Poco noto"], "evidence": ["e1"]})
        submission = self.conclude()
        scored = self.post("sessions/" + self.session["session_id"] + "/submission",
            {"expected_version": self.state()["version"], "submission": submission}, self.token).json()
        self.assertEqual(scored["status"], "scored")
        self.assertEqual(set(scored["scores"]["prediction"]["by_category"]), {"interpolation", "extrapolation"})
        board = self.get("challenges/" + self.challenge["challenge_id"] + "/leaderboard").json()
        self.assertEqual(board["dimensions"]["acceleration_rmse"][0]["rank"], 1)
        self.assertEqual(board["dimensions"]["ast_nodes"], [])
        self.assertNotIn("combined_score", json.dumps(board))
        self.assertEqual(self.get("challenges/" + self.challenge["challenge_id"] + "/leaderboard", self.token).status_code, 403)
        self.post("challenges/" + self.challenge["challenge_id"] + "/close", {})
        self.assertEqual(self.get("challenges/" + self.challenge["challenge_id"] + "/leaderboard", self.token).status_code, 200)
        sid = self.session["session_id"]
        self.post(f"sessions/{sid}/reveal", {"expected_version": self.state()["version"], "confirm": "reveal"})
        self.assertEqual(self.get(f"sessions/{sid}/reveal").json()["world"], self.world)
        self.assertEqual(self.get(f"sessions/{sid}/reveal", self.token).status_code, 401)
        self.assertGreater(len(self.get("audit").json()["audit"]), 8)

    def test_ownership_operator_actions_and_legacy_bypass(self):
        other = self.post("agents", {"name": "Other", "model": "external"}).json()
        sid = self.session["session_id"]
        self.assertEqual(self.get(f"sessions/{sid}", other["token"]).status_code, 404)
        for suffix in ("", "/events", "/result", "/reveal", "/agent/audit"):
            response = self.client.get(f"/v1/sessions/{sid}{suffix}", headers=self.headers())
            self.assertEqual(response.status_code, 404)
        for suffix in ("messages", "run", "submission", "stop", "score", "reveal", "agent/step"):
            response = self.client.post(f"/v1/sessions/{sid}/{suffix}", json={}, headers=self.headers())
            self.assertEqual(response.status_code, 404)
        self.post(f"sessions/{sid}/run", {"expected_version": 1, "request_id": "e1"}, self.token, expected=401)
        self.assertEqual(self.state()["executed_experiments"], 0)

    def test_version_and_idempotency_conflicts(self):
        path = "/v1/arena/sessions/" + self.session["session_id"] + "/messages"
        self.assertEqual(self.client.post(path, json={}, headers={"X-Zone-Token": self.token}).status_code, 426)
        headers = self.headers(self.token)
        del headers["Idempotency-Key"]
        self.assertEqual(self.client.post(path, json={}, headers=headers).status_code, 400)
        value = {"expected_version": 1, "message": {"type": "hypothesis", "hypothesis_id": "h1", "statement": "Candidata", "uncertainties": [], "evidence": []}}
        self.post(path.removeprefix("/v1/arena/"), value, self.token, key="same-key-test")
        self.post(path.removeprefix("/v1/arena/"), {**value, "expected_version": 2}, self.token, key="same-key-test", expected=409)
        self.assertEqual(self.state()["version"], 2)

    def test_revocation_rotation_expiration_and_persistent_quota(self):
        fresh = self.post(f"agents/{self.agent['agent_id']}/tokens", {}, expected=201).json()
        self.post(f"tokens/{self.agent['token_id']}/revoke", {})
        self.assertEqual(self.get(f"sessions/{self.session['session_id']}", self.token).status_code, 401)
        usage = self.get(f"sessions/{self.session['session_id']}", fresh["token"]).json()["account"]["usage"]
        self.assertEqual(usage["sessions"], 1)
        self.client = self.restart()
        self.assertEqual(self.get(f"sessions/{self.session['session_id']}", self.token).status_code, 401)
        self.assertEqual(self.get(f"sessions/{self.session['session_id']}", fresh["token"]).json()["account"]["usage"], usage)
        with patch.object(self.client.app.state.arena, "clock", return_value=fresh["expires_at"]):
            self.assertEqual(self.get(f"sessions/{self.session['session_id']}", fresh["token"]).status_code, 401)

    def test_tokens_not_stored_in_receipts_audit_or_history(self):
        data = self.get("agents").text + self.get("audit").text + self.get("sessions/" + self.session["session_id"], self.token).text
        with closing(sqlite3.connect(self.db)) as db:
            data += "\n".join(db.iterdump())
        self.assertNotIn(self.token, data)
        self.assertNotIn(self.operator, data)
        key = "token-issuance-once"
        first = self.post(f"agents/{self.agent['agent_id']}/tokens", {}, key=key, expected=201).json()
        second = self.post(f"agents/{self.agent['agent_id']}/tokens", {}, key=key, expected=201).json()
        self.assertIsNotNone(first["token"])
        self.assertIsNone(second["token"])
        self.assertEqual(first["token_id"], second["token_id"])

    def test_invalid_responses_and_bad_json_charge_once(self):
        sid = self.session["session_id"]
        path = f"/v1/arena/sessions/{sid}/messages"
        headers = self.headers(self.token, "bad-json-receipt")
        headers["Content-Type"] = "application/json"
        for _ in range(2):
            self.assertEqual(self.client.post(path, content='{"bad":', headers=headers).status_code, 422)
        self.message({"type": "unknown"}, expected=422)
        usage = self.state()["account"]["usage"]
        self.assertEqual(usage["requests"], 3)  # create, malformed transport, invalid message
        self.assertEqual(usage["invalid"], 2)
        self.assertEqual(self.state()["version"], 1)

    def test_no_silent_approval_and_no_theoretical_operator_help(self):
        self.message({"type": "experiment_request", "request_id": "e1", "purpose": "Osservare", "experiment": {
            "initial_position": {"x": 0, "y": 0}, "initial_velocity": {"x": 0, "y": 0}, "duration": .5, "observation_interval": .25}})
        sid = self.session["session_id"]
        self.post(f"sessions/{sid}/run", {"expected_version": 2, "request_id": "e1"}, expected=422)
        self.assertEqual(self.state()["status"], "awaiting_decision")
        self.message({"type": "operator_decision", "request_id": "e1", "action": "reject", "reason": "Private theory sentinel"}, True)
        self.assertNotIn("Private theory sentinel", json.dumps(self.state()))
        self.message({"type": "operator_question", "question_id": "q1", "question": "Quale legge?", "purpose": "aiuto"}, expected=422)

    def test_crashed_run_never_repeated_after_restart(self):
        path, body = self.prepare_run()
        with patch("hidden_lab.arena.finish_run", side_effect=RuntimeError("PRIVATE_ERROR_SENTINEL")) as run:
            self.post(path, body, key="crashed-run-key", expected=503)
            self.post(path, body, key="crashed-run-key", expected=202)
            self.assertEqual(run.call_count, 1)
        self.client = self.restart()
        self.post(path, body, key="crashed-run-key", expected=202)
        self.assertEqual(self.state()["status"], "execution_started")
        self.assertEqual(self.state()["account"]["usage"]["experiments"], 1)
        self.assertNotIn("PRIVATE_ERROR_SENTINEL", self.get("audit").text)
        self.post("sessions/" + self.session["session_id"] + "/stop", {"expected_version": self.state()["version"], "reason": "interrupted_execution"})
        self.assertEqual(self.state()["status"], "stopped")

    def test_submission_survives_scoring_failure(self):
        submission = self.conclude()
        path = "sessions/" + self.session["session_id"] + "/submission"
        body = {"expected_version": self.state()["version"], "submission": submission}
        with patch("hidden_lab.arena.score_scientific_submission", side_effect=RuntimeError("private")):
            self.post(path, body, self.token, key="frozen-submission", expected=503)
        self.assertEqual(self.state()["status"], "scoring_pending")
        self.post(path, body, self.token, key="frozen-submission", expected=202)
        self.post("sessions/" + self.session["session_id"] + "/score", {"expected_version": self.state()["version"]})
        self.assertEqual(self.state()["status"], "scored")

    def test_concurrent_duplicate_message_across_apps(self):
        second = self.restart()
        path = "/v1/arena/sessions/" + self.session["session_id"] + "/messages"
        body = {"expected_version": 1, "message": {"type": "hypothesis", "hypothesis_id": "h1", "statement": "Ipotesi", "uncertainties": [], "evidence": []}}
        headers = self.headers(self.token, "parallel-message")
        with ThreadPoolExecutor(2) as pool:
            replies = list(pool.map(lambda client: client.post(path, json=body, headers=headers), [self.client, second]))
        self.assertEqual([r.status_code for r in replies], [200, 200])
        self.assertEqual(replies[0].json(), replies[1].json())
        self.assertEqual(self.state()["version"], 2)
        self.assertEqual(self.state()["account"]["usage"]["requests"], 2)

    def test_concurrent_run_receipt_never_starts_second_simulation(self):
        path, body = self.prepare_run()
        second = self.restart()
        entered, release = Event(), Event()
        from hidden_lab.backend_state import finish_run
        def blocked(*args):
            entered.set()
            if not release.wait(10):
                raise RuntimeError("Test synchronization timeout")
            return finish_run(*args)
        headers = self.headers(key="concurrent-run-receipt")
        with patch("hidden_lab.arena.finish_run", side_effect=blocked) as run, ThreadPoolExecutor(1) as pool:
            future = pool.submit(self.client.post, "/v1/arena/" + path, json=body, headers=headers)
            try:
                self.assertTrue(entered.wait(10))
                replay = second.post("/v1/arena/" + path, json=body, headers=headers)
                self.assertEqual(replay.status_code, 202)
                self.assertEqual(self.state()["account"]["usage"]["experiments"], 1)
            finally:
                release.set()
            self.assertEqual(future.result(timeout=10).status_code, 200)
            self.assertEqual(run.call_count, 1)
        self.assertEqual(self.state()["observations"], 1)

    def test_stop_during_run_discards_late_observation(self):
        path, body = self.prepare_run()
        entered, release = Event(), Event()
        from hidden_lab.backend_state import finish_run
        def blocked(*args):
            entered.set()
            if not release.wait(10):
                raise RuntimeError("Test synchronization timeout")
            return finish_run(*args)
        headers = self.headers(key="stopped-run-receipt")
        with patch("hidden_lab.arena.finish_run", side_effect=blocked), ThreadPoolExecutor(1) as pool:
            future = pool.submit(self.client.post, "/v1/arena/" + path, json=body, headers=headers)
            try:
                self.assertTrue(entered.wait(10))
                self.post("sessions/" + self.session["session_id"] + "/stop",
                          {"expected_version": self.state()["version"], "reason": "interrupted_execution"})
            finally:
                release.set()
            self.assertEqual(future.result(timeout=10).status_code, 409)
        self.assertEqual(self.state()["status"], "stopped")
        self.assertEqual(self.state()["executed_experiments"], 1)
        self.assertEqual(self.state()["observations"], 0)

    def test_comparison_rejects_changed_probe_or_limits(self):
        with closing(sqlite3.connect(self.db)) as db:
            rules = {**self.challenge["rules"], "max_points": 8}
            db.execute("UPDATE arena_challenges SET rules_json=?", (json.dumps(rules),))
            db.commit()
        response = self.get("challenges/" + self.challenge["challenge_id"] + "/leaderboard")
        self.assertEqual(response.status_code, 422)

    def test_public_payload_contains_no_private_truth(self):
        public = self.client.get("/v1/arena/contract").text + self.client.get("/v1/arena/challenges").text + json.dumps(self.state())
        for key in ('"seed"', '"law"', '"config"', '"schedule"', '"probe_truth"', '"secret_grid"', '"probes"'):
            self.assertNotIn(key, public)
        self.assertEqual(self.get("audit", self.token).status_code, 401)
        self.assertEqual(self.get("agents", self.token).status_code, 401)

    def test_provider_payload_positive_projection_in_discovery_and_submission(self):
        from hidden_lab.arena_client import model_request
        from hidden_lab.agent_contract import openai_payload
        from hidden_lab.provider_base import AgentSettings
        for snapshot in (self.state(), None):
            if snapshot is None:
                self.conclude()
                snapshot = self.state()
            sentinel = "PRIVATE_CREDENTIAL_OR_LAW_SENTINEL"
            snapshot["config"] = {"law": sentinel}
            snapshot["account"]["token"] = sentinel
            snapshot["rules"]["private_seed"] = sentinel
            snapshot["events"][0]["message"]["private_law"] = sentinel
            request = model_request(snapshot, AgentSettings("offline-affine-v1"), 20)
            payload = json.dumps(openai_payload(request))
            self.assertNotIn(sentinel, payload)
            for private in ('"config"', '"account"', '"token"', '"private_seed"', '"probe_truth"'):
                self.assertNotIn(private, payload)
            self.assertEqual(request.history[0]["message"]["type"], "apparatus")

    def test_leaderboard_ties_stopped_rows_and_missing_dimensions(self):
        for index in range(2):
            if index:
                self.agent = self.post("agents", {"name": "Second", "model": "offline-test"}).json()
                self.token = self.agent["token"]
                self.session = self.post("sessions", {"challenge_id": self.challenge["challenge_id"]}, self.token).json()
            submission = self.conclude()
            self.post("sessions/" + self.session["session_id"] + "/submission",
                      {"expected_version": self.state()["version"], "submission": submission}, self.token)
        another = self.post("agents", {"name": "Stopped", "model": "offline-test"}).json()
        stopped = self.post("sessions", {"challenge_id": self.challenge["challenge_id"]}, another["token"]).json()
        self.post("sessions/" + stopped["session_id"] + "/stop", {"expected_version": 1, "reason": "operator_stop"})
        board = self.get("challenges/" + self.challenge["challenge_id"] + "/leaderboard").json()
        self.assertEqual(len(board["trials"]), 3)
        self.assertEqual([r["rank"] for r in board["dimensions"]["acceleration_rmse"]], [1, 1])
        self.assertEqual(board["dimensions"]["functional_rmse"], [])
        self.assertEqual(board["trials"][-1]["status"], "stopped")
        self.assertIsNone(board["trials"][-1]["resources"]["external_cost"])

    def test_closed_challenge_prevents_trials_and_revealed_world_reuse(self):
        self.post("challenges/" + self.challenge["challenge_id"] + "/close", {}, expected=422)
        self.post("sessions/" + self.session["session_id"] + "/stop", {"expected_version": 1, "reason": "operator_stop"})
        self.post("challenges/" + self.challenge["challenge_id"] + "/close", {})
        agent = self.post("agents", {"name": "Too late", "model": "offline"}).json()
        response = self.client.post("/v1/arena/sessions", json={"challenge_id": self.challenge["challenge_id"]}, headers=self.headers(agent["token"]))
        self.assertEqual(response.status_code, 422)
        self.post("sessions/" + self.session["session_id"] + "/reveal", {"expected_version": self.state()["version"], "confirm": "reveal"})
        response = self.client.post("/v1/arena/challenges", json={"world_id": self.world["world_id"], "name": "Contaminated"}, headers=self.headers())
        self.assertEqual(response.status_code, 422)

    def test_account_session_and_experiment_quotas(self):
        path, body = self.prepare_run()
        with closing(sqlite3.connect(self.db)) as db:
            db.execute("UPDATE arena_agents SET experiments=12 WHERE id=?", (self.agent["agent_id"],))
            db.commit()
        self.post(path, body, expected=429)
        self.assertEqual(self.state()["status"], "ready_to_run")
        self.assertEqual(self.state()["executed_experiments"], 0)
        with closing(sqlite3.connect(self.db)) as db:
            db.execute("UPDATE arena_agents SET experiments=0,sessions=4 WHERE id=?", (self.agent["agent_id"],))
            db.commit()
        other = self.post("challenges", {"world_id": self.world["world_id"], "name": "Other challenge"}).json()
        response = self.client.post("/v1/arena/sessions", json={"challenge_id": other["challenge_id"]}, headers=self.headers(self.token))
        self.assertEqual(response.status_code, 429)

    def test_public_world_reveal_blocked_during_arena(self):
        created = self.client.post("/v1/sessions", json={"world_id": self.world["world_id"]}, headers=self.headers()).json()
        sid = created["session_id"]
        self.assertEqual(self.client.post(f"/v1/sessions/{sid}/stop", json={"expected_version": 1, "reason": "operator_stop"}, headers=self.headers()).status_code, 200)
        self.assertEqual(self.client.post(f"/v1/sessions/{sid}/reveal", json={"expected_version": 2, "confirm": "reveal"}, headers=self.headers()).status_code, 422)

    def test_invalid_id_types_are_safe_and_do_not_mutate(self):
        for path, body in (("challenges", {"world_id": [], "name": "bad"}), ("sessions", {"challenge_id": []})):
            response = self.client.post("/v1/arena/" + path, json=body, headers=self.headers(self.operator if path == "challenges" else self.token))
            self.assertIn(response.status_code, (404, 422))
        self.assertEqual(self.state()["version"], 1)

    def test_quota_cannot_reset_with_new_token_and_invalid_requests(self):
        with closing(sqlite3.connect(self.db)) as db:
            db.execute("UPDATE arena_agents SET quotas_json=? WHERE id=?", (json.dumps({"sessions": 1, "requests": 2, "experiments": 1}), self.agent["agent_id"]))
            db.commit()
        self.message({"type": "unknown"}, expected=422)
        fresh = self.post(f"agents/{self.agent['agent_id']}/tokens", {}, expected=201).json()
        self.token = fresh["token"]
        self.message({"type": "unknown"}, expected=429)
        self.assertEqual(self.state()["account"]["usage"]["requests"], 2)
