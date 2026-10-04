"""Modalità locali: provider simulati, approvazione esplicita e parità scientifica."""

import copy
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
from datetime import date
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
from threading import Event
import time
import unittest

from hidden_lab.agent_contract import openai_payload
from hidden_lab.backend_state import LabState
from hidden_lab.backend_store import SQLiteRepository
from hidden_lab.local_worlds import build_world, local_manifest, validate_built_world
from hidden_lab.protocol import ValidationError
from hidden_lab.provider_base import AgentSettings, ModelReply, ProviderError
from hidden_lab.web_agent import OfflineLabClient, build_web_request, safe_generation, safe_metadata
from hidden_lab.world_forge import generate_world

if importlib.util.find_spec("fastapi") is not None:
    from fastapi.testclient import TestClient
    from hidden_lab.backend import RateLimiter, create_app

TOKEN = "local-test-operator-token-only-123456789"
LAW = {"level": 1, "ax": {"op": "const", "value": 1}, "ay": {"op": "const", "value": -4}}


class RecordingClient(OfflineLabClient):
    def __init__(self, replies=()):
        self.requests = []
        self.replies = list(replies)

    def complete(self, request):
        self.requests.append(request)
        if self.replies:
            value = self.replies.pop(0)
            if isinstance(value, Exception):
                raise value
            if callable(value):
                return value(request)
            return value
        return super().complete(request)


