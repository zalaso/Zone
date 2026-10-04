"""Riduttore di eventi e regole del laboratorio HTTP; nessun I/O o provider."""

import math

from .evaluation import compare_positions
from .protocol import (ValidationError, identifier, observation_times,
                       validate_message, validate_observation)
from .simulator import TrajectoryError, simulate


class LabState:
    def __init__(self, events, budget, score=None):
        self.events = events
        self.budget = budget
        self.version = len(events)
        self.requests = {}
        self.hypotheses = {}
        self.predictions = {}
        self.observations = {}
        self.questions = set()
        self.pending_request = None
        self.pending_question = None
        self.running = None
        self.executed_count = 0
        self.closed = False
        self.stopped = False
        self.challenge = None
        self.submission = None
        self.revealed = False
        self.score = score
        for index, event in enumerate(events, 1):
            if event["seq"] != index:
                raise ValidationError("Sequenza eventi non valida.")
            self._apply(event["message"])

    def _apply(self, message):
        kind = message["type"]
        if kind == "experiment_request":
            request_id = message["request_id"]
            self.requests[request_id] = {"status": "pending", "experiment": message["experiment"]}
            self.pending_request = request_id
        elif kind == "operator_decision":
            request = self.requests[message["request_id"]]
            if message["action"] == "reject":
                request["status"] = "rejected"
                self.pending_request = None
            else:
                request["status"] = "approved"
                if message["action"] == "modify":
                    request["experiment"] = message["modified_experiment"]
        elif kind == "execution_mode":
            self.requests[message["request_id"]]["mode"] = message["mode"]
        elif kind == "hypothesis":
            self.hypotheses[message["hypothesis_id"]] = message
        elif kind == "prediction":
            self.predictions[message["request_id"]] = message
        elif kind == "operator_question":
            self.questions.add(message["question_id"])
            self.pending_question = message["question_id"]
        elif kind == "operator_answer":
            self.pending_question = None
        elif kind == "execution_started":
            self.executed_count = message["executed_count"]
            self.requests[message["request_id"]]["status"] = "running"
            self.running = message["request_id"]
            self.pending_request = None
        elif kind == "observation":
            self.observations[message["request_id"]] = message
            self.requests[message["request_id"]]["status"] = "executed"
            self.running = None
        elif kind == "conclusion":
            self.closed = True
            self.pending_request = None
        elif kind == "investigation_stopped":
            self.closed = self.stopped = True
            self.pending_request = None
        elif kind == "probe_challenge":
            self.challenge = message
        elif kind == "scientific_submission":
            self.submission = message
        elif kind == "result_recorded":
            self.score = message["scores"]
        elif kind == "reveal_recorded":
            self.revealed = True

    def status(self):
        if self.revealed:
            return "revealed"
        if self.submission is not None:
            return "scored" if self.score is not None else "scoring_pending"
        if self.stopped:
            return "stopped"
        if self.challenge is not None:
            return "awaiting_submission"
        if self.running is not None:
            return "execution_started"
        if self.pending_question is not None:
            return "awaiting_answer"
        if self.pending_request is not None:
            request = self.requests[self.pending_request]
            if request["status"] == "pending":
                return "awaiting_decision"
            if "mode" not in request:
                return "awaiting_mode"
            if request["mode"] == "verification" and self.pending_request not in self.predictions:
                return "awaiting_prediction"
            return "ready_to_run"
        return "discovering"

    def public_status(self):
        return {"version": self.version, "status": self.status(),
                "executed_experiments": self.executed_count,
                "remaining_experiments": self.budget - self.executed_count,
                "pending_request_id": self.pending_request,
                "pending_question_id": self.pending_question,
                "running_request_id": self.running,
                "challenge_available": self.challenge is not None,
                "result_available": self.score is not None, "revealed": self.revealed}

    def accept_message(self, raw, role):
        message = validate_message(raw)
        kind = message["type"]
        expected_role = "operator" if kind in ("operator_decision", "operator_answer", "execution_mode") else "agent"
        if role != expected_role:
            raise ValidationError("Ruolo non autorizzato per questo messaggio.")
        if self.closed or self.running is not None:
            raise ValidationError("Indagine chiusa o esperimento già avviato.")
        if self.pending_question is not None and kind != "operator_answer":
            raise ValidationError("Rispondere prima alla domanda in attesa.")
        if kind == "operator_question":
            if message["question_id"] in self.questions:
                raise ValidationError("ID domanda duplicato.")
        elif kind == "operator_answer":
            if message["question_id"] != self.pending_question:
                raise ValidationError("Nessuna domanda corrispondente.")
        elif kind == "experiment_request":
            if self.pending_request is not None or message["request_id"] in self.requests or self.executed_count >= self.budget:
                raise ValidationError("Richiesta duplicata, già pendente o budget esaurito.")
        elif kind == "operator_decision":
            request = self.requests.get(message["request_id"])
            if request is None or request["status"] != "pending" or self.pending_request != message["request_id"]:
                raise ValidationError("Richiesta non in attesa di decisione.")
        elif kind == "execution_mode":
            request = self.requests.get(message["request_id"])
            if request is None or request["status"] != "approved" or "mode" in request or message["request_id"] in self.predictions:
                raise ValidationError("Modalità non disponibile.")
        elif kind == "hypothesis":
            if message["hypothesis_id"] in self.hypotheses:
                raise ValidationError("ID ipotesi duplicato.")
            self._check_evidence(message["evidence"])
        elif kind == "prediction":
            request = self.requests.get(message["request_id"])
            if request is None or request["status"] != "approved" or request.get("mode") != "verification":
                raise ValidationError("Previsione ammessa solo per verifica approvata.")
            if message["hypothesis_id"] not in self.hypotheses or message["request_id"] in self.predictions or any(
                    item["prediction_id"] == message["prediction_id"] for item in self.predictions.values()):
                raise ValidationError("Ipotesi mancante o previsione duplicata.")
            times = observation_times(request["experiment"])
            if len(times) != len(message["points"]) or any(not math.isclose(t, point["t"], rel_tol=0, abs_tol=1e-9)
                                                         for t, point in zip(times, message["points"])):
                raise ValidationError("Tempi della previsione non coerenti con l'esperimento approvato.")
            for time, point in zip(times, message["points"]):
                point["t"] = time
        elif kind == "conclusion":
            if message["final_hypothesis_id"] is not None and message["final_hypothesis_id"] not in self.hypotheses:
                raise ValidationError("Ipotesi finale inesistente.")
            self._check_evidence(message["evidence"])
        return message

    def _check_evidence(self, ids):
        if any(key not in self.observations or self.observations[key]["status"] != "ok" for key in ids):
            raise ValidationError("Evidenza senza misura riuscita.")

    def start_run(self, request_id):
        identifier(request_id)
        request = self.requests.get(request_id)
        if self.closed or self.running is not None or self.pending_question is not None or request is None or request["status"] != "approved":
            raise ValidationError("Esperimento non eseguibile.")
        if request.get("mode") not in ("exploration", "verification") or self.executed_count >= self.budget:
            raise ValidationError("Modalità mancante o budget esaurito.")
        if request["mode"] == "verification" and request_id not in self.predictions:
            raise ValidationError("Previsione preregistrata mancante.")
        return {"type": "execution_started", "request_id": request_id,
                "experiment": request["experiment"], "executed_count": self.executed_count + 1}


def finish_run(config, started, prediction):
    request_id, experiment, index = started["request_id"], started["experiment"], started["executed_count"]
    try:
        points = simulate(config, experiment, index)
        status, error = "ok", None
    except TrajectoryError:
        points, status = [], "error"
        error = {"code": "TRAJECTORY_INVALID", "message": "Traiettoria fuori dai limiti o non valida."}
    observation = {"type": "observation", "request_id": request_id,
                   "experiment_index": index, "status": status, "points": points, "error": error,
                   "executed_count": index, "remaining_budget": config.experiment_budget - index}
    validate_observation(observation, experiment, config.experiment_budget)
    entries = [("apparatus", observation)]
    if prediction is not None:
        metrics = compare_positions(prediction["points"], points) if status == "ok" else None
        entries.append(("apparatus", {"type": "verification", "request_id": request_id,
                    "prediction_id": prediction["prediction_id"],
                    "status": "ok" if metrics is not None else "unavailable", "metrics": metrics}))
    return entries
