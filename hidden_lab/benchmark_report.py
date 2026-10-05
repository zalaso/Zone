"""Aggregazione descrittiva da trial salvati; nessun simulatore o provider."""

from collections import Counter, defaultdict
from hashlib import sha256
import json
import math
from pathlib import Path
import random
import statistics

from .benchmark_metrics import acceleration_metrics
from .benchmark_suite import digest
from .identification import (IDENTIFICATION_VERSION, identification_material,
                             score_scientific_submission)
from .protocol import ValidationError
from .simulator import parse_config

CONDITIONS = ("prior_only", "passive_fixed", "passive_sequential", "active")
CATEGORIES = ("interpolation", "extrapolation")


def _same(a, b):
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(_same(a[key], b[key]) for key in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b))
    if isinstance(a, float):
        return math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-12)
    return a == b


def _metric(item, name, category=None):
    metrics = item["metrics"]
    if category is not None and metrics is not None:
        metrics = metrics.get("by_category", {}).get(category)
    return metrics[name] if metrics is not None else None


def _identification_value(item, section, field, category=None):
    part = (item.get("identification") or {}).get(section)
    if category is not None and isinstance(part, dict):
        part = (part.get("metrics") or {}).get("by_category", {}).get(category)
    elif section == "functional" and isinstance(part, dict):
        part = part.get("metrics")
    return part.get(field) if isinstance(part, dict) else None


def _stats(values):
    values = [value for value in values if value is not None]
    return {"n": len(values), "mean": statistics.mean(values) if values else None,
            "median": statistics.median(values) if values else None,
            "sample_stdev": statistics.stdev(values) if len(values) >= 2 else None}


def _percentile(values, fraction):
    ordered = sorted(values)
    position = fraction * (len(ordered) - 1)
    low = math.floor(position)
    high = math.ceil(position)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def paired_bootstrap(paired, minimum_worlds=8, resamples=2000):
    """IC percentile descrittivi su mondi distinti; ripetizioni mediate entro mondo."""
    cohorts = defaultdict(list)
    for pair in paired:
        if pair["benchmark_version"] == "0.1" or not {"passive_sequential", "active"} <= pair["conditions"].keys():
            continue
        key = (pair["suite_hash"], pair["provider"], pair["model"], pair["trial_seed"],
               pair["experiment_budget"], json.dumps(pair["limits"], sort_keys=True),
               pair.get("provider_config_hash"), pair.get("code_version"), pair.get("code_hash"))
        cohorts[key].append(pair)
    output = []
    for key, group in sorted(cohorts.items(), key=lambda item: repr(item[0])):
        dimensions = {}
        for category in (None, *CATEGORIES):
            name = category or "overall"
            metrics = {}
            for metric in ("acceleration_rmse", "max_acceleration_error", "normalized_error"):
                by_world = defaultdict(list)
                for pair in group:
                    conditions = pair["conditions"]
                    def value(condition):
                        cell = conditions[condition]
                        return (cell.get(metric) if category is None else
                                cell.get("by_category", {}).get(category, {}).get(metric))
                    active, passive = value("active"), value("passive_sequential")
                    if active is not None and passive is not None:
                        by_world[pair["world_id"]].append(active - passive)
                world_deltas = [statistics.mean(values) for _, values in sorted(by_world.items())]
                record = {"n_independent_worlds": len(world_deltas), "minimum_worlds": minimum_worlds,
                          "mean_delta_active_minus_sequential": statistics.mean(world_deltas) if world_deltas else None,
                          "ci95": None, "status": "insufficient_sample"}
                if len(world_deltas) >= minimum_worlds:
                    seed = int.from_bytes(sha256(f"{key}:{name}:{metric}".encode()).digest()[:8], "big")
                    rng = random.Random(seed)
                    draws = [statistics.mean(rng.choices(world_deltas, k=len(world_deltas)))
                             for _ in range(resamples)]
                    record["ci95"] = [_percentile(draws, 0.025), _percentile(draws, 0.975)]
                    record["status"] = "descriptive_interval"
                metrics[metric] = record
            dimensions[name] = metrics
        output.append({"suite_hash": key[0], "provider": key[1], "model": key[2],
                       "trial_seed": key[3], "experiment_budget": key[4],
                       "limits": json.loads(key[5]), "provider_config_hash": key[6],
                       "code_version": key[7], "code_hash": key[8],
                       "resamples": resamples, "dimensions": dimensions})
    return output


