"""Mondi costruiti localmente: stesso AST e simulatore, schema distinto da Forge v1."""

import copy
from hashlib import sha256
import json
import math
import secrets

from .protocol import ValidationError, require_keys
from .simulator import TrajectoryError, acceleration_at, parse_config, simulate
from .world_ast import parse_law
from .world_forge import (PROBE_STATES, SCHEDULE, public_manifest,
                          validate_generated_world)

BUILDER_VERSION = "1"


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                             allow_nan=False).encode()).hexdigest()


def _record(law, seed, budget):
    config = {"world": {"family": "ast", "law": law.to_dict()}, "seed": seed,
              "noise_std": 0.0, "integration_step": 0.005, "experiment_budget": budget}
    data = {"builder_version": BUILDER_VERSION, "level": law.level, "config": config,
            "schedule": copy.deepcopy(list(SCHEDULE[:budget])),
            "probes": [{"probe_id": f"p{i:02d}", "category": category,
                        "x": x, "y": y, "vx": vx, "vy": vy}
                       for i, (category, x, y, vx, vy) in enumerate(PROBE_STATES, 1)]}
    data["world_id"] = "w" + digest(data)[:16]
    data["sha256"] = digest(data)
    return data


def validate_built_world(record):
    require_keys(record, ("builder_version", "level", "config", "schedule", "probes", "world_id", "sha256"))
    config = parse_config(record["config"])
    if (record["builder_version"] != BUILDER_VERSION or config.world.family != "ast"
            or not 1 <= config.experiment_budget <= len(SCHEDULE)
            or record != _record(config.world.law, config.seed, config.experiment_budget)):
        raise ValidationError("Record Build a Universe alterato o incompatibile.")
    refined = parse_config({**config.to_dict(), "integration_step": config.integration_step / 2})
    try:
        for i, experiment in enumerate(record["schedule"], 1):
            points = simulate(config, experiment, i)
            reference = simulate(refined, experiment, i)
            if (any(abs(p[axis]) > 80 for p in points for axis in ("x", "y")) or
                    max(math.dist((p["x"], p["y"]), (q["x"], q["y"])) for p, q in zip(points, reference)) > 0.002):
                raise ValidationError("Mondo non sicuro o integrazione instabile nella schedule di controllo.")
        states = [tuple(p[key] for key in ("x", "y", "vx", "vy")) for p in record["probes"]]
        states += [(x, y, vx, vy) for x in (-18, 0, 18) for y in (-18, 0, 18)
                   for vx in (-8, 8) for vy in (-8, 8)]
        values = [acceleration_at(config.world, state) for state in states]
    except TrajectoryError:
        raise ValidationError("Mondo non valido nei controlli numerici.") from None
    if max(math.hypot(*pair) for pair in values) < 0.25:
        raise ValidationError("Legge degenere: segnale numerico insufficiente.")
    return {"heuristic_only": True, "checked_states": len(states),
            "checked_experiments": len(record["schedule"])}


def build_world(law_json, budget=3, seed=None):
    law = parse_law(law_json)
    seed = secrets.randbits(32) if seed is None else seed
    if type(seed) is not int or not 0 <= seed < 2**32 or type(budget) is not int or not 1 <= budget <= 4:
        raise ValidationError("Seed o budget del costruttore non valido.")
    record = _record(law, seed, budget)
    validate_built_world(record)
    return record


def validate_local_world(record):
    return validate_built_world(record) if "builder_version" in record else validate_generated_world(record)


def local_manifest(record):
    if "builder_version" not in record:
        return public_manifest(record)
    validate_built_world(record)
    return {"builder_version": BUILDER_VERSION, "world_id": record["world_id"],
            "sha256": record["sha256"], "level": record["level"],
            "experiment_budget": record["config"]["experiment_budget"],
            "probe_categories": {"interpolation": 3, "extrapolation": 3},
            "difficulty_notice": "Mondo costruito; validazione numerica euristica, identificabilità non garantita."}
