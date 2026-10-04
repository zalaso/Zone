"""Grafici costruiti esclusivamente dal registro pubblico."""

import json
from pathlib import Path


def plot_trajectory(public_directory, request_id):
    # Nessuna lettura della configurazione privata.
    from .protocol import identifier
    identifier(request_id)
    public_directory = Path(public_directory)
    events = [json.loads(line)["message"]
              for line in (public_directory / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    observation = next((event for event in events if event["type"] == "observation"
                        and event["request_id"] == request_id), None)
    if observation is None or observation["status"] != "ok":
        raise ValueError("Nessuna traiettoria valida per questo esperimento.")
    prediction = next((event for event in events if event["type"] == "prediction"
                       and event["request_id"] == request_id), None)
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib import pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), layout="constrained")
    observed = observation["points"]
    axes[0].plot([p["x"] for p in observed], [p["y"] for p in observed], "o-", markersize=3, label="Osservata")
    axes[1].plot([p["t"] for p in observed], [p["y"] for p in observed], "o-", markersize=3, label="Osservata")
    if prediction:
        predicted = prediction["points"]
        axes[0].plot([p["x"] for p in predicted], [p["y"] for p in predicted], "--", label="Prevista prima della verifica")
        axes[1].plot([p["t"] for p in predicted], [p["y"] for p in predicted], "--", label="Prevista prima della verifica")
    axes[0].set(xlabel="x [m]", ylabel="y [m]", title="Traiettoria nello spazio")
    axes[0].set_aspect("equal", adjustable="datalim")
    axes[1].set(xlabel="t [s]", ylabel="y [m]", title="Posizione verticale nel tempo")
    for axis in axes:
        axis.grid(alpha=0.25)
        axis.legend(fontsize=8)
    fig.suptitle(f"Laboratorio · {request_id}")
    output = public_directory / f"trajectory_{request_id}.png"
    fig.savefig(output, dpi=160)
    plt.close(fig)
    return output