def verify_saved_trial(directory):
    directory = Path(directory)
    result = json.loads((directory / "result.json").read_text(encoding="utf-8"))
    if result["metrics"] is not None:
        submission = json.loads((directory / "public" / "submission.json").read_text(encoding="utf-8"))
        truths = json.loads((directory / "private" / "probe_truth.json").read_text(encoding="utf-8"))
        challenges = []
        if result["benchmark_version"] != "0.1":
            events = [json.loads(line) for line in (directory / "public" / "events.jsonl").read_text(encoding="utf-8").splitlines()]
            challenges = [event["message"]["probes"] for event in events
                          if event["message"]["type"] == "probe_challenge"]
            if len(challenges) != 1 or [(probe.get("probe_id"), probe.get("category")) for probe in challenges[0]] != [
                    (truth.get("probe_id"), truth.get("category")) for truth in truths]:
                raise ValidationError("Categorie o ordine dei probe incoerenti con il challenge pubblico.")
        metrics = acceleration_metrics(submission["predictions"], truths)
        if not _same(metrics, result["metrics"]):
            raise ValidationError("Metriche salvate incoerenti con submission e verità del trial.")
        if result["benchmark_version"] != "0.1" and not metrics.get("by_category"):
            raise ValidationError("Metriche per categoria mancanti.")
        if result.get("identification") is not None or "law_ast_json" in submission or "uncertainty_sigma" in submission:
            if result.get("identification_version") != IDENTIFICATION_VERSION:
                raise ValidationError("Versione dell'identificazione non valida.")
            if not challenges:
                raise ValidationError("Challenge necessario per verificare la submission scientifica.")
            private_world = json.loads((directory / "private" / "world.json").read_text(encoding="utf-8"))
            if (private_world.get("suite_hash") != result["suite_hash"] or
                    private_world.get("world_id") != result["world_id"] or
                    digest(private_world.get("config")) != result["world_config_hash"]):
                raise ValidationError("Mondo privato del trial incoerente con il risultato.")
            config = parse_config(private_world["config"])
            material = identification_material(private_world["config"]["seed"], result["world_id"],
                                               f"{result['suite_hash']}:{result['repetition']}")
            scores, audit = score_scientific_submission(submission, challenges[0], config.world, material)
            identification = {key: scores[key] for key in
                              ("functional", "complexity", "dependencies", "calibration")}
            if not _same(scores["prediction"], result["metrics"]) or not _same(identification, result.get("identification")):
                raise ValidationError("Identificazione salvata incoerente con la submission.")
            if not _same(audit["probe_truth"], truths):
                raise ValidationError("Verità dei probe incoerente con il mondo privato.")
            if audit["secret_grid"] is not None:
                saved_grid = json.loads((directory / "private" / "identification_grid.json").read_text(encoding="utf-8"))
                if not _same(audit["secret_grid"], saved_grid):
                    raise ValidationError("Griglia privata di identificazione incoerente.")
    return result


