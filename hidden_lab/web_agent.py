"""Agente del laboratorio: contratto pubblico e baseline senza accesso al mondo."""

from dataclasses import replace
import json

from .agent_contract import (INSTRUCTIONS, ModelRequest, NUMBER, STRING, _project,
                             build_request, obj, public_history, response_schema)
from .benchmark_baselines import fit_affine_acceleration, predict_affine
from .benchmark_contract import IDENTIFICATION_INSTRUCTIONS
from .protocol import ValidationError, decode, require_keys
from .provider_base import ModelReply, metadata

CHALLENGE_SHAPE = {"world_id": None, "probes": [{key: None for key in
                   ("probe_id", "category", "x", "y", "vx", "vy")}]}


def build_web_request(events, settings, state, remaining_calls, remaining_turns, *, paired=False):
    if state.status() == "awaiting_submission":
        history = public_history(events)
        event = next(event for event in events if event["message"]["type"] == "probe_challenge")
        history.append({"seq": event["seq"], "actor": "apparatus",
                        "message": {"type": "probe_challenge", **_project(event["message"], CHALLENGE_SHAPE)}})
        fields = {"type": {"type": "string", "enum": ["scientific_submission"]},
                  "predictions": {"type": "array", "items": obj({"probe_id": STRING, "ax": NUMBER, "ay": NUMBER})}}
        variants = [obj({**fields, **extension}) for extension in
                    ({}, {"law_ast_json": STRING}, {"uncertainty_sigma": {"type": "array", "items": NUMBER}},
                     {"law_ast_json": STRING, "uncertainty_sigma": {"type": "array", "items": NUMBER}})]
        return ModelRequest(settings.model, INSTRUCTIONS + IDENTIFICATION_INSTRUCTIONS +
            '\nOra emetti scientific_submission con previsioni di accelerazione per tutti i probe, in ordine.',
            history, {"phase": "submission", "remaining_model_calls": remaining_calls,
                      "remaining_turns": remaining_turns}, ("scientific_submission",),
            obj({"message": {"anyOf": variants}}), settings.max_output_tokens)
    request = build_request(events, settings, "predict" if state.status() == "awaiting_prediction" else "choose_next",
                            remaining_calls, remaining_turns)
    kinds = list(request.allowed_types)
    if paired:
        kinds.remove("operator_question")
    if state.status() == "discovering":
        latest_observation = max((e["seq"] for e in request.history if e["message"]["type"] == "observation"), default=0)
        latest_hypothesis = max((e["seq"] for e in request.history if e["message"]["type"] == "hypothesis"), default=0)
        if latest_observation > latest_hypothesis:
            kinds = ["hypothesis", "conclusion"]
        elif state.executed_count >= state.budget:
            kinds = [kind for kind in kinds if kind != "experiment_request"]
    if (remaining_turns <= 2 or remaining_calls <= 1) and state.status() != "awaiting_prediction":
        kinds = ["conclusion"]  # Leave one turn for the frozen submission.
    return replace(request, allowed_types=tuple(kinds), schema=response_schema(kinds),
                   context={**request.context, "allowed_types": kinds,
                            "remaining_experiments": state.budget - state.executed_count})


def decode_reply(reply, allowed_types):
    if reply.issue:
        raise ValidationError("Risposta agente incompleta o rifiutata.")
    value = decode(reply.text)
    require_keys(value, ("message",))
    message = value["message"]
    if not isinstance(message, dict) or message.get("type") not in allowed_types:
        raise ValidationError("Messaggio non ammesso in questa fase.")
    return message


def safe_metadata(reply):
    data = reply.metadata
    usage = data.get("usage")
    clean_usage = {k: v for k, v in (usage or {}).items() if k in
                      ("input_tokens", "output_tokens", "total_tokens", "cached_input_tokens", "reasoning_tokens")
                      and type(v) is int and v >= 0} if isinstance(usage, dict) else None
    if clean_usage is not None:
        for group, field in (("input_tokens_details", "cached_tokens"), ("output_tokens_details", "reasoning_tokens")):
            value = usage.get(group)
            count = value.get(field) if isinstance(value, dict) else None
            if type(count) is int and count >= 0:
                clean_usage[group] = {field: count}
    details = data.get("provider_details")
    native = details.get("usage") if isinstance(details, dict) else None
    native_keys = ("cache_creation_input_tokens", "cache_read_input_tokens", "prompt_eval_count",
                   "prompt_eval_cached_count", "eval_count", "prompt_token_count", "candidates_token_count",
                   "total_token_count", "cached_content_token_count", "thoughts_token_count")
    clean_native = {key: value for key, value in native.items() if key in native_keys
                    and type(value) is int and value >= 0} if isinstance(native, dict) else None
    return {"response_id": data.get("response_id") if isinstance(data.get("response_id"), str) and len(data["response_id"]) <= 256 else None,
            "returned_model": data.get("returned_model") if isinstance(data.get("returned_model"), str) and len(data["returned_model"]) <= 128 else None,
            "status": data.get("status") if isinstance(data.get("status"), str) and len(data["status"]) <= 64 else None,
            "usage": clean_usage, "provider_details": {"usage": clean_native} if clean_native is not None else None}


