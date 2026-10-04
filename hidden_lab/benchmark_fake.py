"""Fixture offline con accesso esplicito alla verità; non è un LLM."""

import json

from .provider_base import ModelReply, ProviderError, metadata
from .simulator import acceleration_at


class BenchmarkFixtureClient:
    provider = "simulated"
    sdk_version = None
    generation_settings = {"source": "private_oracle_fixture", "real_model": False}

    def __init__(self, world, scenario="correct"):
        if scenario not in ("correct", "wrong", "insufficient", "malformed", "budget", "provider_error"):
            raise ValueError("Scenario simulato non valido.")
        self.world = world
        self.scenario = scenario
        self.calls = 0
        self.payloads = []
        self.malformed_sent = False

    def complete(self, request):
        self.calls += 1
        self.payloads.append(request)
        if self.scenario == "provider_error":
            raise ProviderError("server_error")
        if self.scenario == "malformed" and not self.malformed_sent:
            self.malformed_sent = True
            return ModelReply("{invalid", metadata(f"fixture-{self.calls}", "benchmark-fixture-v1", "completed", None))
        events = [event["message"] for event in request.history]
        kinds = [message["type"] for message in events]
        phase = request.context["phase"]
        if phase == "submission":
            probes = next(message["probes"] for message in events if message["type"] == "probe_challenge")
            predictions = []
            for probe in probes:
                ax, ay = acceleration_at(self.world, tuple(probe[key] for key in ("x", "y", "vx", "vy")))
                # Approssimazione del fixture: i valori esatti restano nel file privato.
                ax, ay = round(ax, 2), round(ay, 2)
                if self.scenario == "wrong":
                    ax, ay = ax + 3, ay - 2
                if self.scenario == "insufficient":
                    ax = ay = 0
                predictions.append({"probe_id": probe["probe_id"], "ax": ax, "ay": ay})
            conclusion = next(message for message in events if message["type"] == "conclusion")
            message = {"type": "benchmark_submission", "final_hypothesis_id": conclusion["final_hypothesis_id"],
                       "law_description": "Previsione numerica di un fixture offline, non scoperta autonoma.",
                       "predictions": predictions, "limits": ["Fixture con accesso privato alla verità."],
                       "alternatives": ["Non valutate dal fixture."]}
        elif phase == "post_observation":
            observations = [item for item in events if item["type"] == "observation"]
            latest = observations[-1]
            message = {"type": "hypothesis", "hypothesis_id": f"h{len(observations)}",
                       "statement": "Misura registrata; il fixture non apprende una legge.",
                       "uncertainties": ["Ragionamento simulato."],
                       "evidence": [latest["request_id"]] if latest["status"] == "ok" else []}
        elif self.scenario == "insufficient":
            message = {"type": "conclusion", "final_hypothesis_id": None,
                       "summary": "Informazioni insufficienti per identificare la legge.", "evidence": [],
                       "limits": ["Non è stato identificato un modello affidabile."],
                       "alternatives": ["Dinamiche diverse restano compatibili."]}
        elif self.scenario == "budget":
            message = {"type": "operator_question", "question_id": f"q{self.calls}",
                       "question": "Hai indicazioni teoriche?", "purpose": "Verificare la policy neutrale."}
        elif request.context["condition"] == "active" and request.context["remaining_experiments"] > 0:
            index = sum(kind == "experiment_request" for kind in kinds) + 1
            message = {"type": "experiment_request", "request_id": f"a{index}", "purpose": "Misurare un lancio breve.",
                       "experiment": {"initial_position": {"x": index, "y": index + 2},
                                      "initial_velocity": {"x": index + 3, "y": index + 4},
                                      "duration": 1, "observation_interval": 0.25}}
        elif "hypothesis" not in kinds:
            evidence = [item["request_id"] for item in events if item["type"] == "observation" and item["status"] == "ok"]
            message = {"type": "hypothesis", "hypothesis_id": "h1", "statement": "Ipotesi testuale del fixture.",
                       "uncertainties": ["Il fixture non è un agente reale."], "evidence": evidence}
        else:
            evidence = [item["request_id"] for item in events if item["type"] == "observation" and item["status"] == "ok"]
            last_hypothesis = next((item["hypothesis_id"] for item in reversed(events) if item["type"] == "hypothesis"), "h1")
            message = {"type": "conclusion", "final_hypothesis_id": last_hypothesis, "summary": "Scoperta chiusa dal fixture.",
                       "evidence": evidence, "limits": ["Fixture, nessuna capacità di apprendimento dimostrata."],
                       "alternatives": ["Altre leggi possono produrre osservazioni simili."]}
        return ModelReply(json.dumps({"message": message}, ensure_ascii=False),
                          metadata(f"fixture-{self.calls}", "benchmark-fixture-v1", "completed", None))

    def close(self):
        pass
