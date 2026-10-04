"""Interprete matematico tipizzato: dati JSON validati, mai codice eseguibile."""

from dataclasses import dataclass
import json
import math

from .protocol import ValidationError, require_keys

MAX_NODES = 64
MAX_DEPTH = 12
MAX_ABS_VALUE = 1_000_000.0
DIVISION_FLOOR = 1e-6
VARIABLES = frozenset(("x", "y", "vx", "vy", "time"))
UNARY = frozenset(("abs", "sin", "cos", "tanh"))
BINARY = frozenset(("add", "sub", "mul", "div", "norm"))


@dataclass(frozen=True)
class Expression:
    op: str
    args: tuple["Expression", ...] = ()
    value: float | str | int | None = None

    def to_dict(self):
        if self.op == "const":
            return {"op": "const", "value": self.value}
        if self.op == "var":
            return {"op": "var", "name": self.value}
        result = {"op": self.op, "args": [arg.to_dict() for arg in self.args]}
        if self.op == "pow":
            result["exponent"] = self.value
        return result


@dataclass(frozen=True)
class AccelerationLaw:
    ax: Expression
    ay: Expression
    level: int

    def to_dict(self):
        return {"level": self.level, "ax": self.ax.to_dict(), "ay": self.ay.to_dict()}

    def canonical_json(self):
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False)


def _parse(raw, depth, counter, allow_time):
    if depth > MAX_DEPTH:
        raise ValidationError("AST troppo profondo.")
    counter[0] += 1
    if counter[0] > MAX_NODES or not isinstance(raw, dict):
        raise ValidationError("AST troppo grande o non valido.")
    op = raw.get("op")
    if op == "const":
        require_keys(raw, ("op", "value"))
        value = raw["value"]
        if type(value) not in (int, float) or abs(value) > 100 or not math.isfinite(value):
            raise ValidationError("Costante AST non valida.")
        return Expression("const", value=float(value))
    if op == "var":
        require_keys(raw, ("op", "name"))
        if type(raw["name"]) is not str or raw["name"] not in VARIABLES or (raw["name"] == "time" and not allow_time):
            raise ValidationError("Variabile AST non consentita.")
        return Expression("var", value=raw["name"])
    if type(op) is not str or op not in UNARY | BINARY | {"pow", "normalize"}:
        raise ValidationError("Operazione AST non consentita.")
    keys = ("op", "args", "exponent") if op == "pow" else ("op", "args")
    require_keys(raw, keys)
    arity = 3 if op == "normalize" else 2 if op in BINARY else 1
    args = raw["args"]
    if not isinstance(args, list) or len(args) != arity:
        raise ValidationError("Arità AST non valida.")
    exponent = None
    if op == "pow":
        exponent = raw["exponent"]
        if type(exponent) is not int or not 0 <= exponent <= 3:
            raise ValidationError("Esponente AST fuori limite.")
    return Expression(op, tuple(_parse(arg, depth + 1, counter, allow_time) for arg in args), exponent)


def parse_expression(raw, *, allow_time=False):
    return _parse(raw, 1, [0], allow_time)


def _variables(node):
    if node.op == "var":
        return {node.value}
    return set().union(*(_variables(arg) for arg in node.args)) if node.args else set()


def _validate_level(node, level, axis):
    if level == 1 and node.op != "const":
        raise ValidationError("Il livello 1 ammette solo accelerazioni costanti.")
    if level <= 4 and node.op in ("div", "abs", "pow", "sin", "cos", "tanh", "norm", "normalize"):
        raise ValidationError("Operazione non ammessa nel livello lineare.")
    if level <= 4 and node.op == "mul" and all(_variables(arg) for arg in node.args):
        raise ValidationError("Prodotto non lineare fuori livello.")
    if level <= 3:
        allowed = {"x", "vx"} if axis == "ax" else {"y", "vy"}
        if not _variables(node) <= allowed:
            raise ValidationError("Accoppiamento fra assi fuori livello.")
    for arg in node.args:
        _validate_level(arg, level, axis)


def parse_law(raw):
    require_keys(raw, ("level", "ax", "ay"))
    level = raw["level"]
    if type(level) is not int or not 1 <= level <= 5:
        raise ValidationError("Livello AST non supportato.")
    counter = [0]
    ax = _parse(raw["ax"], 1, counter, False)
    ay = _parse(raw["ay"], 1, counter, False)
    _validate_level(ax, level, "ax")
    _validate_level(ay, level, "ay")
    if level == 2 and len(_variables(ax) | _variables(ay)) > 1:
        raise ValidationError("Il livello 2 ammette una sola variabile.")
    return AccelerationLaw(ax, ay, level)


def _bounded(value):
    if not math.isfinite(value) or abs(value) > MAX_ABS_VALUE:
        raise ValidationError("Valore AST non finito o fuori limite.")
    return float(value)


def _eval(node, values):
    if node.op == "const":
        return float(node.value)
    if node.op == "var":
        return values[node.value]
    args = tuple(_eval(arg, values) for arg in node.args)
    try:
        if node.op == "add":
            result = args[0] + args[1]
        elif node.op == "sub":
            result = args[0] - args[1]
        elif node.op == "mul":
            result = args[0] * args[1]
        elif node.op == "div":
            divisor = math.copysign(max(abs(args[1]), DIVISION_FLOOR), args[1])
            result = args[0] / divisor
        elif node.op == "abs":
            result = abs(args[0])
        elif node.op == "pow":
            result = args[0] ** node.value
        elif node.op == "sin":
            result = math.sin(args[0])
        elif node.op == "cos":
            result = math.cos(args[0])
        elif node.op == "tanh":
            result = math.tanh(args[0])
        elif node.op == "norm":
            result = math.hypot(*args)
        elif node.op == "normalize":  # componente scalare divisa per norma protetta
            result = args[0] / max(math.hypot(args[1], args[2]), DIVISION_FLOOR)
        else:
            raise ValidationError("Operazione AST non consentita.")
    except (OverflowError, ValueError, ZeroDivisionError):
        raise ValidationError("Valore AST non calcolabile.") from None
    return _bounded(result)


def evaluate_expression(node, state, *, time=0.0):
    if not isinstance(node, Expression) or not isinstance(state, (tuple, list)) or len(state) != 4:
        raise ValidationError("Stato AST non valido.")
    if any(type(value) not in (int, float) or abs(value) > MAX_ABS_VALUE or not math.isfinite(value)
           for value in (*state, time)):
        raise ValidationError("Stato AST non finito o fuori limite.")
    values = dict(zip(("x", "y", "vx", "vy"), map(float, state)))
    values["time"] = float(time)
    return _bounded(_eval(node, values))


def evaluate_law(law, state):
    if not isinstance(law, AccelerationLaw):
        raise ValidationError("Legge AST non valida.")
    return evaluate_expression(law.ax, state), evaluate_expression(law.ay, state)


def expression_text(node):
    if node.op == "const":
        return f"{node.value:g}"
    if node.op == "var":
        return str(node.value)
    parts = [expression_text(arg) for arg in node.args]
    if node.op in ("add", "sub", "mul", "div"):
        symbol = {"add": "+", "sub": "-", "mul": "×", "div": "÷"}[node.op]
        return f"({parts[0]} {symbol} {parts[1]})"
    if node.op == "pow":
        return f"({parts[0]})^{node.value}"
    return f"{node.op}({', '.join(parts)})"
