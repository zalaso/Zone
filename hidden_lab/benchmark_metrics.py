"""Metriche dei probe calcolabili dai soli file salvati del trial."""

import math

from .protocol import ValidationError


def _metrics(rows):
    squared = [row[0] for row in rows]
    magnitudes = [row[1] for row in rows]
    rmse = math.sqrt(sum(squared) / len(squared))
    truth_rms = math.sqrt(sum(magnitudes) / len(magnitudes))
    scale = max(1.0, truth_rms)
    return {"acceleration_rmse": rmse, "max_acceleration_error": math.sqrt(max(squared)),
            "normalized_error": rmse / scale, "normalization_scale": scale,
            "valid_probe_count": len(squared), "unit": "m/s²"}


def acceleration_metrics(predictions, truths):
    if len(predictions) != len(truths) or not predictions:
        raise ValidationError("Probe e previsioni incompatibili.")
    rows = []
    categorized = all("category" in truth for truth in truths)
    if any("category" in truth for truth in truths) and not categorized:
        raise ValidationError("Categorie probe incomplete.")
    for prediction, truth in zip(predictions, truths):
        if prediction["probe_id"] != truth["probe_id"]:
            raise ValidationError("Ordine dei probe incompatibile.")
        if categorized and truth["category"] not in ("interpolation", "extrapolation"):
            raise ValidationError("Categoria probe non valida.")
        rows.append(((prediction["ax"] - truth["ax"])**2 + (prediction["ay"] - truth["ay"])**2,
                     truth["ax"]**2 + truth["ay"]**2, truth.get("category")))
    result = _metrics(rows)
    if categorized:
        result["by_category"] = {category: _metrics(group) if group else None
            for category in ("interpolation", "extrapolation")
            for group in [[row for row in rows if row[2] == category]]}
    return result
