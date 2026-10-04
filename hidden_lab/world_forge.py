"""World Forge v1: mondi AST privati, riproducibili e filtrati prima dell'uso."""

from dataclasses import dataclass
import copy
from hashlib import sha256
import json
import math
from pathlib import Path
import random
import secrets

from .protocol import ValidationError, decode, require_keys, validate_experiment
from .simulator import TrajectoryError, acceleration_at, parse_config, simulate
from .world_ast import parse_law

FORGE_VERSION = "1"
MAX_ATTEMPTS = 16


@dataclass(frozen=True)
class LevelSpec:
    level: int
    name: str
    state_inputs: tuple[str, ...]
    required_validation: tuple[str, ...]
    implemented: bool


LEVEL_SPECS = {
    1: LevelSpec(1, "constant", ("x", "y", "vx", "vy"), ("nonzero_acceleration",), True),
    2: LevelSpec(2, "one_variable", ("x", "y", "vx", "vy"), ("variable_sensitivity",), True),
    3: LevelSpec(3, "additive", ("x", "y", "vx", "vy"), ("two_axis_sensitivity",), True),
    4: LevelSpec(4, "coupled", ("x", "y", "vx", "vy"), ("cross_axis_sensitivity",), True),
    5: LevelSpec(5, "nonlinear", ("x", "y", "vx", "vy"), ("nonlinear_curvature",), True),
    6: LevelSpec(6, "regions", ("x", "y", "vx", "vy"), ("boundary_continuity", "region_coverage"), False),
    7: LevelSpec(7, "latent", ("x", "y", "vx", "vy", "latent"), ("latent_identifiability",), False),
    8: LevelSpec(8, "memory", ("x", "y", "vx", "vy", "memory"), ("history_replay",), False),
    9: LevelSpec(9, "nonstationary", ("x", "y", "vx", "vy", "time"), ("time_replay",), False),
}


def level_spec(level):
    if type(level) is not int or level not in LEVEL_SPECS:
        raise ValidationError("Livello World Forge non valido.")
    return LEVEL_SPECS[level]


def _const(value):
    return {"op": "const", "value": round(value, 6)}


def _var(name):
    return {"op": "var", "name": name}


def _node(op, *args):
    return {"op": op, "args": list(args)}


def _term(coefficient, variable):
    return _node("mul", _const(coefficient), _var(variable))


def _experiment(x, y, vx, vy, duration=1.0):
    return {"initial_position": {"x": x, "y": y},
            "initial_velocity": {"x": vx, "y": vy},
            "duration": duration, "observation_interval": 0.25}


SCHEDULE = (
    _experiment(0, 0, 3, 5), _experiment(2, 5, -4, 1),
    _experiment(-2, -4, 8, -6, 0.75), _experiment(4, -2, -7, 7, 0.75),
)
PROBE_STATES = (
    ("interpolation", 3.125, -7.25, 2.75, -4.5),
    ("interpolation", -11.25, 8.125, -5.75, 3.25),
    ("interpolation", 14.25, 12.375, 6.75, -8.25),
    ("extrapolation", 31, 28, 2, 1),
    ("extrapolation", 42, -26, -3, 4),
    ("extrapolation", -32, 44, -7, -6),
)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _digest(value):
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _parameters(seed, level, attempt):
    key = sha256(f"zone-forge:{FORGE_VERSION}:{seed}:{level}:{attempt}".encode()).digest()
    rng = random.Random(int.from_bytes(key, "big"))
    return (round(rng.uniform(6.5, 9.5), 4),
            round(rng.uniform(0.17, 0.31), 5),
            round(rng.uniform(0.15, 0.28), 5),
            round(rng.uniform(0.09, 0.17), 5),
            round(rng.uniform(0.018, 0.032), 5), rng.randrange(2**32))


