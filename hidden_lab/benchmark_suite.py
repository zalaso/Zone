"""Suite privata versionata; il manifest è l'unica proiezione pubblica."""

from collections import Counter
import copy
from hashlib import sha256
import json
import math
from pathlib import Path
import random
import secrets

from . import __version__
from .protocol import PROTOCOL_VERSION, ValidationError, identifier, require_keys, validate_experiment
from .simulator import TrajectoryError, acceleration_at, parse_config, simulate

BENCHMARK_VERSION = "0.3"
SUPPORTED_VERSIONS = ("0.1", "0.2", BENCHMARK_VERSION)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def digest(value):
    return sha256(canonical(value).encode("utf-8")).hexdigest()


def _experiment(x, y, vx, vy, duration=1.0):
    return {"initial_position": {"x": x, "y": y}, "initial_velocity": {"x": vx, "y": vy},
            "duration": duration, "observation_interval": 0.25}


SCHEDULE = (
    _experiment(0, 0, 3, 5),
    _experiment(2, 5, -4, 1),
    _experiment(-2, -4, 8, -6, 0.75),
    _experiment(4, -2, -7, 7, 0.75),
)

PROBE_STATES = (
    (31, 28, 2, 1), (42, -26, -3, 4), (35, 37, 9, -2),
    (-32, 44, -7, -6), (-44, -35, 0, 8), (48, -41, 13, 11),
)
INTERPOLATION_STATES = (
    (3.14159, -7.27183, 2.71828, -4.41421),
    (-11.31415, 8.1618, -5.70711, 3.22361),
    (14.1732, 12.4451, 6.6931, -8.2842),
    (-6.8191, -15.1326, -9.4332, 7.6671),
    (17.4142, -3.5355, 1.73205, 10.61803),
    (-13.5772, 16.2915, -3.23606, -11.6055),
)


def make_suite(seed=None, budget=3, version=BENCHMARK_VERSION):
    if version not in SUPPORTED_VERSIONS:
        raise ValidationError("Versione benchmark non valida.")
    if seed is None:
        seed = secrets.randbits(128)
    if type(seed) is not int or not 0 <= seed < 2**128:
        raise ValidationError("Il seed della suite deve essere un intero a 128 bit.")
    if type(budget) is not int or not 1 <= budget <= len(SCHEDULE):
        raise ValidationError("Budget suite fuori dai limiti.")
    rng = random.Random(seed)
    families = [family for family in ("constant", "height", "linear_drag", "quadratic_drag") for _ in range(2)]
    worlds = []
    states = (("interpolation", INTERPOLATION_STATES), ("extrapolation", PROBE_STATES)) if version != "0.1" else ((None, PROBE_STATES),)
    probes = []
    for category, group in states:
        for x, y, vx, vy in group:
            probe = {"probe_id": f"p{len(probes)+1:02d}", "x": x, "y": y, "vx": vx, "vy": vy}
            if category is not None:
                probe["category"] = category
            probes.append(probe)
    for index, family in enumerate(families):
        gravity = round(rng.uniform(5, 11), 4)
        coefficient = 0.0 if family == "constant" else round(
            rng.uniform(0.12, 0.38) if family == "height" else
            rng.uniform(0.08, 0.32) if family == "linear_drag" else rng.uniform(0.015, 0.055), 5)
        config = {"world": {"family": family, "gravity": gravity, "coefficient": coefficient},
                  "integration_step": 0.005, "noise_std": 0.0, "seed": rng.randrange(2**32),
                  "experiment_budget": budget}
        opaque = sha256(f"{seed}:world:{index}".encode()).hexdigest()[:16]
        worlds.append({"id": "w" + opaque, "config": config,
                       "passive_schedule": list(copy.deepcopy(SCHEDULE[:budget])),
                       "probes": copy.deepcopy(probes)})
    rng.shuffle(worlds)
    suite = {"suite_version": version, "simulator_version": __version__,
             "protocol_version": PROTOCOL_VERSION, "generator_seed": seed, "worlds": worlds}
    suite["sha256"] = digest(suite)
    validate_suite(suite)
    return suite


