"""La metrica predittiva usa solo misure pubbliche, mai la legge vera."""

import math


def compare_positions(predicted, observed):
    if len(predicted) != len(observed) or not predicted:
        raise ValueError("Griglie incompatibili.")
    if any(not math.isclose(a["t"], b["t"], rel_tol=0, abs_tol=1e-9)
           for a, b in zip(predicted, observed)):
        raise ValueError("Griglie incompatibili.")
    errors = [math.hypot(a["x"] - b["x"], a["y"] - b["y"])
              for a, b in zip(predicted, observed)]
    return {"position_rmse": math.sqrt(sum(error**2 for error in errors) / len(errors)),
            "max_position_error": max(errors), "point_count": len(errors), "unit": "m",
            "law_identification": "not_assessed"}