def aggregate_trials(root, include_contaminated=False):
    root = Path(root)
    paths = sorted(root.rglob("result.json"))
    if not paths:
        raise ValidationError("Nessun trial completato trovato.")
    results = [verify_saved_trial(path.parent) for path in paths]
    trial_ids = [result["trial_id"] for result in results]
    if len(trial_ids) != len(set(trial_ids)):
        raise ValidationError("Trial duplicato.")
    selected = [item for item in results if include_contaminated or not item["contaminated"]]
    scopes = {(item.get("integrity") or {}).get("manifest_hash", "untracked") + ":" +
              (item.get("integrity") or {}).get("split", "untracked") for item in selected}
    if len(scopes) > 1:
        raise ValidationError("Non aggregare split, manifest integrità o trial non tracciati diversi nello stesso report.")
    if len({item["benchmark_version"] for item in selected}) > 1:
        raise ValidationError("Non aggregare trial di versioni benchmark diverse nello stesso report.")
    by_condition = {}
    for condition in CONDITIONS:
        group = [item for item in selected if item["condition"] == condition]
        by_condition[condition] = {
            "n": len(group), "status_counts": dict(Counter(item["status"] for item in group)),
            "acceleration_rmse": _stats([item["metrics"]["acceleration_rmse"] if item["metrics"] else None for item in group]),
            "max_acceleration_error": _stats([_metric(item, "max_acceleration_error") for item in group]),
            "normalized_error": _stats([item["metrics"]["normalized_error"] if item["metrics"] else None for item in group]),
            "by_category": {category: {name: _stats([_metric(item, name, category) for item in group])
                             for name in ("acceleration_rmse", "max_acceleration_error", "normalized_error")}
                             for category in CATEGORIES},
            "executed_experiments": _stats([item["executed_experiments"] for item in group]),
            "observation_count": _stats([item.get("observation_count") for item in group]),
            "observation_points": _stats([item.get("observation_points") for item in group]),
            "model_calls": _stats([item["model_calls"] for item in group]),
            "api_cost_usd": _stats([item.get("api_cost_usd") for item in group]),
            "duration_seconds": _stats([item["duration_seconds"] for item in group]),
            "invalid_responses": sum(item["invalid_responses"] for item in group),
            "corrections": sum(item["corrections"] for item in group),
            "usage_records": [record for item in group for record in item["usage_records"]],
            "identification": {
                "functional_rmse": _stats([_identification_value(item, "functional", "acceleration_rmse") for item in group]),
                "functional_interpolation_rmse": _stats([_identification_value(item, "functional", "acceleration_rmse", "interpolation") for item in group]),
                "functional_extrapolation_rmse": _stats([_identification_value(item, "functional", "acceleration_rmse", "extrapolation") for item in group]),
                "functional_equivalent": sum(((item.get("identification") or {}).get("functional") or {}).get(
                    "empirically_equivalent") is True for item in group),
                "complexity_nodes": _stats([_identification_value(item, "complexity", "node_count") for item in group]),
                "dependencies_exact": sum(_identification_value(item, "dependencies", "exact_match") is True for item in group),
                "calibration_nll": _stats([_identification_value(item, "calibration", "mean_gaussian_nll") for item in group]),
            },
        }
    by_model_condition = []
    model_cells = defaultdict(list)
    for item in selected:
        model_cells[(item["provider"], item["model"], item["condition"])].append(item)
    for (provider, model, condition), group in sorted(model_cells.items()):
        by_model_condition.append({"provider": provider, "model": model, "condition": condition,
            "n": len(group), "status_counts": dict(Counter(item["status"] for item in group)),
            "acceleration_rmse": _stats([_metric(item, "acceleration_rmse") for item in group]),
            "interpolation_rmse": _stats([_metric(item, "acceleration_rmse", "interpolation") for item in group]),
            "extrapolation_rmse": _stats([_metric(item, "acceleration_rmse", "extrapolation") for item in group]),
            "model_calls": _stats([item["model_calls"] for item in group]),
            "api_cost_usd": _stats([item.get("api_cost_usd") for item in group])})
        by_model_condition[-1]["identification"] = {
            "functional_rmse": _stats([_identification_value(item, "functional", "acceleration_rmse") for item in group]),
            "complexity_nodes": _stats([_identification_value(item, "complexity", "node_count") for item in group]),
            "calibration_nll": _stats([_identification_value(item, "calibration", "mean_gaussian_nll") for item in group]),
        }
    groups = defaultdict(list)
    for item in selected:
        key = (item["benchmark_version"], item["suite_hash"], item["world_id"], item["repetition"],
               item["provider"], item["model"], item["trial_seed"])
        groups[key].append(item)
    paired = []
    ambiguous_pairs = 0
    rejected_pairs = []
    for key, group in sorted(groups.items()):
        conditions = defaultdict(list)
        for item in group:
            conditions[item["condition"]].append(item)
        if any(len(items) != 1 for items in conditions.values()):
            ambiguous_pairs += 1
            continue
        if len(conditions) < 2:
            continue
        mismatch = [field for field in ("experiment_budget", "probe_hash", "limits", "world_config_hash",
                                        "provider_config_hash", "code_version", "code_hash", "integrity")
                    if len({json.dumps(item.get(field), sort_keys=True) for item in group}) > 1]
        if mismatch:
            rejected_pairs.append({"world_id": key[2], "repetition": key[3],
                                   "conditions": sorted(conditions), "mismatches": mismatch})
            continue
        required = ("prior_only", "passive_fixed", "active") if key[0] == "0.1" else ("passive_sequential", "active")
        if not all(condition in conditions for condition in required):
            continue
        included = ("prior_only", "passive_fixed", "active") if key[0] == "0.1" else tuple(
            condition for condition in CONDITIONS if condition in conditions)
        first = group[0]
        paired.append({"benchmark_version": key[0], "suite_hash": key[1], "world_id": key[2],
                       "repetition": key[3], "provider": key[4], "model": key[5], "trial_seed": key[6],
                       "experiment_budget": first["experiment_budget"], "probe_hash": first["probe_hash"],
                       "limits": first["limits"], "world_config_hash": first.get("world_config_hash"),
                       "provider_config_hash": first.get("provider_config_hash"),
                       "code_version": first.get("code_version"), "code_hash": first.get("code_hash"),
                       "conditions": {condition: {"trial_id": conditions[condition][0]["trial_id"],
                           "acceleration_rmse": _metric(conditions[condition][0], "acceleration_rmse"),
                           "max_acceleration_error": _metric(conditions[condition][0], "max_acceleration_error"),
                           "normalized_error": _metric(conditions[condition][0], "normalized_error"),
                           "by_category": {category: {name: _metric(conditions[condition][0], name, category)
                               for name in ("acceleration_rmse", "max_acceleration_error", "normalized_error")}
                               for category in CATEGORIES}}
                           for condition in included}})
    accuracy_vs_experiments = []
    cells = defaultdict(list)
    for item in selected:
        if item["metrics"] is not None:
            cells[(item["provider"], item["model"], item["condition"], item["executed_experiments"])].append(item["metrics"]["acceleration_rmse"])
    for (provider, model, condition, executed), values in sorted(cells.items()):
        accuracy_vs_experiments.append({"provider": provider, "model": model,
                                        "condition": condition, "executed_experiments": executed,
                                        "acceleration_rmse": _stats(values)})
    return {"report_version": "0.3", "trial_count": len(results), "included_count": len(selected),
            "integrity_scope": next(iter(scopes), "untracked"),
            "excluded_contaminated": len(results) - len(selected), "include_contaminated": include_contaminated,
            "trials": selected, "by_condition": by_condition, "by_model_condition": by_model_condition,
            "paired": paired,
            "ambiguous_pair_groups": ambiguous_pairs, "rejected_pair_groups": rejected_pairs,
            "bootstrap_contrasts": paired_bootstrap(paired),
            "accuracy_vs_experiments": accuracy_vs_experiments}


