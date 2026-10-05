"""Un trial, un mondo, un modello: orchestrazione fidata e audit offline-first."""

import copy
from hashlib import sha256
import json
import os
from pathlib import Path
import random
import time
from uuid import uuid4

from . import __version__
from .benchmark_contract import build_benchmark_request, validate_benchmark_message
from .identification import (IDENTIFICATION_VERSION, identification_material,
                             score_scientific_submission)
from .benchmark_suite import digest, save_new, validate_suite
from .protocol import ValidationError, apparatus, decode, require_keys, validate_observation
from .provider_base import ADAPTER_VERSION, ProviderError
from .simulator import TrajectoryError, parse_config, simulate

CONDITIONS = ("prior_only", "passive_fixed", "passive_sequential", "active")
NEUTRAL_ANSWER = "L'operatore non fornisce informazioni teoriche; usa l'apparato pubblico e le misure."


def source_fingerprint():
    """Impronta dei moduli Python installati, indipendente dal percorso assoluto."""
    root = Path(__file__).resolve().parent
    digest = sha256()
    for path in sorted(root.glob("*.py")):
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


class BenchmarkTrial:
    def __init__(self, directory, suite, world_id, condition, client, settings, *, repetition=0,
                 trial_seed=0, contaminated=False, integrity=None):
        validate_suite(suite)
        if condition not in CONDITIONS:
            raise ValidationError("Condizione benchmark non valida.")
        if condition == "passive_sequential" and suite["suite_version"] == "0.1":
            raise ValidationError("passive_sequential richiede una suite v0.2 o successiva.")
        if type(repetition) is not int or repetition < 0 or type(trial_seed) is not int or not 0 <= trial_seed < 2**64:
            raise ValidationError("Ripetizione o seed trial non valido.")
        matches = [item for item in suite["worlds"] if item["id"] == world_id]
        if len(matches) != 1:
            raise ValidationError("ID mondo assente dalla suite.")
        self.directory = Path(directory)
        self.code_hash = source_fingerprint()
        self.directory.mkdir(parents=True, exist_ok=False)
        (self.directory / "public").mkdir()
        (self.directory / "private").mkdir()
        self.suite = suite
        self.world = matches[0]
        self.config = parse_config(self.world["config"])
        self.condition = condition
        self.client = client
        self.settings = settings
        self.repetition = repetition
        self.trial_seed = trial_seed
        self.contaminated = False
        self.integrity = copy.deepcopy(integrity)
        self.events = []
        self.observations = {}
        self.hypotheses = {}
        self.request_ids = set()
        self.question_ids = set()
        self.conclusion = None
        self.submission = None
        self.identification = None
        self.calls = self.turns = self.invalid_count = self.correction_count = 0
        self.requested_count = self.executed_count = self.failed_count = 0
        self.stop_reason = None
        self.usage_records = []
        self.started = time.monotonic()
        self.probes = copy.deepcopy(self.world["probes"])
        # La ripetizione determina l'ordine; un trial_seed diverso non può
        # cambiare i probe per la stessa coppia mondo/ripetizione.
        random.Random(f"{suite['sha256']}:{world_id}:{repetition}").shuffle(self.probes)
        self.probe_hash = digest(self.probes)
        save_new(self.directory / "private" / "world.json", {"suite_hash": suite["sha256"],
                 "world_id": world_id, "config": self.world["config"],
                 "passive_schedule": self.world["passive_schedule"], "probes": self.world["probes"]})
        save_new(self.directory / "private" / "agent_settings.json", {
            "provider": client.provider, "requested_model": settings.model,
            "sdk_version": getattr(client, "sdk_version", None),
            "transport_version": getattr(client, "http_version", None),
            "adapter_version": ADAPTER_VERSION, "settings": settings.to_dict(),
            "generation_settings": client.generation_settings})
        self._emit("apparatus", apparatus(self.config.experiment_budget))
        if contaminated:
            self.mark_contaminated()

    def _append(self, path, value):
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(value, ensure_ascii=False, allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    def _emit(self, actor, message):
        event = {"seq": len(self.events) + 1, "actor": actor, "message": copy.deepcopy(message)}
        self._append(self.directory / "public" / "events.jsonl", event)
        self.events.append(event)
        return event

    def mark_contaminated(self):
        if not self.contaminated:
            self.contaminated = True
            self._emit("benchmark", {"type": "human_intervention", "contaminated": True})

    def _valid_semantics(self, message):
        kind = message["type"]
        if kind == "experiment_request":
            if self.condition != "active" or self.executed_count >= self.config.experiment_budget:
                raise ValidationError("Richiesta non disponibile nella condizione corrente.")
            if message["request_id"] in self.request_ids:
                raise ValidationError("ID esperimento duplicato.")
            count = round(message["experiment"]["duration"] / message["experiment"]["observation_interval"]) + 1
            if count > self.settings.max_points:
                raise ValidationError("Troppi punti di osservazione.")
        elif kind == "hypothesis":
            if message["hypothesis_id"] in self.hypotheses:
                raise ValidationError("ID ipotesi duplicato.")
            self._check_evidence(message["evidence"])
        elif kind == "conclusion":
            if message["final_hypothesis_id"] is not None and message["final_hypothesis_id"] not in self.hypotheses:
                raise ValidationError("Ipotesi finale inesistente.")
            self._check_evidence(message["evidence"])
        elif kind == "operator_question" and message["question_id"] in self.question_ids:
            raise ValidationError("ID domanda duplicato.")

    def _check_evidence(self, ids):
        if any(key not in self.observations or self.observations[key]["status"] != "ok" for key in ids):
            raise ValidationError("Evidenza senza misura riuscita.")

    def _next(self, phase):
        for attempt in range(self.settings.max_corrections + 1):
            if self.calls >= self.settings.max_calls or self.turns >= self.settings.max_turns:
                self.stop_reason = "call_budget" if self.calls >= self.settings.max_calls else "turn_limit"
                return None
            if attempt:
                self.correction_count += 1
            request = build_benchmark_request(self.events, self.settings, phase, self.condition,
                        self.settings.max_calls - self.calls, self.settings.max_turns - self.turns,
                        self.config.experiment_budget - self.executed_count, self.suite["suite_version"])
            if request.size_bytes() > self.settings.max_input_bytes:
                self.stop_reason = "input_limit"
                return None
            self.calls += 1
            audit = {"call_index": self.calls, "turn_index": self.turns + 1,
                     "correction_attempt": attempt, "phase": phase, "public_seq": len(self.events),
                     "provider": self.client.provider, "requested_model": self.settings.model,
                     "adapter_version": ADAPTER_VERSION, **request.contract_fingerprints()}
            self._append(self.directory / "private" / "model_calls.jsonl", {**audit, "outcome": "started", "usage": None})
            start = time.monotonic()
            try:
                reply = self.client.complete(request)
            except ProviderError as exc:
                self._append(self.directory / "private" / "model_calls.jsonl", {**audit,
                             "outcome": "provider_error", "error_code": exc.code,
                             "usage": None, "duration_seconds": round(time.monotonic() - start, 6)})
                self.stop_reason = "provider_error"
                return None
            safe_meta = {key: reply.metadata.get(key) for key in
                         ("response_id", "returned_model", "status", "usage", "provider_details")}
            if safe_meta["usage"] is not None or safe_meta["provider_details"] is not None:
                self.usage_records.append({"call_index": self.calls, "usage": safe_meta["usage"],
                                           "provider_details": safe_meta["provider_details"]})
            try:
                if reply.issue:
                    raise ValidationError("Risposta del provider incompleta.")
                envelope = decode(reply.text)
                require_keys(envelope, ("message",))
                message = validate_benchmark_message(envelope["message"], request.allowed_types,
                    tuple(item["probe_id"] for item in self.probes) if phase == "submission" else (),
                    self.conclusion["final_hypothesis_id"] if self.conclusion else None,
                    self.suite["suite_version"])
                self._valid_semantics(message)
            except ValidationError as exc:
                self.invalid_count += 1
                self._emit("apparatus", {"type": "protocol_error", "message": str(exc)})
                self._append(self.directory / "private" / "model_calls.jsonl", {**audit, **safe_meta,
                             "outcome": "invalid_response", "duration_seconds": round(time.monotonic() - start, 6)})
                continue
            self._append(self.directory / "private" / "model_calls.jsonl", {**audit, **safe_meta,
                         "outcome": "accepted", "duration_seconds": round(time.monotonic() - start, 6)})
            self.turns += 1
            return message
        self.stop_reason = "invalid_response_limit"
        return None

    def _execute(self, request_id, experiment):
        index = self.executed_count + 1
        self._emit("benchmark", {"type": "execution_started", "request_id": request_id,
                                  "experiment": experiment, "executed_count": index})
        self.executed_count = index
        try:
            points = simulate(self.config, experiment, index)
            status, error = "ok", None
        except TrajectoryError:
            points, status = [], "error"
            error = {"code": "TRAJECTORY_INVALID", "message": "Traiettoria fuori dai limiti dell'apparato o numericamente non valida."}
            self.failed_count += 1
        observation = {"type": "observation", "request_id": request_id,
                       "experiment_index": index, "status": status, "points": points,
                       "error": error, "executed_count": index,
                       "remaining_budget": self.config.experiment_budget - index}
        validate_observation(observation, experiment, self.config.experiment_budget)
        self._emit("apparatus", observation)
        self.observations[request_id] = observation

    def _post_observation(self):
        message = self._next("post_observation")
        if message is None:
            return
        self._emit("agent", message)
        self.hypotheses[message["hypothesis_id"]] = message

    def _passive_schedule(self, sequential=False):
        for index, experiment in enumerate(self.world["passive_schedule"], 1):
            request_id = f"s{index}"
            self._emit("benchmark", {"type": "passive_experiment", "request_id": request_id,
                                      "experiment": experiment})
            self._execute(request_id, experiment)
            if sequential:
                self._post_observation()
                if self.stop_reason is not None:
                    break

    def _discovery(self):
        if self.condition == "passive_fixed":
            self._passive_schedule()
        elif self.condition == "passive_sequential":
            self._passive_schedule(sequential=True)
        while self.conclusion is None and self.stop_reason is None:
            message = self._next("discovery")
            if message is None:
                break
            kind = message["type"]
            self._emit("agent", message)
            if kind == "experiment_request":
                request_id = message["request_id"]
                self.request_ids.add(request_id)
                self.requested_count += 1
                self._emit("benchmark", {"type": "operator_decision", "request_id": request_id,
                                          "action": "approve", "reason": "Policy neutrale automatica."})
                self._emit("benchmark", {"type": "execution_mode", "request_id": request_id,
                                          "mode": "exploration"})
                self._execute(request_id, message["experiment"])
                if self.suite["suite_version"] != "0.1":
                    self._post_observation()
            elif kind == "hypothesis":
                self.hypotheses[message["hypothesis_id"]] = message
            elif kind == "operator_question":
                self.question_ids.add(message["question_id"])
                self._emit("benchmark", {"type": "operator_answer", "question_id": message["question_id"],
                                          "answer": NEUTRAL_ANSWER})
            elif kind == "conclusion":
                self.conclusion = message
                self._emit("benchmark", {"type": "discovery_closed",
                                          "final_hypothesis_id": message["final_hypothesis_id"]})

    def _challenge(self):
        self._emit("benchmark", {"type": "probe_challenge", "probes": self.probes})
        message = self._next("submission")
        if message is None:
            return None
        self._emit("agent", message)
        self.submission = message
        # Persistenza della previsione prima di calcolare o scrivere la verità.
        save_new(self.directory / "public" / "submission.json", message)
        material = identification_material(self.world["config"]["seed"], self.world["id"],
                                           f"{self.suite['sha256']}:{self.repetition}")
        scores, audit = score_scientific_submission(message, self.probes, self.config.world, material)
        save_new(self.directory / "private" / "probe_truth.json", audit["probe_truth"])
        if audit["secret_grid"] is not None:
            save_new(self.directory / "private" / "identification_grid.json", audit["secret_grid"])
        if "law_ast_json" in message or "uncertainty_sigma" in message:
            self.identification = {key: scores[key] for key in
                                   ("functional", "complexity", "dependencies", "calibration")}
        return scores["prediction"]

    def run(self):
        self._discovery()
        metrics = self._challenge() if self.conclusion is not None and self.stop_reason is None else None
        if self.submission is not None:
            status = "insufficient" if self.conclusion["final_hypothesis_id"] is None else "completed"
        elif self.stop_reason == "provider_error":
            status = "provider_error"
        else:
            status = "limit_reached"
        result = {"benchmark_version": self.suite["suite_version"], "code_version": __version__,
                  "code_hash": self.code_hash,
                  "provider_config_hash": digest({"settings": self.settings.to_dict(),
                                                  "generation": self.client.generation_settings,
                                                  "adapter_version": ADAPTER_VERSION}),
                  "trial_id": uuid4().hex, "suite_hash": self.suite["sha256"],
                  "world_config_hash": digest(self.world["config"]),
                  "world_id": self.world["id"], "condition": self.condition, "provider": self.client.provider,
                  "model": self.settings.model, "repetition": self.repetition, "trial_seed": self.trial_seed,
                  "experiment_budget": self.config.experiment_budget, "probe_hash": self.probe_hash,
                  "limits": {"max_calls": self.settings.max_calls, "max_turns": self.settings.max_turns,
                             "max_corrections": self.settings.max_corrections,
                             "max_observation_points": self.settings.max_points,
                             "max_output_tokens": self.settings.max_output_tokens,
                             "max_input_bytes": self.settings.max_input_bytes},
                  "status": status, "stop_reason": self.stop_reason, "contaminated": self.contaminated,
                  "requested_experiments": self.requested_count, "executed_experiments": self.executed_count,
                  "failed_experiments": self.failed_count, "model_calls": self.calls, "valid_turns": self.turns,
                  "observation_count": len(self.observations),
                  "observation_points": sum(len(observation["points"]) for observation in self.observations.values()),
                  "invalid_responses": self.invalid_count, "corrections": self.correction_count,
                  "duration_seconds": round(time.monotonic() - self.started, 6),
                  "usage_records": self.usage_records, "metrics": metrics,
                  "identification": self.identification,
                  "identification_version": IDENTIFICATION_VERSION if self.identification is not None else None,
                  "api_cost_usd": 0.0 if self.client.provider in ("simulated", "baseline", "ollama") else None,
                  "trajectory_position_rmse": None}
        if self.integrity is not None:
            result["integrity"] = {**self.integrity, "oracle_fixture": self.client.provider == "simulated"}
        save_new(self.directory / "result.json", result)
        return result
