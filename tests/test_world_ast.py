import json
import math
import unittest

from hidden_lab.protocol import ValidationError
from hidden_lab.world_ast import (evaluate_expression, evaluate_law, expression_text,
                                  parse_expression, parse_law)


def const(value):
    return {"op": "const", "value": value}


def var(name):
    return {"op": "var", "name": name}


def node(op, *args, **extra):
    return {"op": op, "args": list(args), **extra}


class WorldAstTests(unittest.TestCase):
    def test_constant_law_round_trip_is_canonical_and_deterministic(self):
        law = parse_law({"level": 1, "ay": const(-9.8), "ax": const(0)})
        self.assertEqual(evaluate_law(law, (1, 2, 3, 4)), (0, -9.8))
        self.assertEqual(law.canonical_json(), parse_law(json.loads(law.canonical_json())).canonical_json())
        self.assertEqual(law.canonical_json(), '{"ax":{"op":"const","value":0.0},"ay":{"op":"const","value":-9.8},"level":1}')

    def test_levels_one_to_five_enforce_structure_and_coupling(self):
        height = node("add", const(-9), node("mul", const(-0.2), var("y")))
        law2 = parse_law({"level": 2, "ax": const(0), "ay": height})
        self.assertAlmostEqual(evaluate_law(law2, (0, 5, 0, 0))[1], -10)
        with self.assertRaises(ValidationError):
            parse_law({"level": 1, "ax": const(0), "ay": height})
        linear = {"level": 3,
                  "ax": node("mul", const(-0.2), var("vx")),
                  "ay": node("add", const(-9), node("mul", const(-0.2), var("vy")))}
        self.assertAlmostEqual(evaluate_law(parse_law(linear), (0, 0, 5, -5))[0], -1)
        coupled = {"level": 4, "ax": node("mul", const(0.1), var("y")), "ay": const(-9)}
        self.assertAlmostEqual(evaluate_law(parse_law(coupled), (0, 5, 0, 0))[0], 0.5)
        with self.assertRaises(ValidationError):
            parse_law({**coupled, "level": 3})
        nonlinear = {"level": 5,
                     "ax": node("add", node("sin", var("x")), node("mul", var("vx"), var("vy"))),
                     "ay": node("sub", node("tanh", var("y")), node("pow", var("vx"), exponent=2))}
        ax, ay = evaluate_law(parse_law(nonlinear), (math.pi / 2, 0, 2, 3))
        self.assertAlmostEqual(ax, 7)
        self.assertAlmostEqual(ay, -4)
        with self.assertRaises(ValidationError):
            parse_law({**nonlinear, "level": 4})

    def test_protected_division_norm_and_normalization(self):
        division = parse_expression(node("div", const(1), const(0)))
        self.assertEqual(evaluate_expression(division, (0, 0, 0, 0)), 1_000_000)
        self.assertEqual(evaluate_expression(parse_expression(node("norm", const(3), const(4))),
                                             (0, 0, 0, 0)), 5)
        normalized = parse_expression(node("normalize", const(2), const(3), const(4)))
        self.assertAlmostEqual(evaluate_expression(normalized, (0, 0, 0, 0)), 0.4)
        self.assertIn("normalize", expression_text(normalized))
        self.assertEqual(evaluate_expression(parse_expression(node("abs", const(-3))), (0, 0, 0, 0)), 3)
        self.assertEqual(evaluate_expression(parse_expression(node("cos", const(0))), (0, 0, 0, 0)), 1)

    def test_time_is_gated_and_payloads_are_never_executed(self):
        with self.assertRaises(ValidationError):
            parse_law({"level": 5, "ax": var("time"), "ay": const(0)})
        self.assertEqual(evaluate_expression(parse_expression(var("time"), allow_time=True),
                                             (0, 0, 0, 0), time=2.5), 2.5)
        for invalid in ("__import__('os').system('echo bad')", "eval", "exec"):
            with self.assertRaises(ValidationError):
                parse_expression({"op": invalid, "args": []})
        for invalid in (const(True), const(float("nan")), const(10**1000),
                        {"op": "var", "name": ["x"]}, {"op": "const", "value": 1, "code": "x"},
                        node("pow", const(2), exponent=100), node("add", const(1))):
            with self.assertRaises(ValidationError):
                parse_expression(invalid)

    def test_complexity_and_output_bounds(self):
        deep = const(1)
        for _ in range(13):
            deep = node("abs", deep)
        with self.assertRaises(ValidationError):
            parse_expression(deep)
        wide = [const(1) for _ in range(65)]
        while len(wide) > 1:
            wide = [node("add", wide[index], wide[index + 1])
                    for index in range(0, len(wide) - 1, 2)] + (wide[-1:] if len(wide) % 2 else [])
        with self.assertRaises(ValidationError):
            parse_expression(wide[0])
        with self.assertRaises(ValidationError):
            evaluate_expression(parse_expression(node("div", const(2), const(0))), (0, 0, 0, 0))
        with self.assertRaises(ValidationError):
            evaluate_expression(parse_expression(var("x")), (float("inf"), 0, 0, 0))


if __name__ == "__main__":
    unittest.main()