def _fmt(value):
    return "—" if value is None else f"{value:.6g}" if isinstance(value, float) else str(value)


def render_report(data):
    lines = ["# Zone Benchmark v0.3 — report descrittivo", "",
             f"Trial inclusi: {data['included_count']} di {data['trial_count']}; contaminati esclusi: {data['excluded_contaminated']}.",
             "Fixture e baseline offline non sono modelli LLM. Nessuna inferenza di superiorità statistica.",
             f"Provenienza split/manifest: {data.get('integrity_scope', 'untracked')}. I fixture oracolo non sono valutazioni cieche.",
             "Confronto principale: active vs passive_sequential; passive_fixed è una diagnosi batch.",
             f"Gruppi appaiati ambigui: {data['ambiguous_pair_groups']}; rifiutati per configurazione: {len(data.get('rejected_pair_groups', []))}.", "",
             "## Trial grezzi", "",
             "| Mondo | Rip. | Condizione | Provider/modello | Stato/arresto | Richiesti/eseguiti/falliti | Osservazioni/punti | Probe validi tot/int/ext | RMSE totale | Max totale | Norm totale | RMSE interpolation | Max interpolation | Norm interpolation | RMSE extrapolation | Max extrapolation | Norm extrapolation | Chiamate | Turni validi | Invalidi | Correzioni | Durata s | Costo API noto USD | Utilizzo nativo |",
             "| --- | ---: | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |"]
    lines[-1] = "| " + " | ".join(["---"] * (lines[-2].count("|") - 1)) + " |"
    names = ("acceleration_rmse", "max_acceleration_error", "normalized_error")
    for item in data["trials"]:
        values = [_metric(item, name) for name in names]
        values += [_metric(item, name, category) for category in CATEGORIES for name in names]
        probe_counts = "/".join(_fmt(_metric(item, "valid_probe_count", category))
                                for category in (None, *CATEGORIES))
        usage = json.dumps(item["usage_records"], ensure_ascii=False, separators=(",", ":"))
        lines.append(f"| {item['world_id']} | {item['repetition']} | {item['condition']} | {item['provider']}/{item['model']} | "
                     f"{item['status']}/{_fmt(item['stop_reason'])} | {item['requested_experiments']}/{item['executed_experiments']}/{item['failed_experiments']} | {_fmt(item.get('observation_count'))}/{_fmt(item.get('observation_points'))} | "
                     + probe_counts + " | " + " | ".join(_fmt(value) for value in values) +
                     f" | {item['model_calls']} | {_fmt(item.get('valid_turns'))} | {item['invalid_responses']} | {item['corrections']} | {_fmt(item['duration_seconds'])} | {_fmt(item.get('api_cost_usd'))} | {usage} |")
    lines += ["", "## Condizioni", "",
              "Riepilogo descrittivo: se la cartella contiene modelli o baseline diversi, usa anche la tabella stratificata qui sotto.", "",
              "| Condizione | n trial | RMSE medio | Max medio | Norm medio | n interpolation | RMSE interpolation | Max interpolation | Norm interpolation | n extrapolation | RMSE extrapolation | Max extrapolation | Norm extrapolation | Osservazioni medie | Punti medi | Chiamate medie | Invalidi | Stati |",
              "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |"]
    lines[-1] = "| " + " | ".join(["---"] * (lines[-2].count("|") - 1)) + " |"
    for condition in CONDITIONS:
        item = data["by_condition"][condition]
        values = [item[name]["mean"] for name in names]
        values += [value for category in CATEGORIES for value in
                   (item["by_category"][category]["acceleration_rmse"]["n"],
                    *(item["by_category"][category][name]["mean"] for name in names))]
        lines.append(f"| {condition} | {item['n']} | " + " | ".join(_fmt(value) for value in values) +
                     f" | {_fmt(item['observation_count']['mean'])} | {_fmt(item['observation_points']['mean'])} | {_fmt(item['model_calls']['mean'])} | "
                     f"{item['invalid_responses']} | {json.dumps(item['status_counts'], ensure_ascii=False)} |")
    if data.get("by_model_condition"):
        lines += ["", "## Provider e modello, senza mescolare strategie", "",
                  "| Provider/modello | Condizione | n | RMSE totale medio | RMSE interpolation medio | RMSE extrapolation medio | Chiamate medie | Costo API noto USD | Stati |",
                  "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |"]
        for item in data["by_model_condition"]:
            lines.append(f"| {item['provider']}/{item['model']} | {item['condition']} | {item['n']} | "
                         f"{_fmt(item['acceleration_rmse']['mean'])} | {_fmt(item['interpolation_rmse']['mean'])} | "
                         f"{_fmt(item['extrapolation_rmse']['mean'])} | {_fmt(item['model_calls']['mean'])} | "
                         f"{_fmt(item['api_cost_usd']['mean'])} | {json.dumps(item['status_counts'], ensure_ascii=False)} |")
    lines += ["", "## Identificazione AST e calibrazione — dimensioni separate", "",
              "La previsione numerica sui probe resta la metrica principale. L'equivalenza è solo empirica sulla griglia privata; i campi assenti indicano submission storiche senza AST o incertezza.", "",
              "| Condizione | AST valutati | Equivalenti | RMSE funzione totale | RMSE interpolation | RMSE extrapolation | Nodi medi | Dipendenze esatte | NLL calibrazione media |",
              "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for condition in CONDITIONS:
        item = data["by_condition"][condition]["identification"]
        lines.append(f"| {condition} | {item['functional_rmse']['n']} | {item['functional_equivalent']} | "
                     f"{_fmt(item['functional_rmse']['mean'])} | {_fmt(item['functional_interpolation_rmse']['mean'])} | "
                     f"{_fmt(item['functional_extrapolation_rmse']['mean'])} | {_fmt(item['complexity_nodes']['mean'])} | "
                     f"{item['dependencies_exact']} | {_fmt(item['calibration_nll']['mean'])} |")
    lines += ["", "### Trial con submission scientifica", "",
              "| Mondo | Condizione | Equivalenza | RMSE funzione int/ext | Nodi/profondità | Dipendenze (corrette/mancate/spurie) | Coverage 68/95 | NLL |",
              "| --- | --- | --- | --- | --- | --- | --- | ---: |"]
    for item in data["trials"]:
        identification = item.get("identification")
        if not identification:
            continue
        functional = identification.get("functional") or {}
        complexity = identification.get("complexity") or {}
        dependencies = identification.get("dependencies") or {}
        calibration = identification.get("calibration") or {}
        int_rmse = _identification_value(item, "functional", "acceleration_rmse", "interpolation")
        ext_rmse = _identification_value(item, "functional", "acceleration_rmse", "extrapolation")
        lines.append(f"| {item['world_id']} | {item['condition']} | {_fmt(functional.get('empirically_equivalent'))} | "
                     f"{_fmt(int_rmse)}/{_fmt(ext_rmse)} | {_fmt(complexity.get('node_count'))}/{_fmt(complexity.get('max_depth'))} | "
                     f"{_fmt(dependencies.get('correct_count'))}/{_fmt(dependencies.get('missed_count'))}/{_fmt(dependencies.get('spurious_count'))} | "
                     f"{_fmt(calibration.get('coverage_68'))}/{_fmt(calibration.get('coverage_95'))} | "
                     f"{_fmt(calibration.get('mean_gaussian_nll'))} |")
    lines += ["", "## Confronti appaiati", "",
              "Stesso mondo, ripetizione, provider, modello, seed, budget, probe, limiti e configurazione.", "",
              "| Mondo | Rip. | Provider/modello | Budget | Prior RMSE | Passive batch RMSE | Passive sequential RMSE | Active RMSE |",
              "| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |"]
    for pair in data["paired"]:
        c = pair["conditions"]
        lines.append(f"| {pair['world_id']} | {pair['repetition']} | {pair['provider']}/{pair['model']} | {pair['experiment_budget']} | "
                     + " | ".join(_fmt(c.get(condition, {}).get("acceleration_rmse")) for condition in CONDITIONS) + " |")
    lines += ["", "## Intervalli bootstrap descrittivi", "",
              "Delta = active − passive_sequential; mondi distinti sono le unità di ricampionamento. "
              "Le ripetizioni dello stesso mondo sono mediate. Nessun intervallo sotto otto mondi indipendenti.", "",
              "| Provider/modello | Dimensione | Metrica | Mondi | Delta medio | IC 95% | Stato |",
              "| --- | --- | --- | ---: | ---: | --- | --- |"]
    for cohort in data.get("bootstrap_contrasts", []):
        for dimension, metrics in cohort["dimensions"].items():
            for metric, record in metrics.items():
                ci = record["ci95"]
                interval = f"[{_fmt(ci[0])}, {_fmt(ci[1])}]" if ci else "—"
                lines.append(f"| {cohort['provider']}/{cohort['model']} | {dimension} | {metric} | "
                             f"{record['n_independent_worlds']} | {_fmt(record['mean_delta_active_minus_sequential'])} | "
                             f"{interval} | {record['status']} |")
    lines += ["", "## Accuratezza per esperimenti eseguiti", "",
              "| Provider/modello | Condizione | Esperimenti | n | RMSE medio m/s² |",
              "| --- | --- | ---: | ---: | ---: |"]
    for row in data["accuracy_vs_experiments"]:
        label = f"{row.get('provider', 'legacy')}/{row.get('model', 'legacy')}"
        lines.append(f"| {label} | {row['condition']} | {row['executed_experiments']} | {row['acceleration_rmse']['n']} | "
                     f"{_fmt(row['acceleration_rmse']['mean'])} |")
    lines += ["", "I conteggi d'uso conservano i nomi nativi dei provider e non sono confrontati come unità identiche.", ""]
    return "\n".join(lines)
