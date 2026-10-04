"""Submission scientifica e valutazione separata; la griglia della verità resta privata."""

from collections import Counter
from hashlib import sha256
import json
import math
import random

from .benchmark_metrics import acceleration_metrics
from .protocol import ValidationError, decode, identifier, number, require_keys
from .simulator import TrajectoryError, acceleration_at
from .world_ast import evaluate_law, parse_law

IDENTIFICATION_VERSION = "1"
GRID_PER_CATEGORY = 64
MAX_LAW_AST_BYTES = 8000
VARIABLES = ("x", "y", "vx", "vy")
EQUIVALENCE_ABS_TOL = 1e-3
EQUIVALENCE_REL_TOL = 1e-3


def identification_material(physical_seed, world_id, context):
    """Derivazione locale della griglia, mai inclusa nella richiesta al modello."""
    return f"{physical_seed}:{world_id}:{context}"


def parse_public_law(raw):
    """Il testo contiene solo JSON AST; non è mai una formula eseguibile."""
    if type(raw) is not str or len(raw.encode("utf-8")) > MAX_LAW_AST_BYTES:
        raise ValidationError("Legge AST JSON troppo grande o non valida.")
    law = parse_law(decode(raw))
    return law.canonical_json()


def validate_scientific_submission(value, probe_ids):
    """Stesso sottoinsieme per file umani e benchmark agenti."""
    require_keys(value, ("predictions",), ("law_ast_json", "uncertainty_sigma"))
    if not isinstance(value["predictions"], list) or len(value["predictions"]) != len(probe_ids) or not probe_ids:
        raise ValidationError("Serve una previsione per ogni probe pubblico.")
    predictions = []
    for expected, prediction in zip(probe_ids, value["predictions"]):
        require_keys(prediction, ("probe_id", "ax", "ay"))
        if identifier(prediction["probe_id"]) != expected:
            raise ValidationError("Probe mancanti, duplicati o fuori ordine.")
        predictions.append({"probe_id": expected, "ax": number(prediction["ax"]),
                            "ay": number(prediction["ay"])})
    result = {"predictions": predictions}
    if "law_ast_json" in value:
        result["law_ast_json"] = parse_public_law(value["law_ast_json"])
    if "uncertainty_sigma" in value:
        sigmas = value["uncertainty_sigma"]
        if not isinstance(sigmas, list) or len(sigmas) != len(probe_ids):
            raise ValidationError("Serve una deviazione standard per ogni probe.")
        result["uncertainty_sigma"] = [number(sigma, 0.001, 1000) for sigma in sigmas]
    return result


def secret_grid(material):
    """128 stati deterministici; material deve includere un seed fisico privato."""
    if not isinstance(material, str) or not material:
        raise ValidationError("Materiale privato della griglia mancante.")
    seed = int.from_bytes(sha256(f"zone-identification-v{IDENTIFICATION_VERSION}:{material}".encode()).digest(), "big")
    rng = random.Random(seed)
    states = []
    for category in ("interpolation", "extrapolation"):
        for _ in range(GRID_PER_CATEGORY):
            if category == "interpolation":
                x, y = rng.uniform(-18, 18), rng.uniform(-18, 18)
            else:
                outer = rng.uniform(25, 55) * rng.choice((-1, 1))
                inner = rng.uniform(-18, 18)
                x, y = (outer, inner) if rng.randrange(2) else (inner, outer)
            states.append({"category": category, "x": x, "y": y,
                           "vx": rng.uniform(-18, 18), "vy": rng.uniform(-18, 18)})
    return states


def _state(row):
    return tuple(row[key] for key in VARIABLES)


def _complexity(law):
    operations = Counter()
    def walk(node):
        operations[node.op] += 1
        children = [walk(child) for child in node.args]
        return 1 + sum(count for count, _ in children), 1 + max((depth for _, depth in children), default=0)
    left, right = walk(law.ax), walk(law.ay)
    return {"level": law.level, "node_count": left[0] + right[0],
            "max_depth": max(left[1], right[1]), "operations": dict(sorted(operations.items()))}


def _dependencies(accelerate, anchors):
    found = set()
    for name in VARIABLES:
        index = VARIABLES.index(name)
        for row in anchors:
            base_state = _state(row)
            changed = list(base_state)
            changed[index] += 0.5
            base, shifted = accelerate(base_state), accelerate(tuple(changed))
            delta = math.dist(base, shifted)
            if delta > 1e-3 * max(1.0, math.hypot(*base)):
                found.add(name)
                break
    return found


