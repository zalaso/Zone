"""Codice riservato all'operatore. Integrazione RK4 e sorgente delle misure."""

from dataclasses import dataclass
import math
import random

from .protocol import ValidationError, number, observation_times, require_keys, validate_experiment
from .world_ast import AccelerationLaw, evaluate_law, parse_law


@dataclass(frozen=True)
class World:
    family: str
    gravity: float
    coefficient: float = 0.0
    law: AccelerationLaw | None = None


@dataclass(frozen=True)
class SimulationConfig:
    world: World
    integration_step: float
    noise_std: float
    seed: int
    experiment_budget: int

    def to_dict(self):
        world = ({"family": "ast", "law": self.world.law.to_dict()}
                 if self.world.family == "ast" else
                 {"family": self.world.family, "gravity": self.world.gravity,
                  "coefficient": self.world.coefficient})
        return {"world": world, "integration_step": self.integration_step,
                "noise_std": self.noise_std, "seed": self.seed,
                "experiment_budget": self.experiment_budget}


def parse_config(value):
    require_keys(value, ("world", "integration_step", "noise_std", "seed", "experiment_budget"))
    world = value["world"]
    if not isinstance(world, dict):
        raise ValidationError("Mondo privato non valido.")
    if world.get("family") == "ast":
        require_keys(world, ("family", "law"))
        parsed_world = World("ast", 0.0, 0.0, parse_law(world["law"]))
    else:
        require_keys(world, ("family", "gravity", "coefficient"))
        if world["family"] not in ("constant", "height", "linear_drag", "quadratic_drag"):
            raise ValidationError("Famiglia privata non valida.")
        gravity = number(world["gravity"], 0, 30)
        coefficient = number(world["coefficient"], 0, 2)
        if world["family"] == "constant" and coefficient != 0:
            raise ValidationError("La famiglia constant richiede coefficient=0.")
        parsed_world = World(world["family"], gravity, coefficient)
    if type(value["seed"]) is not int or not 0 <= value["seed"] <= 2**32 - 1:
        raise ValidationError("Seed non valido.")
    if type(value["experiment_budget"]) is not int or not 1 <= value["experiment_budget"] <= 100:
        raise ValidationError("Budget non valido.")
    return SimulationConfig(parsed_world,
                            number(value["integration_step"], 0.0001, 0.01),
                            number(value["noise_std"], 0, 1), value["seed"], value["experiment_budget"])


class TrajectoryError(Exception):
    """Nessun dettaglio della legge deve essere trasmesso con questo errore."""


def _check_state(state):
    x, y, vx, vy = state
    if (not all(math.isfinite(item) for item in state) or
            abs(x) > 100 or abs(y) > 100 or math.hypot(vx, vy) > 200):
        raise TrajectoryError()


def _derivative(world, state):
    _check_state(state)
    _, y, vx, vy = state
    if world.family == "ast":
        try:
            ax, ay = evaluate_law(world.law, state)
        except ValidationError:
            raise TrajectoryError() from None
        return vx, vy, ax, ay
    ax, ay = 0.0, -world.gravity
    if world.family == "height":
        ay -= world.coefficient * y
    elif world.family == "linear_drag":
        ax -= world.coefficient * vx
        ay -= world.coefficient * vy
    elif world.family == "quadratic_drag":
        speed = math.hypot(vx, vy)
        ax -= world.coefficient * speed * vx
        ay -= world.coefficient * speed * vy
    return vx, vy, ax, ay


def acceleration_at(world, state):
    """Verità privata per probe del benchmark; non esporre nel protocollo pubblico."""
    _, _, ax, ay = _derivative(world, state)
    return ax, ay


def _offset(state, derivative, scale):
    return tuple(a + scale * b for a, b in zip(state, derivative))


def _rk4(world, state, step):
    k1 = _derivative(world, state)
    k2 = _derivative(world, _offset(state, k1, step / 2))
    k3 = _derivative(world, _offset(state, k2, step / 2))
    k4 = _derivative(world, _offset(state, k3, step))
    result = tuple(a + step * (b + 2*c + 2*d + e) / 6
                   for a, b, c, d, e in zip(state, k1, k2, k3, k4))
    _check_state(result)
    return result


def simulate(config, experiment, experiment_index):
    experiment = validate_experiment(experiment)
    position, velocity = experiment["initial_position"], experiment["initial_velocity"]
    state = position["x"], position["y"], velocity["x"], velocity["y"]
    times = observation_times(experiment)
    # Il massimo passo è privato e indipendente dal campionamento richiesto.
    substeps = math.ceil(experiment["observation_interval"] / config.integration_step)
    step = experiment["duration"] / (len(times) - 1) / substeps
    rng = random.Random(config.seed + experiment_index)
    points = []
    for index, time in enumerate(times):
        if index:
            for _ in range(substeps):
                state = _rk4(config.world, state, step)
        _check_state(state)
        x, y = state[:2]
        if config.noise_std:
            x += rng.gauss(0, config.noise_std)
            y += rng.gauss(0, config.noise_std)
        points.append({"t": time, "x": x, "y": y})
    return points
