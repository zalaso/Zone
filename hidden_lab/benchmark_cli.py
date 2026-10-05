"""Comandi offline-first per suite, trial singolo, aggregazione e report."""

import json
import os
from pathlib import Path
import sys

from .benchmark_fake import BenchmarkFixtureClient
from .benchmark_baselines import BASELINES, BaselineClient, baseline_seed
from .benchmark_report import aggregate_trials, render_report
from .benchmark_suite import make_suite, manifest, read_suite, save_new
from .benchmark_trial import BenchmarkTrial, CONDITIONS
from .protocol import ValidationError
from .provider_base import AgentSettings, ProviderError
from .provider_factory import create_real_client
from .simulator import parse_config

MODEL_ENV = {"openai": "OPENAI_MODEL", "anthropic": "ANTHROPIC_MODEL",
             "gemini": "GEMINI_MODEL", "ollama": "OLLAMA_MODEL"}


def add_parser(commands):
    root = commands.add_parser("benchmark", help="Zone Benchmark v0.3: un trial per comando")
    sub = root.add_subparsers(dest="benchmark_command", required=True)
    prepare = sub.add_parser("prepare", help="Genera suite privata e manifest pubblico")
    prepare.add_argument("--private", required=True, type=Path)
    prepare.add_argument("--manifest", required=True, type=Path)
    prepare.add_argument("--seed", type=int)
    prepare.add_argument("--budget", type=int, default=3)
    prepare.add_argument("--suite-version", choices=("0.1", "0.2", "0.3"), default="0.3")
    check = sub.add_parser("check", help="Valida suite, schedule e hash senza modelli")
    check.add_argument("--private", required=True, type=Path)
    check.add_argument("--manifest", type=Path)
    trial = sub.add_parser("trial", help="Esegue un solo mondo, condizione e ripetizione")
    trial.add_argument("--suite", required=True, type=Path)
    trial.add_argument("--integrity-pack", type=Path, help="Pacchetto privato v1; verifica split e registra provenienza")
    trial.add_argument("--world", required=True)
    trial.add_argument("--condition", required=True, choices=CONDITIONS)
    trial.add_argument("--provider", required=True, choices=(*MODEL_ENV, "simulated", "baseline"))
    trial.add_argument("--baseline", choices=BASELINES, help="Solo --provider baseline: policy o stimatore offline")
    trial.add_argument("--model")
    trial.add_argument("--repeat", type=int, default=0)
    trial.add_argument("--trial-seed", type=int, default=0)
    trial.add_argument("--out", required=True, type=Path)
    trial.add_argument("--max-calls", type=int, default=20)
    trial.add_argument("--max-turns", type=int, default=15)
    trial.add_argument("--max-corrections", type=int, default=2)
    trial.add_argument("--timeout", type=float, default=30)
    trial.add_argument("--max-output-tokens", type=int, default=2500)
    trial.add_argument("--max-input-bytes", type=int, default=200000)
    trial.add_argument("--simulated-scenario", choices=("correct", "wrong", "insufficient", "malformed", "budget", "provider_error"), default="correct")
    trial.add_argument("--yes", action="store_true", help="Solo client offline: avvio non interattivo")
    trial.add_argument("--contaminated", action="store_true", help="Marca intervento umano nel trial")
    aggregate = sub.add_parser("aggregate", help="Aggrega risultati già salvati, senza simulazioni")
    aggregate.add_argument("--runs", required=True, type=Path)
    aggregate.add_argument("--out", required=True, type=Path)
    aggregate.add_argument("--include-contaminated", action="store_true")
    report = sub.add_parser("report", help="Rigenera report leggibile da risultati salvati")
    source = report.add_mutually_exclusive_group(required=True)
    source.add_argument("--runs", type=Path)
    source.add_argument("--aggregate", type=Path)
    report.add_argument("--out", required=True, type=Path)
    report.add_argument("--include-contaminated", action="store_true")