def _calibration(predictions, truths, sigmas):
    def metrics(indices):
        values = []
        for index in indices:
            prediction, truth, sigma = predictions[index], truths[index], sigmas[index]
            error = math.hypot(prediction["ax"] - truth["ax"], prediction["ay"] - truth["ay"])
            values.append((error, sigma))
        return {"count": len(values), "mean_sigma": sum(s for _, s in values) / len(values),
                "coverage_68": sum(e <= 1.5095921854516636 * s for e, s in values) / len(values),
                "coverage_95": sum(e <= 2.447746830680816 * s for e, s in values) / len(values),
                "mean_gaussian_nll": sum(math.log(2 * math.pi * s * s) + e * e / (2 * s * s)
                                         for e, s in values) / len(values)}
    result = metrics(range(len(truths)))
    if all("category" in truth for truth in truths):
        result["by_category"] = {category: metrics(indices) for category in
            ("interpolation", "extrapolation")
            for indices in [[index for index, truth in enumerate(truths) if truth["category"] == category]]
            if indices}
    return result


def score_scientific_submission(submission, probes, world, secret_material):
    """Ritorna metriche pubblicabili e audit privato; nessuna verità nei payload LLM."""
    probe_ids = tuple(probe["probe_id"] for probe in probes)
    normalized = validate_scientific_submission({key: submission[key] for key in
        ("predictions", "law_ast_json", "uncertainty_sigma") if key in submission}, probe_ids)
    truths = []
    for probe in probes:
        ax, ay = acceleration_at(world, _state(probe))
        truth = {"probe_id": probe["probe_id"], "ax": ax, "ay": ay}
        if "category" in probe:
            truth["category"] = probe["category"]
        truths.append(truth)
    prediction = acceleration_metrics(normalized["predictions"], truths)
    calibration = (_calibration(normalized["predictions"], truths, normalized["uncertainty_sigma"])
                   if "uncertainty_sigma" in normalized else None)
    functional = complexity = dependencies = private_grid = None
    if "law_ast_json" in normalized:
        law = parse_law(decode(normalized["law_ast_json"]))
        complexity = _complexity(law)
        grid = secret_grid(secret_material)
        private_grid = []
        predicted, actual = [], []
        valid = True
        for index, row in enumerate(grid, 1):
            truth_ax, truth_ay = acceleration_at(world, _state(row))
            private_grid.append({**row, "probe_id": f"g{index:03d}", "ax": truth_ax, "ay": truth_ay})
            actual.append({"probe_id": f"g{index:03d}", "category": row["category"],
                           "ax": truth_ax, "ay": truth_ay})
            try:
                proposed_ax, proposed_ay = evaluate_law(law, _state(row))
            except ValidationError:
                valid = False
            else:
                if valid:
                    predicted.append({"probe_id": f"g{index:03d}", "ax": proposed_ax, "ay": proposed_ay})
        if valid:
            errors = [math.hypot(proposal["ax"] - truth["ax"], proposal["ay"] - truth["ay"])
                      for proposal, truth in zip(predicted, actual)]
            equivalent = all(error <= EQUIVALENCE_ABS_TOL + EQUIVALENCE_REL_TOL *
                             math.hypot(truth["ax"], truth["ay"])
                             for error, truth in zip(errors, actual))
            functional = {"status": "evaluated", "empirically_equivalent": equivalent,
                          "grid_version": IDENTIFICATION_VERSION,
                          "metrics": acceleration_metrics(predicted, actual),
                          "absolute_tolerance": EQUIVALENCE_ABS_TOL,
                          "relative_tolerance": EQUIVALENCE_REL_TOL}
            try:
                anchors = grid[::8]
                proposed_dependencies = _dependencies(lambda state: evaluate_law(law, state), anchors)
                true_dependencies = _dependencies(lambda state: acceleration_at(world, state), anchors)
                dependencies = {"status": "evaluated", "proposed": sorted(proposed_dependencies),
                                "correct_count": len(proposed_dependencies & true_dependencies),
                                "missed_count": len(true_dependencies - proposed_dependencies),
                                "spurious_count": len(proposed_dependencies - true_dependencies),
                                "exact_match": proposed_dependencies == true_dependencies}
            except (ValidationError, TrajectoryError):
                dependencies = {"status": "unavailable"}
        else:
            functional = {"status": "undefined_on_secret_grid", "empirically_equivalent": False,
                          "grid_version": IDENTIFICATION_VERSION, "metrics": None,
                          "evaluated_before_failure": len(predicted)}
    scores = {"prediction": prediction, "functional": functional,
              "complexity": complexity, "dependencies": dependencies,
              "calibration": calibration}
    audit = {"probe_truth": truths, "secret_grid": private_grid}
    return scores, audit