def _laws(level, gravity, height, drag, coupling, quadratic):
    zero, down = _const(0), _const(-gravity)
    if level == 1:
        law = {"level": 1, "ax": _const(0.5), "ay": down}
        simpler = {"level": 1, "ax": zero, "ay": zero}
        alternative = {"level": 1, "ax": _const(0.5), "ay": _const(-gravity - 0.6)}
    elif level == 2:
        law = {"level": 2, "ax": zero, "ay": _node("add", down, _term(-height, "y"))}
        simpler = {"level": 1, "ax": zero, "ay": down}
        alternative = {"level": 2, "ax": zero,
                       "ay": _node("add", down, _term(-round(height * 0.7, 6), "y"))}
    elif level == 3:
        law = {"level": 3, "ax": _term(-drag, "vx"),
               "ay": _node("add", down, _term(-drag, "vy"))}
        simpler = {"level": 1, "ax": zero, "ay": down}
        alternative = {"level": 3, "ax": _term(-round(drag * 0.7, 6), "vx"),
                       "ay": _node("add", down, _term(-round(drag * 0.7, 6), "vy"))}
    elif level == 4:
        law = {"level": 4,
               "ax": _node("add", _term(-drag, "vx"), _term(coupling, "y")),
               "ay": _node("add", _node("add", down, _term(-drag, "vy")), _term(-coupling, "x"))}
        simpler = {"level": 3, "ax": _term(-drag, "vx"),
                   "ay": _node("add", down, _term(-drag, "vy"))}
        alternative = {"level": 4,
                       "ax": _node("add", _term(-drag, "vx"), _term(round(coupling * 0.7, 6), "y")),
                       "ay": _node("add", _node("add", down, _term(-drag, "vy")),
                                   _term(-round(coupling * 0.7, 6), "x"))}
    else:
        speed = _node("norm", _var("vx"), _var("vy"))
        ax_drag = _node("mul", _const(-quadratic), _node("mul", speed, _var("vx")))
        ay_drag = _node("mul", _const(-quadratic), _node("mul", speed, _var("vy")))
        law = {"level": 5, "ax": ax_drag, "ay": _node("add", down, ay_drag)}
        linearized = round(quadratic * 5, 6)
        simpler = {"level": 3, "ax": _term(-linearized, "vx"),
                   "ay": _node("add", down, _term(-linearized, "vy"))}
        weaker = _const(-round(quadratic * 0.7, 6))
        alternative = {"level": 5,
                       "ax": _node("mul", weaker, _node("mul", speed, _var("vx"))),
                       "ay": _node("add", down,
                                   _node("mul", weaker, _node("mul", speed, _var("vy"))))}
    return parse_law(law), parse_law(simpler), parse_law(alternative)


def _candidate(seed, level, attempt, budget):
    gravity, height, drag, coupling, quadratic, physical_seed = _parameters(seed, level, attempt)
    law, simpler, alternative = _laws(level, gravity, height, drag, coupling, quadratic)
    config = {"world": {"family": "ast", "law": law.to_dict()},
              "integration_step": 0.005, "noise_std": 0.0,
              "seed": physical_seed, "experiment_budget": budget}
    probes = [{"probe_id": f"p{index:02d}", "category": category,
               "x": x, "y": y, "vx": vx, "vy": vy}
              for index, (category, x, y, vx, vy) in enumerate(PROBE_STATES, 1)]
    record = {"forge_version": FORGE_VERSION, "generator_seed": seed,
              "level": level, "attempt": attempt, "world_id": "w" +
              sha256(f"{FORGE_VERSION}:{seed}:{level}:{attempt}".encode()).hexdigest()[:16],
              "config": config, "schedule": copy.deepcopy(list(SCHEDULE[:budget])), "probes": probes}
    record["sha256"] = _digest(record)
    return record, simpler, alternative


def _signature(world, states):
    return [acceleration_at(world, state) for state in states]


def _rms_distance(left, right):
    return math.sqrt(sum((ax - bx)**2 + (ay - by)**2
                         for (ax, ay), (bx, by) in zip(left, right)) / len(left))