def run_command(args):
    command = args.benchmark_command
    if command == "prepare":
        if args.private.resolve() == args.manifest.resolve() or args.private.exists() or args.manifest.exists():
            raise ValidationError("Scegli due nuovi percorsi distinti per suite e manifest.")
        suite = make_suite(args.seed, args.budget, args.suite_version)
        save_new(args.private, suite)
        save_new(args.manifest, manifest(suite))
        print(f"Suite privata creata: {len(suite['worlds'])} mondi; SHA-256 {suite['sha256']}. Manifest: {args.manifest}")
        return 0
    if command == "check":
        suite = read_suite(args.private)
        public = manifest(suite)
        if args.manifest is not None and json.loads(args.manifest.read_text(encoding="utf-8")) != public:
            raise ValidationError("Manifest non corrispondente alla suite privata.")
        print(f"Suite valida: {public['case_count']} mondi, {public['limits']['passive_experiments']} lanci passivi per mondo; SHA-256 {suite['sha256']}.")
        return 0
    if command == "aggregate":
        data = aggregate_trials(args.runs, args.include_contaminated)
        save_new(args.out, data)
        print(f"Aggregati {data['included_count']} trial; contaminati esclusi: {data['excluded_contaminated']}.")
        return 0
    if command == "report":
        data = (aggregate_trials(args.runs, args.include_contaminated) if args.runs is not None else
                json.loads(args.aggregate.read_text(encoding="utf-8")))
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("x", encoding="utf-8") as stream:
            stream.write(render_report(data))
        print(f"Report creato: {args.out}")
        return 0
    if command != "trial":
        raise ValidationError("Comando benchmark non valido.")
    suite = read_suite(args.suite)
    integrity = None
    if getattr(args, "integrity_pack", None) is not None:
        from .integrity_suite import benchmark_binding, read_pack
        integrity = benchmark_binding(read_pack(args.integrity_pack), suite, args.world)
    worlds = [item for item in suite["worlds"] if item["id"] == args.world]
    if len(worlds) != 1:
        raise ValidationError("ID mondo non presente nella suite.")
    if args.out.exists():
        raise ValidationError("La cartella del trial esiste già: non si riprendono trial parziali.")
    if args.provider not in ("simulated", "baseline") and args.yes:
        raise ValidationError("--yes è riservato ai client offline: per un provider reale digita avvia.")
    if args.provider != "simulated" and args.simulated_scenario != "correct":
        raise ValidationError("--simulated-scenario richiede --provider simulated.")
    if (args.provider == "baseline") != (args.baseline is not None):
        raise ValidationError("--provider baseline richiede --baseline; gli altri provider non lo accettano.")
    if args.provider == "baseline" and args.model is not None:
        raise ValidationError("La baseline fissa il proprio ID modello; non usare --model.")
    if args.provider == "baseline" and ((args.baseline == "random_policy" and args.condition != "active") or
                                        (args.baseline == "affine_estimator" and args.condition != "passive_sequential")):
        raise ValidationError("random_policy richiede active; affine_estimator richiede passive_sequential.")
    model = ("benchmark-fixture-v1" if args.provider == "simulated" else args.baseline
             if args.provider == "baseline" else (args.model or os.environ.get(MODEL_ENV[args.provider], "")))
    settings = AgentSettings(model=model, max_calls=args.max_calls, max_turns=args.max_turns,
                             max_corrections=args.max_corrections, timeout=args.timeout,
                             max_output_tokens=args.max_output_tokens, max_input_bytes=args.max_input_bytes)
    budget = worlds[0]["config"]["experiment_budget"]
    cost = "nessun costo API: client offline" if args.provider in ("simulated", "baseline") else (
           "modello locale; nessun download automatico" if args.provider == "ollama" else
           "chiamate API potenzialmente a pagamento")
    print(f"Trial: provider={args.provider}; modello={settings.model}; mondo={args.world}; condizione={args.condition}; "
          f"ripetizione={args.repeat}; max chiamate={settings.max_calls}; max turni={settings.max_turns}; "
          f"max esperimenti simulati={budget}; {cost}.")
    if not args.yes:
        try:
            answer = input("Confermi questo trial? Digita avvia: ").strip()
        except EOFError:
            return 2
        if answer != "avvia":
            print("Trial non avviato; nessuna chiamata al modello.")
            return 2
    config = parse_config(worlds[0]["config"])
    if args.provider == "simulated":
        client = BenchmarkFixtureClient(config.world, args.simulated_scenario)
    elif args.provider == "baseline":
        client = BaselineClient(args.baseline, baseline_seed(suite["sha256"], args.world, args.repeat, args.trial_seed))
    else:
        client = create_real_client(args.provider, settings)
    try:
        if args.provider == "ollama":
            try:
                client.preflight(settings.model)
            except ProviderError as exc:
                print(f"Errore locale Ollama ({exc.code}); nessun modello scaricato.", file=sys.stderr)
                return 2
        trial = BenchmarkTrial(args.out, suite, args.world, args.condition, client, settings,
                               repetition=args.repeat, trial_seed=args.trial_seed,
                               contaminated=args.contaminated, integrity=integrity)
        result = trial.run()
        print(f"Trial {result['status']}: {result['executed_experiments']} esperimenti, "
              f"{result['model_calls']} chiamate, {result['invalid_responses']} risposte non valide. "
              f"Risultato: {args.out / 'result.json'}")
        return 0 if result["status"] in ("completed", "insufficient") else 2
    finally:
        client.close()