def safe_generation(client):
    """Impostazioni documentate dagli adapter; esclude campi aggiunti o credenziali."""
    value = getattr(client, "generation_settings", {})
    allowed = ("real_model", "policy", "response_format", "response_mime_type", "store", "truncation",
               "max_output_tokens", "max_retries", "timeout_seconds", "stream", "format", "temperature",
               "thinking_budget", "thinking_level", "num_predict", "max_tokens", "response_json_schema",
               "retry_attempts", "automatic_download", "retries", "authentication", "max_output_tokens_supported",
               "local_response_limit_bytes", "text_extraction_version")
    result = {key: value[key] for key in allowed if key in value and
            (value[key] is None or type(value[key]) in (str, int, float, bool))}
    if value.get("tools") == []:
        result["tools"] = []
    return result


class OfflineLabClient:
    """Baseline numerica: dati pubblici, fit affine e proposte prefissate; nessun oracolo."""
    provider = "offline_baseline"
    sdk_version = None
    generation_settings = {"real_model": False, "policy": "public_affine_v1"}

    def complete(self, request):
        messages = [event["message"] for event in request.history]
        observations = [m for m in messages if m["type"] == "observation"]
        hypotheses = [m for m in messages if m["type"] == "hypothesis"]
        requests = [m for m in messages if m["type"] == "experiment_request"]
        evidence = [m["request_id"] for m in observations if m["status"] == "ok"]
        if request.context["phase"] == "submission":
            probes = next(m["probes"] for m in messages if m["type"] == "probe_challenge")
            message = {"type": "scientific_submission", "predictions": predict_affine(request.history, probes)}
        elif request.context["phase"] == "predict" and hypotheses:
            experiment = request.context["approved_experiment"]
            state = {"probe_id": "estimate", **experiment["initial_position"],
                     "vx": experiment["initial_velocity"]["x"], "vy": experiment["initial_velocity"]["y"]}
            prediction = predict_affine(request.history, [state])[0]
            points = [{"t": t, **{axis: experiment["initial_position"][axis] +
                      experiment["initial_velocity"][axis] * t + prediction[f"a{axis}"] * t * t / 2
                      for axis in ("x", "y")}} for t in request.context["prediction_times"]]
            message = {"type": "prediction", "prediction_id": f"pred{len(requests)}",
                       "hypothesis_id": hypotheses[-1]["hypothesis_id"],
                       "request_id": request.context["request_id"], "points": points}
        elif "hypothesis" in request.allowed_types and (request.context["phase"] == "predict" or
                not hypotheses or len(observations) > len(hypotheses) - 1):
            coefficients = fit_affine_acceleration(request.history)
            message = {"type": "hypothesis", "hypothesis_id": f"offline_h{len(hypotheses)+1}",
                       "statement": f"Fit affine da sole posizioni pubbliche: ax,ay = c0+c1*y+c2*vx+c3*vy; coefficienti {coefficients}.",
                       "uncertainties": ["Baseline numerica, non un LLM. Fit limitato e sensibile al rumore; dipendenza da x e non linearità non rappresentate."],
                       "evidence": evidence}
        elif "experiment_request" in request.allowed_types and len(requests) < 4:
            x, y, vx, vy = ((0, 0, 3, 4), (3, 6, -4, 1), (-3, -5, 6, -4), (2, -3, -5, 5))[len(requests)]
            message = {"type": "experiment_request", "request_id": f"offline_e{len(requests)+1}",
                       "purpose": "Raccogliere posizioni per un fit affine; policy offline senza accesso alla legge.",
                       "experiment": {"initial_position": {"x": x, "y": y}, "initial_velocity": {"x": vx, "y": vy},
                                      "duration": 0.5, "observation_interval": 0.25}}
        else:
            message = {"type": "conclusion", "final_hypothesis_id": hypotheses[-1]["hypothesis_id"] if hypotheses else None,
                       "summary": "Baseline offline conclusa. Il fit numerico non prova identificazione della legge.",
                       "evidence": evidence, "limits": ["Classe affine limitata; nessuna prova di equivalenza generale."],
                       "alternatives": ["Leggi non lineari e dipendenze non osservate restano plausibili."]}
        return ModelReply(json.dumps({"message": message}, ensure_ascii=False, allow_nan=False),
                          metadata(returned_model="offline-affine-v1", status="completed"))

    def close(self):
        pass
