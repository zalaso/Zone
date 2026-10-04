"""Client dichiaratamente simulato: risposte prefissate, non un modello LLM."""

import copy
import json

from .agent_contract import ModelRequest, openai_payload
from .provider_base import ModelReply, ProviderError, metadata


def demo_replies():
    experiment = {"initial_position": {"x": 0, "y": 0}, "initial_velocity": {"x": 4, "y": 6},
                  "duration": 1, "observation_interval": 0.25}
    return [
        {"type": "operator_question", "question_id": "q1", "question": "Preferisci iniziare con un lancio breve?",
         "purpose": "Concordare il primo passo operativo."},
        {"type": "experiment_request", "request_id": "probe-1", "purpose": "Misurare il moto a intervalli regolari.", "experiment": experiment},
        {"type": "hypothesis", "hypothesis_id": "h1", "statement": "Ipotesi del copione simulato: accelerazione verticale circa -8 m/s² e moto orizzontale uniforme.",
         "uncertainties": ["Pochi campioni non identificano una legge."], "evidence": ["probe-1"]},
        {"type": "experiment_request", "request_id": "check-1", "purpose": "Verificare la previsione numerica del copione.",
         "experiment": {**experiment, "initial_position": {"x": 1, "y": 2}, "initial_velocity": {"x": 3, "y": 4}}},
        {"type": "prediction", "prediction_id": "p1", "hypothesis_id": "h1", "request_id": "check-1",
         "points": [{"t": 0, "x": 1, "y": 2}, {"t": 0.25, "x": 1.75, "y": 2.75}, {"t": 0.5, "x": 2.5, "y": 3},
                    {"t": 0.75, "x": 3.25, "y": 2.75}, {"t": 1, "x": 4, "y": 2}]},
        {"type": "conclusion", "final_hypothesis_id": "h1", "summary": "Copione simulato concluso: il ciclo operativo è dimostrato, non la capacità di ricerca di un LLM.",
         "evidence": ["probe-1", "check-1"], "limits": ["Solo due esperimenti; giudicare l'accuratezza dalle metriche registrate."],
         "alternatives": ["Leggi diverse possono concordare sui pochi punti osservati."]},
    ]


class SimulatedClient:
    provider = "simulated"
    sdk_version = None
    generation_settings = {"source": "fixed_offline_script"}

    def __init__(self, replies=None):
        self.replies = iter(copy.deepcopy(demo_replies() if replies is None else replies))
        self.payloads = []

    def complete(self, payload):
        self.payloads.append(copy.deepcopy(openai_payload(payload) if isinstance(payload, ModelRequest) else payload))
        try:
            reply = next(self.replies)
        except StopIteration:
            raise ProviderError("provider_error") from None
        if isinstance(reply, Exception):
            raise reply
        if isinstance(reply, ModelReply):
            return reply
        raw = reply if isinstance(reply, str) else json.dumps({"message": reply}, ensure_ascii=False)
        return ModelReply(raw, metadata(f"simulated-{len(self.payloads)}", "simulated-script-v1", "completed", None))

    def close(self):
        pass
