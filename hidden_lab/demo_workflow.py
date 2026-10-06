"""Percorso locale ripetibile: demo dichiarata, fixture oracolo, backup e restore."""

from pathlib import Path
import json

from .protocol import ValidationError


def run_demo(destination):
    from .cli import main
    destination = Path(destination)
    if destination.exists():
        raise ValidationError("La demo richiede una cartella nuova.")
    destination.mkdir(parents=True, exist_ok=False)
    forge, benchmark = destination / "forge", destination / "benchmark"
    def command(*args):
        result = main([str(arg) for arg in args])
        if result:
            raise ValidationError("Demo arrestata; conservare la cartella per la diagnosi e ripartire su un percorso nuovo.")
    command("integrity", "prepare", "--out", forge, "--kind", "forge", "--levels", 1, "--seed", 900610, "--budget", 3)
    command("integrity", "check", "--pack", forge)
    public = json.loads((forge / "public" / "manifest.json").read_text(encoding="utf-8"))
    db, proof = destination / "arena.sqlite3", forge / "public" / "demo-reveal.json"
    command("arena", "demo", "--db", db, "--integrity-pack", forge / "private" / "pack.json", "--proof-out", proof)
    command("integrity", "verify-reveal", "--manifest", forge / "public" / "manifest.json", "--proof", proof,
            "--expected-manifest-hash", public["sha256"])
    command("integrity", "prepare", "--out", benchmark, "--kind", "benchmark", "--seed", 810456, "--budget", 1)
    command("integrity", "check", "--pack", benchmark)
    suite = json.loads((benchmark / "private" / "test.json").read_text(encoding="utf-8"))
    for condition in ("prior_only", "passive_fixed", "passive_sequential", "active"):
        command("benchmark", "trial", "--suite", benchmark / "private" / "test.json", "--integrity-pack", benchmark / "private" / "pack.json",
                "--world", suite["worlds"][0]["id"], "--condition", condition, "--provider", "simulated", "--yes", "--out", benchmark / "runs" / condition)
    command("benchmark", "aggregate", "--runs", benchmark / "runs", "--out", benchmark / "aggregate.json")
    command("benchmark", "report", "--aggregate", benchmark / "aggregate.json", "--out", benchmark / "report.md")
    backup = destination / "backup.sqlite3"
    command("ops", "backup", "--db", db, "--out", backup)
    command("ops", "restore", "--backup", backup, "--out", destination / "restored.sqlite3")
    command("ops", "check", "--db", destination / "restored.sqlite3")
    command("ops", "retention", "--db", db)
    print("Demo completa: baseline e fixture offline, seed noti; nessun LLM, nessuna pubblicazione.")
    return 0