@unittest.skipUnless(importlib.util.find_spec("fastapi") is not None, "Installare l'extra backend")
class PublicModesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.world = generate_world(73152, 2, 2)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "zone.sqlite3"
        self.repo = SQLiteRepository(self.db, [self.world])
        self.model = RecordingClient()
        self.settings = AgentSettings("offline-affine-v1")
        self.client = self.app()
        self.headers = {"x-zone-token": TOKEN}

    def app(self, **kwargs):
        client = TestClient(create_app(repository=self.repo, operator_token=TOKEN,
            agent_client=self.model, agent_settings=self.settings,
            rate_limiter=RateLimiter(read=10000, write=10000, run=10000), **kwargs))
        self.addCleanup(client.close)
        return client

    def create(self, mode="watch_agent"):
        result = self.client.post("/v1/sessions", headers=self.headers,
            json={"world_id": self.world["world_id"], "mode": mode})
        self.assertEqual(result.status_code, 201, result.text)
        return result.json()

    def status(self, sid):
        return self.client.get(f"/v1/sessions/{sid}").json()

    def step(self, sid):
        return self.client.post(f"/v1/sessions/{sid}/agent/step", headers=self.headers,
                                json={"expected_version": self.status(sid)["version"]})

    def message(self, sid, message, token=TOKEN):
        return self.client.post(f"/v1/sessions/{sid}/messages", headers={"x-zone-token": token},
            json={"expected_version": self.status(sid)["version"], "message": message})

    def advance(self, sid):
        snapshot = self.status(sid)
        rid = snapshot["pending_request_id"]
        if snapshot["status"] in ("discovering", "awaiting_prediction", "awaiting_submission"):
            result = self.step(sid)
        elif snapshot["status"] == "awaiting_decision":
            result = self.message(sid, {"type": "operator_decision", "request_id": rid,
                "action": "approve", "reason": "Parametri validi."})
        elif snapshot["status"] == "awaiting_mode":
            result = self.message(sid, {"type": "execution_mode", "request_id": rid, "mode": "exploration"})
        elif snapshot["status"] == "ready_to_run":
            result = self.client.post(f"/v1/sessions/{sid}/run", headers=self.headers,
                json={"expected_version": snapshot["version"], "request_id": rid})
        else:
            self.fail(f"Stato inatteso {snapshot['status']}")
        self.assertEqual(result.status_code, 200, result.text)

    def finish(self, sid):
        for _ in range(50):
            if self.status(sid)["status"] == "scored":
                return
            self.advance(sid)
        self.fail("Ciclo non terminato")

    def conclude_human(self, sid, token):
        result = self.message(sid, {"type": "conclusion", "final_hypothesis_id": None,
            "summary": "Dati insufficienti.", "evidence": [], "limits": ["Nessuna misura."],
            "alternatives": ["Molte leggi plausibili."]}, token)
        self.assertEqual(result.status_code, 200, result.text)
        challenge = self.repo.read_session(sid)["events"][-1]["message"]
        return {"predictions": [{"probe_id": p["probe_id"], "ax": 0, "ay": 0} for p in challenge["probes"]]}

    def test_watch_complete_cycle_and_restart_keeps_resources(self):
        created = self.create()
        self.assertIsNone(created["agent_token"])
        sid = created["session_id"]
        self.advance(sid)  # initial hypothesis
        self.advance(sid)  # proposal, still no execution
        self.assertEqual(self.status(sid)["executed_experiments"], 0)
        self.assertEqual(self.step(sid).status_code, 422)
        self.finish(sid)
        record = self.repo.read_session(sid)
        kinds = [e["message"]["type"] for e in record["events"]]
        self.assertEqual(kinds[-3:], ["probe_challenge", "scientific_submission", "result_recorded"])
        self.assertEqual(kinds.count("observation"), 2)
        for index, kind in enumerate(kinds):
            if kind == "observation":
                self.assertEqual(kinds[index-1], "execution_started")
                self.assertEqual(kinds[index+1], "hypothesis")
        restarted = self.app()
        snapshot = restarted.get(f"/v1/sessions/{sid}").json()
        self.assertEqual(snapshot["agent"]["calls"], len(record["calls"]))
        self.assertEqual(snapshot["agent"]["turns"], len(record["calls"]))
        self.assertFalse(snapshot["agent"]["real_model"])
        self.assertEqual(self.client.get(f"/v1/sessions/{sid}/agent/audit").status_code, 401)
        audit = self.client.get(f"/v1/sessions/{sid}/agent/audit", headers=self.headers)
        self.assertNotIn(TOKEN, audit.text)
        self.assertNotIn('"config"', audit.text)

    def test_watch_modify_prediction_and_reject(self):
        sid = self.create()["session_id"]
        self.advance(sid); self.advance(sid)
        rid = self.status(sid)["pending_request_id"]
        self.message(sid, {"type": "operator_decision", "request_id": rid, "action": "reject", "reason": "Altro controllo."})
        self.advance(sid)
        rid = self.status(sid)["pending_request_id"]
        experiment = copy.deepcopy(self.repo.read_session(sid)["events"][-1]["message"]["experiment"])
        experiment["duration"] = .25
        experiment["initial_velocity"]["x"] = 8
        modified = self.message(sid, {"type": "operator_decision", "request_id": rid, "action": "modify",
            "modified_experiment": experiment, "reason": "Verifica breve."})
        self.assertEqual(modified.status_code, 200, modified.text)
        self.message(sid, {"type": "execution_mode", "request_id": rid, "mode": "verification"})
        self.advance(sid)
        payload = self.model.requests[-1]
        self.assertEqual(payload.context["approved_experiment"], experiment)
        self.assertEqual(payload.context["prediction_times"], [0., .25])
        self.assertEqual(self.status(sid)["status"], "ready_to_run")
        self.assertEqual(self.status(sid)["executed_experiments"], 0)
        self.advance(sid)
        self.assertEqual(self.status(sid)["executed_experiments"], 1)

    def test_invalid_correction_and_network_error_never_runs_experiment(self):
        self.model.replies = [ModelReply("not json", {"usage": {"input_tokens": 7, "secret": TOKEN}})]
        sid = self.create()["session_id"]
        result = self.step(sid)
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(self.status(sid)["agent"]["calls"], 2)
        self.assertEqual(self.status(sid)["agent"]["invalid_responses"], 1)
        self.assertIn("correction", self.model.requests[-1].context)
        self.model.replies = [ProviderError("connection")]
        self.assertEqual(self.step(sid).status_code, 503)
        self.assertEqual(self.status(sid)["executed_experiments"], 0)
        self.assertEqual(len(self.model.requests), 3)  # network errors are not retried
        self.assertEqual(self.step(sid).status_code, 200)
        self.assertEqual(self.status(sid)["status"], "awaiting_decision")
        self.assertEqual(self.status(sid)["executed_experiments"], 0)
        self.assertNotIn(TOKEN, json.dumps(self.repo.read_session(sid)["calls"]))

    def test_call_budget_and_turn_budget_are_persistent_and_independent(self):
        self.settings = AgentSettings("offline-affine-v1", max_calls=2, max_turns=15, max_corrections=0)
        self.client = self.app()
        sid = self.create()["session_id"]
        self.advance(sid)  # two calls left: conclude, preserving the last call for submission
        self.assertEqual(self.status(sid)["status"], "awaiting_submission")
        self.advance(sid)
        self.assertEqual(self.status(sid)["status"], "scored")
        self.assertEqual(self.step(sid).status_code, 422)
        self.assertEqual(self.status(sid)["remaining_experiments"], 2)
        self.assertEqual(len(self.model.requests), 2)
        self.client = self.app()
        self.assertEqual(self.step(sid).status_code, 422)
        self.settings = AgentSettings("offline-affine-v1", max_calls=20, max_turns=2)
        self.client = self.app()
        other = self.create()["session_id"]
        self.finish(other)
        self.assertEqual(self.status(other)["agent"]["turns"], 2)
        self.assertEqual(self.status(other)["agent"]["calls"], 2)
        self.assertEqual(self.status(other)["executed_experiments"], 0)

    def test_timeout_late_reply_is_not_committed(self):
        self.settings = AgentSettings("offline-affine-v1", timeout=1)
        self.client = self.app()
        self.model.replies = [lambda request: (time.sleep(1.15), OfflineLabClient().complete(request))[1]]
        sid = self.create()["session_id"]
        result = self.step(sid)
        self.assertEqual(result.status_code, 503, result.text)
        time.sleep(.2)
        self.assertEqual(self.status(sid)["version"], 1)
        self.assertEqual(self.status(sid)["executed_experiments"], 0)

    def test_payload_boundary_all_phases_and_separate_histories(self):
        sid = self.create()["session_id"]
        self.finish(sid)
        for request in self.model.requests:
            payload = json.dumps(openai_payload(request))
            for secret in ('"config"', '"seed"', '"law"', '"schedule"', 'secret_grid', 'probe_truth', TOKEN,
                           'README', 'generator_seed', 'phase6', 'family'):
                self.assertNotIn(secret, payload)
            self.assertFalse(hasattr(request, "session"))
            self.assertEqual(openai_payload(request)["tools"], [])
            if request.context["phase"] != "submission":
                self.assertNotIn('"probe_id"', request.user_content())
        events = copy.deepcopy(self.repo.read_session(sid)["events"])
        for event in events:
            event["message"]["config"] = {"secret": TOKEN}
        state = LabState(events[:1], 2)
        request = build_web_request(events[:1], self.settings, state, 20, 15)
        self.assertNotIn(TOKEN, request.user_content())

    def test_match_equal_conditions_freeze_then_agent_and_delayed_scores(self):
        response = self.client.post("/v1/matches", json={"world_id": self.world["world_id"]}, headers=self.headers)
        self.assertEqual(response.status_code, 201, response.text)
        match = response.json()
        human, agent = match["human_session_id"], match["agent_session_id"]
        self.assertEqual(self.step(agent).status_code, 422)
        self.assertEqual(self.repo.read_session(human)["record"], self.repo.read_session(agent)["record"])
        self.assertEqual(self.status(human)["remaining_experiments"], self.status(agent)["remaining_experiments"])
        experiment = {"initial_position": {"x": 0, "y": 0}, "initial_velocity": {"x": 1, "y": 1},
                      "duration": 1, "observation_interval": .1}  # 11 points: prohibited on both sides
        denied = self.message(human, {"type": "experiment_request", "request_id": "dense",
            "experiment": experiment, "purpose": "Dense sampling."}, match["human_agent_token"])
        self.assertEqual(denied.status_code, 422)
        submission = self.conclude_human(human, match["human_agent_token"])
        frozen = self.client.post(f"/v1/sessions/{human}/submission", headers={"x-zone-token": match["human_agent_token"]},
            json={"expected_version": self.status(human)["version"], "submission": submission})
        self.assertEqual(frozen.status_code, 200, frozen.text)
        self.assertEqual(frozen.json()["status"], "scoring_pending")
        self.assertEqual(self.client.get(f"/v1/sessions/{human}/result").status_code, 404)
        self.assertEqual(self.client.post(f"/v1/sessions/{human}/score", headers=self.headers,
            json={"expected_version": self.status(human)["version"]}).status_code, 422)
        self.finish(agent)
        compared = self.client.get(f"/v1/matches/{match['match_id']}").json()
        self.assertTrue(compared["complete"])
        self.assertEqual(compared["human"]["scores"], self.repo.read_session(human)["score"])
        self.assertNotIn("winner", compared)
        for request in self.model.requests:
            self.assertNotIn("Dati insufficienti.", request.user_content())
            self.assertNotIn("operator_question", request.allowed_types)
        # Incompatibility rejects the comparison, rather than producing misleading numbers.
        with closing(sqlite3.connect(self.db)) as db:
            rules = {**match["rules"], "max_points": 8}
            db.execute("UPDATE matches SET rules_json=? WHERE id=?", (json.dumps(rules), match["match_id"]))
            db.commit()
        self.assertEqual(self.client.get(f"/v1/matches/{match['match_id']}").status_code, 422)

    def test_match_prohibits_guidance_modification_and_early_reveal(self):
        match = self.client.post("/v1/matches", json={"world_id": self.world["world_id"]}, headers=self.headers).json()
        human, agent = match["human_session_id"], match["agent_session_id"]
        token = match["human_agent_token"]
        question = self.message(human, {"type": "operator_question", "question_id": "q1", "question": "Quale legge?",
                                       "purpose": "Suggerimento."}, token)
        self.assertEqual(question.status_code, 422)
        experiment = {"initial_position": {"x": 0, "y": 0}, "initial_velocity": {"x": 1, "y": 1},
                      "duration": .5, "observation_interval": .25}
        self.message(human, {"type": "experiment_request", "request_id": "e1", "purpose": "Misura.", "experiment": experiment}, token)
        rejected = self.message(human, {"type": "operator_decision", "request_id": "e1", "action": "reject", "reason": "No."})
        self.assertEqual(rejected.status_code, 422)
        self.message(human, {"type": "operator_decision", "request_id": "e1", "action": "approve", "reason": "OK."})
        verification = self.message(human, {"type": "execution_mode", "request_id": "e1", "mode": "verification"})
        self.assertEqual(verification.status_code, 422)
        self.client.post(f"/v1/sessions/{human}/stop", headers=self.headers,
            json={"expected_version": self.status(human)["version"], "reason": "operator_stop"})
        reveal = self.client.post(f"/v1/sessions/{human}/reveal", headers=self.headers,
            json={"expected_version": self.status(human)["version"], "confirm": "reveal"})
        self.assertEqual(reveal.status_code, 422)
        self.assertEqual(self.status(agent)["executed_experiments"], 0)

    def test_daily_world_persists_across_restart_and_changes_with_utc_day(self):
        self.client = self.app(day_clock=lambda: date(2026, 10, 4))
        first = self.client.get("/v1/worlds/daily")
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(self.create("scientist")["status"], "discovering")
        denied = self.client.post("/v1/sessions", headers=self.headers,
            json={"world_id": self.world["world_id"], "mode": "world_of_day"})
        self.assertEqual(denied.status_code, 422)
        self.client = self.app(day_clock=lambda: date(2026, 10, 4))
        self.assertEqual(first.json(), self.client.get("/v1/worlds/daily").json())
        self.client = self.app(day_clock=lambda: date(2026, 10, 5))
        self.assertNotEqual(first.json()["world"]["world_id"], self.client.get("/v1/worlds/daily").json()["world"]["world_id"])
        for forbidden in ('"seed"', '"law"', '"probes"', '"config"'):
            self.assertNotIn(forbidden, first.text)

    def test_builder_validation_registration_and_author_exclusion(self):
        endpoint = "/v1/worlds/build"
        self.assertEqual(self.client.post(endpoint, json={"law": LAW, "budget": 2}).status_code, 401)
        built = self.client.post(endpoint, headers=self.headers, json={"law": LAW, "budget": 2, "seed": 4})
        self.assertEqual(built.status_code, 201, built.text)
        manifest = built.json()["world"]
        for forbidden in ('"seed"', '"law"', '"probes"', '"config"'):
            self.assertNotIn(forbidden, built.text)
        created = self.client.post("/v1/sessions", headers=self.headers,
            json={"world_id": manifest["world_id"], "mode": "watch_agent"}).json()
        self.finish(created["session_id"])
        self.assertEqual(self.client.post("/v1/matches", headers=self.headers,
            json={"world_id": manifest["world_id"]}).status_code, 422)
        for law in ({**LAW, "ax": {"op": "eval", "value": "open('secret')"}},
                    {**LAW, "ax": {"op": "div", "args": [{"op": "const", "value": 1}, {"op": "var", "name": "x"}] }},
                    {**LAW, "ax": {"op": "const", "value": 0}, "ay": {"op": "const", "value": 0}}):
            self.assertEqual(self.client.post(endpoint, headers=self.headers,
                json={"law": law, "budget": 2}).status_code, 422)
        record = build_world(LAW, 2, 4)
        self.assertEqual(local_manifest(record), manifest)
        record["probes"][0]["x"] = 999
        with self.assertRaises(ValidationError):
            validate_built_world(record)

    def test_provider_metadata_preserves_native_counts_and_excludes_extra_fields(self):
        reply = ModelReply("", {"response_id": "r1", "returned_model": "m1", "status": "completed",
            "usage": {"input_tokens": 20, "input_tokens_details": {"cached_tokens": 4, "secret": TOKEN},
                      "output_tokens": 10, "secret": TOKEN},
            "provider_details": {"usage": {"thoughts_token_count": 3, "secret": TOKEN}, "secret": TOKEN}})
        clean = safe_metadata(reply)
        self.assertEqual(clean["usage"]["input_tokens_details"], {"cached_tokens": 4})
        self.assertEqual(clean["provider_details"]["usage"], {"thoughts_token_count": 3})
        self.model.generation_settings = {"max_tokens": 2500, "tools": [], "api_key": TOKEN}
        self.assertEqual(safe_generation(self.model), {"max_tokens": 2500, "tools": []})
        self.assertNotIn(TOKEN, json.dumps(clean))

    def test_error_after_an_observation_does_not_repeat_completed_experiment(self):
        sid = self.create()["session_id"]
        for _ in range(5):
            self.advance(sid)
        self.assertEqual(self.status(sid)["executed_experiments"], 1)
        self.model.replies = [ProviderError("connection")]
        self.assertEqual(self.step(sid).status_code, 503)
        self.assertEqual(self.status(sid)["executed_experiments"], 1)
        self.assertEqual(self.step(sid).status_code, 200)
        observations = [e for e in self.repo.read_session(sid)["events"] if e["message"]["type"] == "observation"]
        self.assertEqual(len(observations), 1)

    def test_concurrent_step_and_stale_reply_do_not_commit_or_spend_twice(self):
        entered, release = Event(), Event()
        def delayed(request):
            entered.set()
            release.wait(5)
            return OfflineLabClient().complete(request)
        self.model.replies = [delayed]
        sid = self.create()["session_id"]
        # Keep TestClient's portal alive while two requests overlap.
        with self.client, ThreadPoolExecutor(max_workers=1) as pool:
            first = pool.submit(self.step, sid)
            self.assertTrue(entered.wait(3))
            try:
                duplicate = self.step(sid)
                self.assertEqual(duplicate.status_code, 409, duplicate.text)
                stopped = self.client.post(f"/v1/sessions/{sid}/stop", headers=self.headers,
                    json={"expected_version": 1, "reason": "operator_stop"})
                self.assertEqual(stopped.status_code, 200, stopped.text)
            finally:
                release.set()
            self.assertEqual(first.result(timeout=5).status_code, 409)
        record = self.repo.read_session(sid)
        self.assertEqual(len(record["calls"]), 1)
        self.assertEqual(record["calls"][0]["outcome"], "stale")
        self.assertEqual(len(record["events"]), 2)
        self.assertEqual(self.status(sid)["executed_experiments"], 0)

    def test_stop_after_call_exhaustion_and_frozen_match_preserves_submission(self):
        self.settings = AgentSettings("offline-affine-v1", max_calls=1)
        self.client = self.app()
        sid = self.create()["session_id"]
        self.advance(sid)
        self.assertEqual(self.status(sid)["status"], "awaiting_submission")
        self.assertEqual(self.step(sid).status_code, 422)
        result = self.client.post(f"/v1/sessions/{sid}/stop", headers=self.headers,
            json={"expected_version": self.status(sid)["version"], "reason": "operator_stop"})
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()["status"], "stopped")
        manual = self.create("scientist")
        predictions = self.conclude_human(manual["session_id"], manual["agent_token"])
        self.client.post(f"/v1/sessions/{manual['session_id']}/stop", headers=self.headers,
            json={"expected_version": self.status(manual["session_id"])["version"], "reason": "operator_stop"})
        denied = self.client.post(f"/v1/sessions/{manual['session_id']}/submission",
            headers={"x-zone-token": manual["agent_token"]},
            json={"expected_version": self.status(manual["session_id"])["version"], "submission": predictions})
        self.assertEqual(denied.status_code, 422)
        match = self.client.post("/v1/matches", headers=self.headers, json={"world_id": self.world["world_id"]}).json()
        human, agent = match["human_session_id"], match["agent_session_id"]
        submission = self.conclude_human(human, match["human_agent_token"])
        self.client.post(f"/v1/sessions/{human}/submission", headers={"x-zone-token": match["human_agent_token"]},
            json={"expected_version": self.status(human)["version"], "submission": submission})
        for participant in (human, agent):
            stopped = self.client.post(f"/v1/sessions/{participant}/stop", headers=self.headers,
                json={"expected_version": self.status(participant)["version"], "reason": "operator_stop"})
            self.assertEqual(stopped.status_code, 200, stopped.text)
        self.assertIsNotNone(self.repo.read_session(human)["events"][3]["message"])
        self.assertEqual(self.repo.read_session(human)["events"][3]["message"]["type"], "scientific_submission")
        self.assertEqual(self.client.post(f"/v1/sessions/{human}/score", headers=self.headers,
            json={"expected_version": self.status(human)["version"]}).status_code, 422)
        reveal = self.client.post(f"/v1/sessions/{agent}/reveal", headers=self.headers,
            json={"expected_version": self.status(agent)["version"], "confirm": "reveal"})
        self.assertEqual(reveal.status_code, 200, reveal.text)


if __name__ == "__main__":
    unittest.main()
