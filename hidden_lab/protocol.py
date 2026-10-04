"""Contratto pubblico. Nessuna importazione del simulatore o della legge vera."""

import json
import math
import re

PROTOCOL_VERSION = 2
MAX_MESSAGE_BYTES = 64_000


class ValidationError(ValueError):
    """Errore comunicabile senza ripetere il contenuto ricevuto."""


def require_keys(value, required, optional=()):
    if not isinstance(value, dict):
        raise ValidationError("È richiesto un oggetto JSON.")
    if not set(required) <= value.keys() or value.keys() - set(required) - set(optional):
        raise ValidationError("Campi mancanti o non previsti dal protocollo.")


def number(value, minimum=-1e6, maximum=1e6):
    if type(value) not in (int, float):
        raise ValidationError("È richiesto un numero finito nei limiti.")
    if not minimum <= value <= maximum or not math.isfinite(value):
        raise ValidationError("È richiesto un numero finito nei limiti.")
    return float(value)


def text(value, maximum=2000):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError("Testo vuoto o troppo lungo.")
    return value


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,47}", value):
        raise ValidationError("Identificatore non valido.")
    return value


def text_list(value, minimum=0):
    if not isinstance(value, list) or not minimum <= len(value) <= 100:
        raise ValidationError("Lista non valida: massimo 100 elementi.")
    return [text(item) for item in value]


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValidationError("Chiave JSON duplicata.")
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValidationError("JSON non ammette NaN o Infinity.")


def decode(raw):
    if not isinstance(raw, str) or len(raw.encode("utf-8")) > MAX_MESSAGE_BYTES:
        raise ValidationError("Messaggio troppo grande.")
    try:
        return json.loads(raw, object_pairs_hook=_unique_object, parse_constant=_invalid_constant)
    except (ValueError, RecursionError) as exc:
        raise ValidationError("JSON non valido.") from exc


def validate_experiment(value):
    require_keys(value, ("initial_position", "initial_velocity", "duration", "observation_interval"))
    result = {}
    for key in ("initial_position", "initial_velocity"):
        require_keys(value[key], ("x", "y"))
        result[key] = {axis: number(value[key][axis], -20, 20) for axis in ("x", "y")}
    duration = number(value["duration"], 0.1, 5)
    interval = number(value["observation_interval"], 0.05, 1)
    count = round(duration / interval)
    if count < 1 or not math.isclose(count * interval, duration, rel_tol=0, abs_tol=1e-9):
        raise ValidationError("La durata deve essere un multiplo dell'intervallo di osservazione.")
    result.update(duration=duration, observation_interval=interval)
    return result


def observation_times(experiment):
    count = round(experiment["duration"] / experiment["observation_interval"])
    return [index * experiment["duration"] / count for index in range(count + 1)]