def _level_signal(level, world):
    base = acceleration_at(world, (0, 0, 0, 0))
    if level == 1:
        return math.hypot(*base)
    if level == 2:
        return math.dist(acceleration_at(world, (0, 8, 0, 0)),
                         acceleration_at(world, (0, -8, 0, 0)))
    if level == 3:
        return min(abs(acceleration_at(world, (0, 0, 8, 0))[0] - base[0]),
                   abs(acceleration_at(world, (0, 0, 0, 8))[1] - base[1]))
    if level == 4:
        return max(abs(acceleration_at(world, (0, 8, 0, 0))[0] - base[0]),
                   abs(acceleration_at(world, (8, 0, 0, 0))[1] - base[1]))
    plus = acceleration_at(world, (0, 0, 8, 0))[0]
    minus = acceleration_at(world, (0, 0, -8, 0))[0]
    # La curvatura di una legge dispari è rilevata a velocità non simmetriche.
    middle = acceleration_at(world, (0, 0, 4, 0))[0]
    return max(abs(plus - 2 * middle + base[0]), abs(minus + plus - 2 * base[0]))


def _complexity(law):
    def dimensions(node):
        children = [dimensions(arg) for arg in node.args]
        return 1 + sum(count for count, _ in children), 1 + max((depth for _, depth in children), default=0)
    left, right = dimensions(law.ax), dimensions(law.ay)
    return {"nodes": left[0] + right[0], "depth": max(left[1], right[1])}


def _probe_state(probe):
    return tuple(probe[key] for key in ("x", "y", "vx", "vy"))


def validate_generated_world(record):
    """Ricalcola la proposta dal seed e testa sicurezza, osservabilità e distinzione."""
    require_keys(record, ("forge_version", "generator_seed", "level", "attempt", "world_id",
                          "config", "schedule", "probes", "sha256"))
    if record["forge_version"] != FORGE_VERSION:
        raise ValidationError("Versione World Forge incompatibile.")
    seed, level, attempt = record["generator_seed"], record["level"], record["attempt"]
    spec = level_spec(level)
    if not spec.implemented:
        raise ValidationError("Livello World Forge non ancora implementato.")
    if type(seed) is not int or not 0 <= seed < 2**128 or type(attempt) is not int or not 0 <= attempt < MAX_ATTEMPTS:
        raise ValidationError("Seed o tentativo World Forge non valido.")
    config = parse_config(record["config"])
    budget = config.experiment_budget
    if not 1 <= budget <= len(SCHEDULE) or config.world.family != "ast" or config.world.law.level != level:
        raise ValidationError("Configurazione World Forge incoerente.")
    expected, simpler_law, alternative_law = _candidate(seed, level, attempt, budget)
    if record != expected or record["sha256"] != _digest({key: value for key, value in record.items() if key != "sha256"}):
        raise ValidationError("Mondo non riproducibile dal seed o modificato.")
    world = config.world
    simpler = parse_config({**config.to_dict(), "world": {"family": "ast", "law": simpler_law.to_dict()}})
    alternative = parse_config({**config.to_dict(), "world": {"family": "ast", "law": alternative_law.to_dict()}})
    trajectories, reference_trajectories, alternative_trajectories = [], [], []
    for index, experiment in enumerate(record["schedule"], 1):
        validate_experiment(experiment)
        try:
            points = simulate(config, experiment, index)
            reference = simulate(simpler, experiment, index)
            alternate = simulate(alternative, experiment, index)
            refined = simulate(parse_config({**config.to_dict(), "integration_step": config.integration_step / 2}),
                               experiment, index)
        except TrajectoryError:
            raise ValidationError("Traiettoria World Forge non sicura.") from None
        if max(math.dist((p["x"], p["y"]), (q["x"], q["y"])) for p, q in zip(points, refined)) > 0.002:
            raise ValidationError("Integrazione World Forge instabile al dimezzamento del passo.")
        if any(abs(p[axis]) > 80 for p in points for axis in ("x", "y")):
            raise ValidationError("Traiettoria troppo vicina al limite fisico.")
        trajectories.append(points)
        reference_trajectories.append(reference)
        alternative_trajectories.append(alternate)
    scheduled = {tuple(experiment[key][axis] for key in ("initial_position", "initial_velocity")
                       for axis in ("x", "y")) for experiment in record["schedule"]}
    categories = set()
    for probe in record["probes"]:
        state = _probe_state(probe)
        category = probe["category"]
        categories.add(category)
        if (category == "interpolation" and (max(map(abs, state)) > 20 or state in scheduled) or
                category == "extrapolation" and max(map(abs, state)) <= 20):
            raise ValidationError("Probe World Forge nella categoria errata.")
        try:
            acceleration_at(world, state)
        except TrajectoryError:
            raise ValidationError("Probe World Forge fuori dominio.") from None
    if categories != {"interpolation", "extrapolation"}:
        raise ValidationError("Categorie probe World Forge incomplete.")
    states = [_probe_state(probe) for probe in record["probes"]]
    signature = _signature(world, states)
    reference_signature = _signature(simpler.world, states)
    alternative_signature = _signature(alternative.world, states)
    if not all(math.isfinite(value) for pair in signature for value in pair):
        raise ValidationError("Accelerazione World Forge non finita.")
    signal = _level_signal(level, world)
    separation = _rms_distance(signature, reference_signature)
    alternative_separation = _rms_distance(signature, alternative_signature)
    if signal < 0.25 or separation < 0.25 or alternative_separation < 0.15:
        raise ValidationError("Legge degenere o troppo simile alle alternative.")
    observation_separations = [math.sqrt(sum((p["x"] - q["x"])**2 + (p["y"] - q["y"])**2
                                             for p, q in zip(points, reference)) / len(points))
                               for points, reference in zip(trajectories, reference_trajectories)]
    alternative_observation_separations = [math.sqrt(sum((p["x"] - q["x"])**2 + (p["y"] - q["y"])**2
                                for p, q in zip(points, alternate)) / len(points))
                                for points, alternate in zip(trajectories, alternative_trajectories)]
    informative = [index for index, (simple, alternate) in enumerate(zip(
        observation_separations, alternative_observation_separations), 1)
        if min(simple, alternate) >= 0.04]
    if not informative:
        raise ValidationError("Nessun esperimento informativo nella schedule.")
    interpolation = [state for probe, state in zip(record["probes"], states)
                     if probe["category"] == "interpolation"]
    extrapolation = [state for probe, state in zip(record["probes"], states)
                     if probe["category"] == "extrapolation"]
    difficulty = {"heuristic_only": True, "structural_complexity": _complexity(world.law),
                  "level_signal": round(signal, 6),
                  "sensitivity_observation_rmse": round(max(observation_separations), 6),
                  "distance_from_simpler_probe_rmse": round(separation, 6),
                  "nearest_alternative_probe_rmse": round(alternative_separation, 6),
                  "informative_experiments": informative,
                  "experiments_until_first_informative": informative[0],
                  "nearest_alternative_observation_rmse": round(max(alternative_observation_separations), 6),
                  "interpolation_separation_rmse": round(_rms_distance(_signature(world, interpolation),
                    _signature(simpler.world, interpolation)), 6),
                  "extrapolation_separation_rmse": round(_rms_distance(_signature(world, extrapolation),
                    _signature(simpler.world, extrapolation)), 6)}
    return difficulty


