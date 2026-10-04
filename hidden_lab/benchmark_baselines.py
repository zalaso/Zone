"""Baseline offline: solo storia pubblica, nessuna legge privata o API LLM."""

from hashlib import sha256
import json
import math
import random

from .provider_base import ModelReply, metadata

BASELINES = ("random_policy", "affine_estimator")


def baseline_seed(suite_hash, world_id, repetition, trial_seed):
    """Seed riproducibile da metadati pubblici; non legge la configurazione del mondo."""
    value = f"{suite_hash}:{world_id}:{repetition}:{trial_seed}:baseline-v1"
    return int.from_bytes(sha256(value.encode("utf-8")).digest()[:8], "big")


def _observations(history):
    experiments = {message["request_id"]: message["experiment"] for event in history
                   if (message := event["message"])["type"] in ("execution_started", "passive_experiment")}
    return [(experiments[message["request_id"]], message["points"])
            for event in history if (message := event["message"])["type"] == "observation"
            and message["status"] == "ok" and message["request_id"] in experiments]


def _samples(history):
    """Stima accelerazione e velocità con differenze centrate delle sole posizioni pubbliche."""
    samples = []
    for _, points in _observations(history):
        for before, point, after in zip(points, points[1:], points[2:]):
            dt = (after["t"] - before["t"]) / 2
            if dt <= 0:
                continue
            vx = (after["x"] - before["x"]) / (2 * dt)
            vy = (after["y"] - before["y"]) / (2 * dt)
            ax = (after["x"] - 2 * point["x"] + before["x"]) / dt**2
            ay = (after["y"] - 2 * point["y"] + before["y"]) / dt**2
            values = (point["y"], vx, vy, ax, ay)
            if all(math.isfinite(value) for value in values):
                samples.append(((1.0, point["y"], vx, vy), (ax, ay)))
    return samples


def _solve(matrix, rhs):
    """Gauss con pivot parziale per un sistema 4×4 regolarizzato."""
    rows = [list(row) + [value] for row, value in zip(matrix, rhs)]
    for col in range(4):
        pivot = max(range(col, 4), key=lambda row: abs(rows[row][col]))
        rows[col], rows[pivot] = rows[pivot], rows[col]
        divisor = rows[col][col]
        if abs(divisor) < 1e-12:
            return (0.0, 0.0, 0.0, 0.0)
        for key in range(col, 5):
            rows[col][key] /= divisor
        for row in range(4):
            if row != col:
                factor = rows[row][col]
                for key in range(col, 5):
                    rows[row][key] -= factor * rows[col][key]
    return tuple(row[4] for row in rows)


def fit_affine_acceleration(history):
    """Fit ridge di ax,ay = c0+c1*y+c2*vx+c3*vy; non rappresenta quadratic_drag."""
    samples = _samples(history)
    if not samples:
        return (0.0,) * 4, (0.0,) * 4
    matrix = [[sum(features[i] * features[j] for features, _ in samples)
               for j in range(4)] for i in range(4)]
    for index in range(4):
        matrix[index][index] += 1e-8 if index == 0 else 1e-4
    coefficients = []
    for axis in (0, 1):
        rhs = [sum(features[i] * acceleration[axis] for features, acceleration in samples)
               for i in range(4)]
        coefficients.append(_solve(matrix, rhs))
    return tuple(coefficients)


def predict_affine(history, probes):
    coefficients = fit_affine_acceleration(history)
    predictions = []
    for probe in probes:
        features = (1.0, probe["y"], probe["vx"], probe["vy"])
        values = [sum(a * b for a, b in zip(coeff, features)) for coeff in coefficients]
        values = [max(-1e6, min(1e6, value)) if math.isfinite(value) else 0.0 for value in values]
        predictions.append({"probe_id": probe["probe_id"], "ax": values[0], "ay": values[1]})
    return predictions


class BaselineClient:
    provider = "baseline"
    sdk_version = None
    generation_settings = {"source": "public_history_only", "real_model": False}

    def __init__(self, kind, seed):
        if kind not in BASELINES:
            raise ValueError("Baseline non valida.")
        self.kind = kind
        self.rng = random.Random(seed)
        self.seed = seed
        self.generation_settings = {"source": "public_history_only", "real_model": False,
                                    "baseline": kind, "seed": seed,
                                    "fit": "ridge_affine_y_vx_vy_finite_difference_v1"}
        self.calls = 0
        self.payloads = []

    def complete(self, request):
        self.calls += 1
        self.payloads.append(request)
        history = request.history
        messages = [event["message"] for event in history]
        phase = request.context["phase"]
        observations = [item for item in messages if item["type"] == "observation"]
        if phase == "submission":
            probes = next(item["probes"] for item in messages if item["type"] == "probe_challenge")
            conclusion = next(item for item in messages if item["type"] == "conclusion")
            message = {"type": "benchmark_submission", "final_hypothesis_id": conclusion["final_hypothesis_id"],
                       "law_description": "Fit affine dell'accelerazione da differenze finite delle posizioni pubbliche.",
                       "predictions": predict_affine(history, probes),
                       "limits": ["Non rappresenta resistenza quadratica o termini non lineari; differenze finite sensibili al rumore."],
                       "alternatives": ["Altre dinamiche possono coincidere sui campioni osservati."]}
        elif phase == "post_observation" or ("hypothesis" in request.allowed_types and
                                           not any(item["type"] == "hypothesis" for item in messages)):
            latest = observations[-1] if observations else None
            message = {"type": "hypothesis", "hypothesis_id": f"h{len(observations) or 1}",
                       "statement": "Stimatore affine da differenze finite; non identifica la famiglia vera.",
                       "uncertainties": ["Velocità non osservate direttamente; modello limitato."],
                       "evidence": [latest["request_id"]] if latest and latest["status"] == "ok" else []}
        elif self.kind == "random_policy" and "experiment_request" in request.allowed_types:
            index = sum(item["type"] == "experiment_request" for item in messages) + 1
            experiment = {"initial_position": {axis: round(self.rng.uniform(-8, 8), 6) for axis in ("x", "y")},
                          "initial_velocity": {axis: round(self.rng.uniform(-8, 8), 6) for axis in ("x", "y")},
                          "duration": 0.75, "observation_interval": 0.25}
            message = {"type": "experiment_request", "request_id": f"r{index}",
                       "purpose": "Policy casuale riproducibile, senza adattamento ai dati.", "experiment": experiment}
        else:
            latest_hypothesis = next((item["hypothesis_id"] for item in reversed(messages)
                                      if item["type"] == "hypothesis"), None)
            message = {"type": "conclusion", "final_hypothesis_id": latest_hypothesis,
                       "summary": "Baseline numerica conclusa; fit affine non è identificazione generale.",
                       "evidence": [item["request_id"] for item in observations if item["status"] == "ok"],
                       "limits": ["Famiglia quadratica fuori dalla classe del modello."],
                       "alternatives": ["Dinamiche non lineari o diverse possono spiegare le misure."]}
        return ModelReply(json.dumps({"message": message}, ensure_ascii=False, allow_nan=False),
                          metadata(f"baseline-{self.calls}", self.kind, "completed", None))

    def close(self):
        pass
