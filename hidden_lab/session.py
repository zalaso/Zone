"""Orchestrazione fidata locale; il modello remoto riceve solo messaggi pubblici."""

import copy
import json
import math
import os
from pathlib import Path
import platform

from . import __version__
from .evaluation import compare_positions
from .protocol import ValidationError, apparatus, observation_times, validate_message, validate_observation
from .simulator import TrajectoryError, simulate


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


class Session:
    def __init__(self, directory, config):
        self.directory = Path(directory)
        # Non sovrascrivere esperimenti già registrati.
        self.directory.mkdir(parents=True, exist_ok=False)
        (self.directory / "public").mkdir()
        (self.directory / "private").mkdir()
        self._initialize_state(config)
        write_json(self.directory / "private" / "reproducibility.json", {
            "config": config.to_dict(), "package_version": __version__,
            "python_version": platform.python_version(),
            "integrator": "RK4; ceil(observation_interval/integration_step) passi per intervallo",
            "noise": "random.Random(seed + experiment_index), gauss indipendente per x e y; index da 1",
        })
        self._emit("apparatus", apparatus(config.experiment_budget))

    def _initialize_state(self, config):
        self.config = config
        self.events = []
        self.requests = {}
        self.hypotheses = {}
        self.predictions = {}
        self.observations = {}
        self.executed_count = 0
        self.pending = None
        self.questions = {}
        self.pending_question = None
        self.conclusion = None
        self.closed = False

    def _append(self, path, value):
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(value, ensure_ascii=False, allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    def _emit(self, actor, message):
        event = {"seq": len(self.events) + 1, "actor": actor, "message": copy.deepcopy(message)}
        self._append(self.directory / "public" / "events.jsonl", event)
        self.events.append(event)
        return copy.deepcopy(event)

    def record_error(self, message="Messaggio non valido."):
        return self._emit("apparatus", {"type": "protocol_error", "message": message})

    def record_private(self, filename, value):
        if filename not in ("model_calls.jsonl", "agent_settings.jsonl"):
            raise ValueError("Registro privato non previsto.")
        self._append(self.directory / "private" / filename, value)

    def stop(self, reason):
        if reason not in ("operator_stop", "call_budget", "turn_limit", "invalid_response_limit",
                          "provider_error", "input_limit"):
            raise ValueError("Motivo di arresto non valido.")
        if not self.closed:
            self._emit("apparatus", {"type": "investigation_stopped", "reason": reason})
            self.closed = True

    def submit(self, raw_message, actor="agent"):
        message = validate_message(raw_message)
        kind = message["type"]
        if self.closed:
            raise ValidationError("Indagine già chiusa.")
        required_actor = "operator" if kind in ("operator_decision", "operator_answer", "execution_mode") else "agent"
        if actor != required_actor:
            raise ValidationError("Il ruolo non può inviare questo tipo di messaggio.")

        if self.pending_question is not None and kind != "operator_answer":
            raise ValidationError("Occorre prima rispondere alla domanda in attesa.")
        if kind == "operator_question":
            if message["question_id"] in self.questions:
                raise ValidationError("Identificatore di domanda già usato.")
            event = self._emit(actor, message)
            self.questions[message["question_id"]] = message
            self.pending_question = message["question_id"]
        elif kind == "operator_answer":
            if message["question_id"] != self.pending_question:
                raise ValidationError("Nessuna domanda corrispondente in attesa.")
            event = self._emit(actor, message)
            self.pending_question = None
        elif kind == "execution_mode":
            request = self.requests.get(message["request_id"])
            if request is None or request["status"] != "approved" or "mode" in request:
                raise ValidationError("La modalità richiede un esperimento approvato, senza modalità già scelta.")
            if message["request_id"] in self.predictions:
                raise ValidationError("La modalità va scelta prima della previsione.")
            event = self._emit(actor, message)
            request["mode"] = message["mode"]
        elif kind == "conclusion":
            if message["final_hypothesis_id"] is not None and message["final_hypothesis_id"] not in self.hypotheses:
                raise ValidationError("L'ipotesi finale deve essere già registrata oppure null.")
            if any(item not in self.observations or self.observations[item]["status"] != "ok"
                   for item in message["evidence"]):
                raise ValidationError("Le evidenze finali devono riferirsi a misure già disponibili.")
            event = self._emit(actor, message)
            self.conclusion = message
            self.closed = True
            if self.pending is not None:
                self.requests[self.pending]["status"] = "cancelled"
                self.pending = None
        elif kind == "experiment_request":
            request_id = message["request_id"]
            if request_id in self.requests or self.pending is not None:
                raise ValidationError("ID già usato oppure un esperimento è ancora in attesa.")
            if self.executed_count >= self.config.experiment_budget:
                raise ValidationError("Budget esaurito.")
            event = self._emit(actor, message)
            self.requests[request_id] = {"status": "pending", "experiment": message["experiment"]}
            self.pending = request_id
        elif kind == "operator_decision":
            request_id = message["request_id"]
            request = self.requests.get(request_id)
            if request is None or request["status"] != "pending":
                raise ValidationError("Richiesta inesistente o decisione già definitiva.")
            event = self._emit(actor, message)
            if message["action"] == "reject":
                request["status"] = "rejected"
                self.pending = None
            else:
                request["status"] = "approved"
                if message["action"] == "modify":
                    request["experiment"] = message["modified_experiment"]
        elif kind == "hypothesis":
            hypothesis_id = message["hypothesis_id"]
            if hypothesis_id in self.hypotheses:
                raise ValidationError("Identificatore di ipotesi già usato.")
            if any(item not in self.observations or self.observations[item]["status"] != "ok"
                   for item in message["evidence"]):
                raise ValidationError("Le evidenze devono riferirsi a esperimenti conclusi con misure.")
            event = self._emit(actor, message)
            self.hypotheses[hypothesis_id] = message
        elif kind == "prediction":
            request_id = message["request_id"]
            request = self.requests.get(request_id)
            if request is None or request["status"] != "approved":
                raise ValidationError("La previsione richiede un esperimento approvato e non ancora eseguito.")
            if request.get("mode") == "exploration":
                raise ValidationError("La modalità esplorativa non accetta previsioni.")
            if message["hypothesis_id"] not in self.hypotheses:
                raise ValidationError("Ipotesi inesistente.")
            if request_id in self.predictions or any(
                    item["prediction_id"] == message["prediction_id"] for item in self.predictions.values()):
                raise ValidationError("Previsione già registrata: non è sostituibile.")
            times = observation_times(request["experiment"])
            if len(times) != len(message["points"]) or any(
                    not math.isclose(t, point["t"], rel_tol=0, abs_tol=1e-9)
                    for t, point in zip(times, message["points"])):
                raise ValidationError("I tempi devono coincidere, in ordine, con tutte le osservazioni approvate.")
            # Canonicalizza solo i tempi; nessun accesso al simulatore per creare previsioni.
            for t, point in zip(times, message["points"]):
                point["t"] = t
            event = self._emit(actor, message)
            self.predictions[request_id] = message
        return event

    def _begin_execution(self, request_id):
        if self.closed or self.pending_question is not None:
            raise ValidationError("Indagine chiusa oppure risposta dell'operatore ancora in attesa.")
        request = self.requests.get(request_id)
        if request is None or request["status"] != "approved":
            raise ValidationError("Esecuzione ammessa solo una volta dopo l'approvazione.")
        if self.executed_count >= self.config.experiment_budget:
            raise ValidationError("Budget esaurito.")
        if request.get("mode") == "verification" and request_id not in self.predictions:
            raise ValidationError("La verifica richiede prima una previsione registrata.")
        experiment_index = self.executed_count + 1
        self._emit("operator", {"type": "execution_started", "request_id": request_id,
                                "experiment": request["experiment"], "executed_count": experiment_index})
        self.executed_count = experiment_index
        request["status"] = "executed"
        self.pending = None
        return request, experiment_index

    def run(self, request_id):
        request, experiment_index = self._begin_execution(request_id)
        try:
            points = simulate(self.config, request["experiment"], experiment_index)
            status, error = "ok", None
        except TrajectoryError:
            points, status = [], "error"
            error = {"code": "TRAJECTORY_INVALID", "message": "Traiettoria fuori dai limiti dell'apparato o numericamente non valida."}
        observation = {"type": "observation", "request_id": request_id,
                       "experiment_index": experiment_index, "status": status, "points": points,
                       "error": error, "executed_count": self.executed_count,
                       "remaining_budget": self.config.experiment_budget - self.executed_count}
        validate_observation(observation, request["experiment"], self.config.experiment_budget)
        self._emit("apparatus", observation)
        self.observations[request_id] = observation
        prediction = self.predictions.get(request_id)
        metrics = compare_positions(prediction["points"], points) if prediction and status == "ok" else None
        if prediction:
            self._emit("apparatus", {"type": "verification", "request_id": request_id,
                                     "prediction_id": prediction["prediction_id"],
                                     "status": "ok" if metrics is not None else "unavailable", "metrics": metrics})
        self._append(self.directory / "private" / "evaluations.jsonl", {
            "public_seq": len(self.events), "request_id": request_id,
            "experiment_index": experiment_index, "world": self.config.to_dict()["world"],
            "prediction_id": prediction["prediction_id"] if prediction else None,
            "hypothesis": self.hypotheses[prediction["hypothesis_id"]] if prediction else None,
            "predictive_metrics": metrics, "law_identification": "not_assessed",
            "note": "La legge vera è disponibile solo qui; nessun test di equivalenza implementato.",
        })
        return copy.deepcopy(observation)