def validate_message(value):
    """Valida la forma; Session verifica anche ordine, riferimenti e budget."""
    if not isinstance(value, dict) or not isinstance(value.get("type"), str):
        raise ValidationError("Tipo di messaggio mancante.")
    kind = value["type"]
    if kind == "operator_question":
        require_keys(value, ("type", "question_id", "question", "purpose"))
        return dict(type=kind, question_id=identifier(value["question_id"]),
                    question=text(value["question"]), purpose=text(value["purpose"]))
    if kind == "operator_answer":
        require_keys(value, ("type", "question_id", "answer"))
        return dict(type=kind, question_id=identifier(value["question_id"]), answer=text(value["answer"]))
    if kind == "execution_mode":
        require_keys(value, ("type", "request_id", "mode"))
        if value["mode"] not in ("exploration", "verification"):
            raise ValidationError("Modalità di esecuzione non valida.")
        return dict(type=kind, request_id=identifier(value["request_id"]), mode=value["mode"])
    if kind == "conclusion":
        require_keys(value, ("type", "final_hypothesis_id", "summary", "evidence", "limits", "alternatives"))
        evidence = text_list(value["evidence"])
        return dict(type=kind, final_hypothesis_id=(identifier(value["final_hypothesis_id"])
                    if value["final_hypothesis_id"] is not None else None), summary=text(value["summary"]),
                    evidence=[identifier(item) for item in evidence], limits=text_list(value["limits"], 1),
                    alternatives=text_list(value["alternatives"]))
    if kind == "experiment_request":
        require_keys(value, ("type", "request_id", "purpose", "experiment"))
        return dict(type=kind, request_id=identifier(value["request_id"]),
                    purpose=text(value["purpose"]), experiment=validate_experiment(value["experiment"]))
    if kind == "operator_decision":
        require_keys(value, ("type", "request_id", "action", "reason"), ("modified_experiment",))
        action = value["action"]
        if action not in ("approve", "modify", "reject"):
            raise ValidationError("Decisione non valida.")
        if (action == "modify") != ("modified_experiment" in value):
            raise ValidationError("Solo modify richiede modified_experiment completo.")
        result = dict(type=kind, request_id=identifier(value["request_id"]),
                      action=action, reason=text(value["reason"]))
        if action == "modify":
            result["modified_experiment"] = validate_experiment(value["modified_experiment"])
        return result
    if kind == "hypothesis":
        require_keys(value, ("type", "hypothesis_id", "statement", "uncertainties", "evidence"))
        for key in ("uncertainties", "evidence"):
            if not isinstance(value[key], list) or len(value[key]) > 100:
                raise ValidationError("È richiesta una lista di massimo 100 elementi.")
        return dict(type=kind, hypothesis_id=identifier(value["hypothesis_id"]),
                    statement=text(value["statement"]),
                    uncertainties=[text(item) for item in value["uncertainties"]],
                    evidence=[identifier(item) for item in value["evidence"]])
    if kind == "prediction":
        require_keys(value, ("type", "prediction_id", "hypothesis_id", "request_id", "points"))
        if not isinstance(value["points"], list) or not 2 <= len(value["points"]) <= 101:
            raise ValidationError("La previsione richiede da 2 a 101 punti.")
        points = []
        for point in value["points"]:
            require_keys(point, ("t", "x", "y"))
            points.append(dict(t=number(point["t"], 0, 5),
                               x=number(point["x"]), y=number(point["y"])))
        return dict(type=kind, prediction_id=identifier(value["prediction_id"]),
                    hypothesis_id=identifier(value["hypothesis_id"]),
                    request_id=identifier(value["request_id"]), points=points)
    raise ValidationError("Tipo di messaggio sconosciuto.")


def apparatus(budget):
    return {
        "type": "apparatus", "protocol_version": PROTOCOL_VERSION,
        "coordinates": "x verso destra, y verso l'alto; origine fissa; nessun pavimento",
        "units": {"time": "s", "position": "m", "velocity": "m/s"},
        "controls": ["initial_position", "initial_velocity", "duration", "observation_interval"],
        "limits": {"initial_position_per_axis": [-20, 20], "initial_velocity_per_axis": [-20, 20],
                   "duration": [0.1, 5], "observation_interval": [0.05, 1],
                   "position_per_axis": [-100, 100], "speed": [0, 200]},
        "sampling": "t=0 e tutti i multipli dell'intervallo fino alla durata inclusa; durata multipla dell'intervallo",
        "experiment_budget": budget,
        "budget_policy": "Ogni esecuzione consuma una unità, anche se la traiettoria è invalida. Rifiuti e messaggi invalidi non consumano.",
    }


def validate_observation(value, experiment, budget):
    """Controlla anche il confine in uscita: misure complete oppure errore senza punti."""
    require_keys(value, ("type", "request_id", "experiment_index", "status", "points", "error",
                         "executed_count", "remaining_budget"))
    if value["type"] != "observation":
        raise ValidationError("Tipo di risposta non valido.")
    identifier(value["request_id"])
    for key in ("experiment_index", "executed_count", "remaining_budget"):
        if type(value[key]) is not int:
            raise ValidationError("Contatore non valido.")
    if not (1 <= value["experiment_index"] == value["executed_count"] <= budget
            and value["remaining_budget"] == budget - value["executed_count"]):
        raise ValidationError("Contatori incoerenti.")
    if not isinstance(value["points"], list):
        raise ValidationError("Misure non valide.")
    if value["status"] == "error":
        require_keys(value["error"], ("code", "message"))
        if value["points"] or value["error"]["code"] != "TRAJECTORY_INVALID":
            raise ValidationError("Risposta di errore non valida.")
        text(value["error"]["message"])
    elif value["status"] == "ok":
        times = observation_times(experiment)
        if value["error"] is not None or len(value["points"]) != len(times):
            raise ValidationError("Misure incomplete.")
        for expected, point in zip(times, value["points"]):
            require_keys(point, ("t", "x", "y"))
            if not math.isclose(number(point["t"], 0, 5), expected, rel_tol=0, abs_tol=1e-9):
                raise ValidationError("Griglia delle misure non valida.")
            number(point["x"])
            number(point["y"])
    else:
        raise ValidationError("Stato della risposta non valido.")
    return value
