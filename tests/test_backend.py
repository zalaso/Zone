import importlib.util
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

if importlib.util.find_spec("fastapi") is not None:
    from fastapi.testclient import TestClient
    from hidden_lab.backend import RateLimiter, create_app
    from hidden_lab.backend_store import SQLiteRepository
    from hidden_lab.simulator import acceleration_at, parse_config
    from hidden_lab.world_forge import generate_world


@unittest.skipUnless(importlib.util.find_spec("fastapi") is not None, "Installare l'extra backend")
class BackendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.world = generate_world(123456789, 1)
        cls.operator_token = "operator-token-for-offline-tests-only-123456789"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.database = Path(self.temp.name) / "zone.sqlite3"
        self.app = create_app(self.database, worlds=[self.world], operator_token=self.operator_token)
        self.client = TestClient(self.app)
        self.addCleanup(self.client.close)

    def create(self):
        response = self.client.post("/v1/sessions", json={"world_id": self.world["world_id"]},
            headers={"x-zone-token": self.operator_token})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def send(self, session_id, token, version, message):
        return self.client.post(f"/v1/sessions/{session_id}/messages",
            json={"expected_version": version, "message": message}, headers={"x-zone-token": token})

    def test_complete_cycle_replay_privacy_and_controlled_reveal(self):
        listing = self.client.get("/v1/worlds")
        self.assertEqual(listing.status_code, 200)
        for forbidden in ('"seed"', '"law"', '"config"', '"probes"'):
            self.assertNotIn(forbidden, listing.text)
        created = self.create()
        sid, agent = created["session_id"], created["agent_token"]
        with closing(sqlite3.connect(self.database)) as db:
            saved_hash = db.execute("SELECT agent_token_hash FROM sessions WHERE id=?", (sid,)).fetchone()[0]
        self.assertNotEqual(saved_hash, agent)
        self.assertEqual(created["status"], "discovering")
        self.assertNotIn("agent_token", self.client.get(f"/v1/sessions/{sid}").text)
        experiment = {"initial_position": {"x": 0, "y": 0},
                      "initial_velocity": {"x": 1, "y": 2},
                      "duration": 0.5, "observation_interval": 0.25}
        modified = {**experiment, "initial_velocity": {"x": 2, "y": 3}}
        request = {"type": "experiment_request", "request_id": "e1", "purpose": "Misurare il moto.",
                   "experiment": experiment}
        r = self.send(sid, agent, 1, request)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["status"], "awaiting_decision")
        self.assertEqual(self.client.post(f"/v1/sessions/{sid}/run",
            json={"expected_version": 2, "request_id": "e1"},
            headers={"x-zone-token": self.operator_token}).status_code, 422)
        decision = {"type": "operator_decision", "request_id": "e1", "action": "modify",
                    "reason": "Confronto controllato.", "modified_experiment": modified}
        r = self.send(sid, self.operator_token, 2, decision)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["status"], "awaiting_mode")
        r = self.send(sid, self.operator_token, 3,
                      {"type": "execution_mode", "request_id": "e1", "mode": "verification"})
        self.assertEqual(r.json()["status"], "awaiting_prediction")
        hypothesis = {"type": "hypothesis", "hypothesis_id": "h1", "statement": "Moto regolare.",
                      "uncertainties": ["Pochi dati."], "evidence": []}
        self.assertEqual(self.send(sid, agent, 4, hypothesis).status_code, 200)
        prediction = {"type": "prediction", "prediction_id": "p1", "hypothesis_id": "h1",
                      "request_id": "e1", "points": [{"t": t, "x": 0, "y": 0} for t in (0, .25, .5)]}
        self.assertEqual(self.send(sid, agent, 5, prediction).status_code, 200)
        run = self.client.post(f"/v1/sessions/{sid}/run", json={"expected_version": 6, "request_id": "e1"},
                               headers={"x-zone-token": self.operator_token})
        self.assertEqual(run.status_code, 200, run.text)
        self.assertEqual(run.json()["executed_experiments"], 1)
        self.assertEqual(run.json()["version"], 9)
        replay = self.client.get(f"/v1/sessions/{sid}/events").json()["events"]
        self.assertEqual([event["message"]["type"] for event in replay[-3:]],
                         ["execution_started", "observation", "verification"])
        self.assertEqual(replay[-3]["message"]["experiment"], modified)
        self.assertEqual(self.client.post(f"/v1/sessions/{sid}/run",
            json={"expected_version": 6, "request_id": "e1"},
            headers={"x-zone-token": self.operator_token}).status_code, 409)
        conclusion = {"type": "conclusion", "final_hypothesis_id": "h1",
                      "summary": "Legge candidata.", "evidence": ["e1"],
                      "limits": ["Una sola misura."], "alternatives": ["Altre leggi."]}
        closed = self.send(sid, agent, 9, conclusion)
        self.assertEqual(closed.status_code, 200, closed.text)
        self.assertEqual(closed.json()["status"], "awaiting_submission")
        public = self.client.get(f"/v1/sessions/{sid}/events").json()["events"]
        challenge = public[-1]["message"]
        self.assertEqual(challenge["type"], "probe_challenge")
        self.assertEqual(len(challenge["probes"]), 6)
        self.assertEqual(self.client.get(f"/v1/sessions/{sid}/result").status_code, 404)
        self.assertEqual(self.client.post(f"/v1/sessions/{sid}/reveal",
            json={"expected_version": 11, "confirm": "reveal"},
            headers={"x-zone-token": self.operator_token}).status_code, 422)
        world = parse_config(self.world["config"]).world
        predictions = []
        for probe in challenge["probes"]:
            ax, ay = acceleration_at(world, tuple(probe[key] for key in ("x", "y", "vx", "vy")))
            predictions.append({"probe_id": probe["probe_id"], "ax": ax, "ay": ay})
        submission = {"predictions": predictions,
                      "law_ast_json": json.dumps(self.world["config"]["world"]["law"]),
                      "uncertainty_sigma": [0.5] * len(predictions)}
        scored = self.client.post(f"/v1/sessions/{sid}/submission",
            json={"expected_version": 11, "submission": submission},
            headers={"x-zone-token": agent})
        self.assertEqual(scored.status_code, 200, scored.text)
        self.assertEqual(scored.json()["status"], "scored")
        result = self.client.get(f"/v1/sessions/{sid}/result").json()["scores"]
        self.assertEqual(result["prediction"]["acceleration_rmse"], 0)
        self.assertTrue(result["functional"]["empirically_equivalent"])
        public_text = self.client.get(f"/v1/sessions/{sid}/events").text
        self.assertNotIn('"seed"', public_text)
        self.assertNotIn("secret_grid", public_text)
        self.assertNotIn("probe_truth", public_text)
        self.assertEqual(self.client.post(f"/v1/sessions/{sid}/reveal",
            json={"expected_version": scored.json()["version"], "confirm": "reveal"},
            headers={"x-zone-token": agent}).status_code, 401)
        revealed = self.client.post(f"/v1/sessions/{sid}/reveal",
            json={"expected_version": scored.json()["version"], "confirm": "reveal"},
            headers={"x-zone-token": self.operator_token})
        self.assertEqual(revealed.status_code, 200, revealed.text)
        self.assertEqual(revealed.json()["world"], self.world)
        self.assertEqual(len(revealed.json()["audit"]["secret_grid"]), 128)
        self.assertNotIn('"seed"', self.client.get(f"/v1/sessions/{sid}/events").text)
        reopened = TestClient(create_app(self.database, operator_token=self.operator_token))
        self.addCleanup(reopened.close)
        self.assertEqual(reopened.get(f"/v1/sessions/{sid}").json()["status"], "revealed")
        self.assertEqual(reopened.get(f"/v1/sessions/{sid}/events?after=9").json()["events"][0]["seq"], 10)

    def test_roles_input_limits_and_no_silent_approval(self):
        self.assertEqual(self.client.post("/v1/sessions", json={"world_id": self.world["world_id"]}).status_code, 401)
        created = self.create()
        sid, agent = created["session_id"], created["agent_token"]
        question = {"type": "operator_question", "question_id": "q1", "question": "Indicazioni?",
                    "purpose": "Chiarire."}
        self.assertEqual(self.send(sid, agent, 1, question).json()["status"], "awaiting_answer")
        self.assertEqual(self.send(sid, agent, 2, {"type": "conclusion", "final_hypothesis_id": None,
            "summary": "Stop", "evidence": [], "limits": ["Pochi dati"], "alternatives": []}).status_code, 422)
        self.assertEqual(self.send(sid, agent, 2,
            {"type": "operator_answer", "question_id": "q1", "answer": "Nessun suggerimento."}).status_code, 401)
        self.assertEqual(self.send(sid, self.operator_token, 2,
            {"type": "operator_answer", "question_id": "q1", "answer": "Nessun suggerimento."}).status_code, 200)
        duplicate = '{"expected_version":3,"expected_version":3,"message":{}}'
        self.assertEqual(self.client.post(f"/v1/sessions/{sid}/messages", content=duplicate,
            headers={"x-zone-token": agent, "content-type": "application/json"}).status_code, 422)
        self.assertEqual(self.client.post(f"/v1/sessions/{sid}/messages", content="x" * 65000,
            headers={"x-zone-token": agent, "content-type": "application/json"}).status_code, 413)
        self.assertEqual(self.client.post(f"/v1/sessions/{sid}/messages", content="{}",
            headers={"x-zone-token": agent, "content-type": "text/plain"}).status_code, 415)
        repository = SQLiteRepository(self.database)
        repository.append(sid, 3, [("apparatus", {"type": "protocol_error", "message": "Messaggio invalido.",
                                                 "private": "SECRET_SENTINEL"})])
        self.assertNotIn("SECRET_SENTINEL", self.client.get(f"/v1/sessions/{sid}/events").text)

    def test_rate_limit_and_crash_does_not_repeat_experiment(self):
        limiter = RateLimiter(read=20, write=20, run=1)
        app = create_app(self.database, operator_token=self.operator_token, rate_limiter=limiter)
        client = TestClient(app, raise_server_exceptions=False)
        self.addCleanup(client.close)
        created = self.create()
        sid, agent = created["session_id"], created["agent_token"]
        experiment = {"initial_position": {"x": 0, "y": 0}, "initial_velocity": {"x": 1, "y": 1},
                      "duration": 0.5, "observation_interval": 0.25}
        self.assertEqual(self.send(sid, agent, 1, {"type": "experiment_request", "request_id": "e1",
            "purpose": "Misura", "experiment": experiment}).status_code, 200)
        self.assertEqual(self.send(sid, self.operator_token, 2, {"type": "operator_decision",
            "request_id": "e1", "action": "approve", "reason": "Va bene"}).status_code, 200)
        self.assertEqual(self.send(sid, self.operator_token, 3, {"type": "execution_mode",
            "request_id": "e1", "mode": "exploration"}).status_code, 200)
        with patch("hidden_lab.backend.finish_run", side_effect=RuntimeError("private sentinel")):
            crashed = client.post(f"/v1/sessions/{sid}/run",
                json={"expected_version": 4, "request_id": "e1"},
                headers={"x-zone-token": self.operator_token})
        self.assertEqual(crashed.status_code, 500)
        self.assertNotIn("private sentinel", crashed.text)
        self.assertEqual(client.get(f"/v1/sessions/{sid}").json()["status"], "execution_started")
        self.assertEqual(client.get(f"/v1/sessions/{sid}").json()["executed_experiments"], 1)
        self.assertEqual(client.post(f"/v1/sessions/{sid}/run",
            json={"expected_version": 5, "request_id": "e1"},
            headers={"x-zone-token": self.operator_token}).status_code, 429)
        # Anche senza rate limit, lo stato impedisce di ripetere l'esperimento.
        self.assertEqual(self.client.post(f"/v1/sessions/{sid}/run",
            json={"expected_version": 5, "request_id": "e1"},
            headers={"x-zone-token": self.operator_token}).status_code, 422)
        stopped = self.client.post(f"/v1/sessions/{sid}/stop",
            json={"expected_version": 5, "reason": "interrupted_execution"},
            headers={"x-zone-token": self.operator_token})
        self.assertEqual(stopped.json()["status"], "stopped")
        self.assertEqual(self.client.get(f"/v1/sessions/{sid}/events").json()["events"][-2]["message"]["type"],
                         "execution_started")
        reveal = self.client.post(f"/v1/sessions/{sid}/reveal",
            json={"expected_version": stopped.json()["version"], "confirm": "reveal"},
            headers={"x-zone-token": self.operator_token})
        self.assertEqual(reveal.status_code, 200, reveal.text)
        self.assertIsNone(reveal.json()["audit"])

    def test_scoring_can_resume_without_resubmission(self):
        created = self.create()
        sid, agent = created["session_id"], created["agent_token"]
        conclusion = {"type": "conclusion", "final_hypothesis_id": None,
                      "summary": "Informazioni insufficienti.", "evidence": [],
                      "limits": ["Nessuna misura"], "alternatives": ["Più leggi"]}
        closed = self.send(sid, agent, 1, conclusion)
        self.assertEqual(closed.json()["version"], 3)
        probes = self.client.get(f"/v1/sessions/{sid}/events").json()["events"][-1]["message"]["probes"]
        submission = {"predictions": [{"probe_id": probe["probe_id"], "ax": 0, "ay": 0}
                                      for probe in probes]}
        with patch("hidden_lab.backend.score_scientific_submission", side_effect=RuntimeError("temporary")):
            crashing = TestClient(self.app, raise_server_exceptions=False)
            self.addCleanup(crashing.close)
            failed = crashing.post(f"/v1/sessions/{sid}/submission",
                json={"expected_version": 3, "submission": submission},
                headers={"x-zone-token": agent})
        self.assertEqual(failed.status_code, 500)
        self.assertEqual(self.client.get(f"/v1/sessions/{sid}").json()["status"], "scoring_pending")
        self.assertEqual(self.client.post(f"/v1/sessions/{sid}/submission",
            json={"expected_version": 4, "submission": submission},
            headers={"x-zone-token": agent}).status_code, 422)
        resumed = self.client.post(f"/v1/sessions/{sid}/score",
            json={"expected_version": 4}, headers={"x-zone-token": self.operator_token})
        self.assertEqual(resumed.status_code, 200, resumed.text)
        self.assertEqual(resumed.json()["status"], "scored")
        self.assertIsNotNone(self.client.get(f"/v1/sessions/{sid}/result").json()["scores"]["prediction"])