def generate_world(seed, level, budget=3):
    if seed is None:
        seed = secrets.randbits(128)
    if type(seed) is not int or not 0 <= seed < 2**128:
        raise ValidationError("Seed World Forge non valido.")
    spec = level_spec(level)
    if not spec.implemented:
        raise ValidationError("Livello World Forge non ancora implementato.")
    if type(budget) is not int or not 1 <= budget <= len(SCHEDULE):
        raise ValidationError("Budget World Forge non valido.")
    for attempt in range(MAX_ATTEMPTS):
        record, _, _ = _candidate(seed, level, attempt, budget)
        try:
            validate_generated_world(record)
        except ValidationError:
            continue
        return record
    raise ValidationError("Nessun mondo valido nei tentativi World Forge consentiti.")


def public_manifest(record):
    validate_generated_world(record)
    return {"forge_version": FORGE_VERSION, "world_id": record["world_id"],
            "sha256": record["sha256"], "level": record["level"],
            "experiment_budget": record["config"]["experiment_budget"],
            "probe_categories": {category: sum(probe["category"] == category for probe in record["probes"])
                                 for category in ("interpolation", "extrapolation")},
            "difficulty_notice": "Livello di generazione; la difficoltà empirica resta una stima privata."}


def read_world(path):
    record = decode(Path(path).read_text(encoding="utf-8"))
    validate_generated_world(record)
    return record