def validate_suite(suite):
    require_keys(suite, ("suite_version", "simulator_version", "protocol_version", "generator_seed", "worlds", "sha256"))
    if suite["suite_version"] not in SUPPORTED_VERSIONS or suite["simulator_version"] != __version__ or suite["protocol_version"] != PROTOCOL_VERSION:
        raise ValidationError("Versione della suite non compatibile con il codice corrente.")
    if type(suite["generator_seed"]) is not int or not 0 <= suite["generator_seed"] < 2**128:
        raise ValidationError("Seed suite non valido.")
    if not isinstance(suite["worlds"], list) or len(suite["worlds"]) < 8:
        raise ValidationError("La suite richiede almeno due casi per ciascuna famiglia.")
    if digest({key: value for key, value in suite.items() if key != "sha256"}) != suite["sha256"]:
        raise ValidationError("Hash SHA-256 della suite non valido.")
    ids, families, signatures = set(), Counter(), []
    common_schedule = common_probes = common_budget = None
    for item in suite["worlds"]:
        require_keys(item, ("id", "config", "passive_schedule", "probes"))
        world_id = identifier(item["id"])
        if world_id in ids:
            raise ValidationError("ID mondo duplicato.")
        ids.add(world_id)
        config = parse_config(item["config"])
        families[config.world.family] += 1
        if config.world.gravity <= 0 or (config.world.family != "constant" and config.world.coefficient <= 0):
            raise ValidationError("Mondo degenere.")
        schedule = item["passive_schedule"]
        if not isinstance(schedule, list) or len(schedule) != config.experiment_budget:
            raise ValidationError("Schedule passiva incompleta.")
        if common_schedule is None:
            common_schedule, common_budget = canonical(schedule), config.experiment_budget
        if canonical(schedule) != common_schedule or config.experiment_budget != common_budget:
            raise ValidationError("Budget o schedule non uniforme.")
        for index, experiment in enumerate(schedule, 1):
            validated = validate_experiment(experiment)
            if len(range(round(validated["duration"] / validated["observation_interval"]) + 1)) > 9:
                raise ValidationError("Schedule oltre il limite di campioni.")
            try:
                simulate(config, validated, index)
            except TrajectoryError:
                raise ValidationError("Schedule non valida su uno dei mondi.") from None
        probes = item["probes"]
        if not isinstance(probes, list) or len(probes) < 4:
            raise ValidationError("Probe insufficienti.")
        if common_probes is None:
            common_probes = canonical(probes)
        if canonical(probes) != common_probes:
            raise ValidationError("I mondi devono usare gli stessi probe nella v0.1.")
        probe_ids, signature, categories = set(), [], Counter()
        scheduled_states = {tuple(experiment[key][axis] for key in ("initial_position", "initial_velocity") for axis in ("x", "y")) for experiment in schedule}
        for probe in probes:
            required = ("probe_id", "x", "y", "vx", "vy") + (("category",) if suite["suite_version"] != "0.1" else ())
            require_keys(probe, required)
            pid = identifier(probe["probe_id"])
            if pid in probe_ids:
                raise ValidationError("Probe duplicato.")
            probe_ids.add(pid)
            state = tuple(probe[key] for key in ("x", "y", "vx", "vy"))
            if not all(type(value) in (int, float) and math.isfinite(value) for value in state):
                raise ValidationError("Stato di probe non finito.")
            if suite["suite_version"] != "0.1":
                category = probe["category"]
                if category not in ("interpolation", "extrapolation"):
                    raise ValidationError("Categoria probe non valida.")
                categories[category] += 1
                if category == "interpolation" and (any(abs(value) > 20 for value in state) or state in scheduled_states):
                    raise ValidationError("Probe interpolation fuori dominio o già osservato.")
                if category == "extrapolation" and all(abs(value) <= 20 for value in state):
                    raise ValidationError("Probe extrapolation nel dominio degli esperimenti.")
            elif abs(state[0]) <= 20 or abs(state[1]) <= 20:
                raise ValidationError("I probe v0.1 devono essere fuori dalle posizioni iniziali accessibili.")
            try:
                signature.extend(acceleration_at(config.world, state))
            except TrajectoryError:
                raise ValidationError("Probe fuori dal dominio fisico.") from None
        signatures.append((config.world.family, signature))
        if suite["suite_version"] != "0.1" and (not categories["interpolation"] or not categories["extrapolation"]):
            raise ValidationError("La suite richiede probe in entrambe le categorie.")
    if set(families) != {"constant", "height", "linear_drag", "quadratic_drag"} or min(families.values()) < 2:
        raise ValidationError("Le quattro famiglie richiedono almeno due casi ciascuna.")
    for i, (family, signature) in enumerate(signatures):
        for other_family, other in signatures[i + 1:]:
            distance = math.sqrt(sum((a-b)**2 for a, b in zip(signature, other)) / len(signature))
            if family != other_family and distance < 0.1:
                raise ValidationError("Famiglie non distinguibili sui probe della suite.")
            if family == other_family and distance < 1e-4:
                raise ValidationError("Configurazioni duplicate o quasi identiche nella stessa famiglia.")
    return suite


def manifest(suite):
    validate_suite(suite)
    first = suite["worlds"][0]
    return {"suite_version": suite["suite_version"], "simulator_version": suite["simulator_version"],
            "protocol_version": suite["protocol_version"], "sha256": suite["sha256"],
            "case_count": len(suite["worlds"]), "world_ids": [item["id"] for item in suite["worlds"]],
            "limits": {"experiment_budget": first["config"]["experiment_budget"],
                       "passive_experiments": len(first["passive_schedule"]),
                       "probe_count": len(first["probes"]), "max_observation_points": 9}}


def read_suite(path):
    return validate_suite(json.loads(Path(path).read_text(encoding="utf-8")))


def save_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
