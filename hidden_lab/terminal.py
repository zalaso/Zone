"""Interfaccia testuale per la persona; nessun JSON necessario per decidere."""

import copy

from .protocol import ValidationError, observation_times, text, validate_experiment


class OperatorStop(Exception):
    pass


class Terminal:
    def __init__(self, read=input, write=print):
        self.read = read
        self.write = write

    def show(self, value):
        # Il testo del modello è solo testo: neutralizza i controlli del terminale.
        self.write("".join(c if c.isprintable() or c in "\n\t" else "?" for c in str(value)))

    def ask(self, prompt):
        try:
            value = self.read(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            raise OperatorStop() from None
        if value.lower() == "esci":
            raise OperatorStop()
        return value

    def choose(self, prompt, options):
        while True:
            value = self.ask(prompt).lower()
            if value in options:
                return value
            self.show("Scegli esplicitamente una delle opzioni. Invio vuoto non autorizza nulla; 'esci' termina.")

    def answer_text(self, prompt):
        while True:
            value = self.ask(prompt)
            try:
                return text(value)
            except ValidationError as exc:
                self.show(exc)

    def experiment(self, settings):
        p, v = settings["initial_position"], settings["initial_velocity"]
        self.show(f"Posizione iniziale: ({p['x']:g}, {p['y']:g}) m; velocità: ({v['x']:g}, {v['y']:g}) m/s")
        self.show(f"Durata: {settings['duration']:g} s; intervallo misure: {settings['observation_interval']:g} s")
        self.show("Tempi [s]: " + ", ".join(f"{t:g}" for t in observation_times(settings)))

    def modify(self, original, max_points):
        while True:
            settings = copy.deepcopy(original)
            try:
                for group, axis, label in (("initial_position", "x", "x iniziale [m]"),
                                          ("initial_position", "y", "y iniziale [m]"),
                                          ("initial_velocity", "x", "vx iniziale [m/s]"),
                                          ("initial_velocity", "y", "vy iniziale [m/s]"),
                                          (None, "duration", "Durata [s]"),
                                          (None, "observation_interval", "Intervallo misure [s]")):
                    target = settings[group] if group else settings
                    value = self.ask(f"{label} [{target[axis]:g}] (Invio conserva il valore): ")
                    if value:
                        target[axis] = float(value.replace(",", "."))
                settings = validate_experiment(settings)
                if len(observation_times(settings)) > max_points:
                    raise ValidationError(f"Usa al massimo {max_points} punti di osservazione.")
                self.experiment(settings)
                self.choose("Confermi questi parametri? [conferma/esci]: ", ("conferma",))
                return settings
            except (ValueError, OverflowError):
                self.show("Parametri non validi: rispetta i limiti dell'apparato, pochi punti e una durata multipla dell'intervallo.")

    def points(self, points, label):
        self.show(label)
        self.show("      t [s]          x [m]          y [m]")
        for point in points:
            self.show(f"{point['t']:11.5g} {point['x']:14.7g} {point['y']:14.7g}")

    def message(self, message):
        kind = message["type"]
        if kind == "experiment_request":
            self.show(f"\nRichiesta {message['request_id']} — Scopo: {message['purpose']}")
            self.experiment(message["experiment"])
        elif kind == "hypothesis":
            self.show(f"\nIpotesi {message['hypothesis_id']}: {message['statement']}")
            self.show("Evidenze: " + (", ".join(message["evidence"]) or "nessuna misura ancora"))
            for item in message["uncertainties"]:
                self.show(f"  Incerto: {item}")
        elif kind == "operator_question":
            self.show(f"\nDomanda: {message['question']}\nScopo: {message['purpose']}")
        elif kind == "prediction":
            self.points(message["points"], f"\nPrevisione preregistrata {message['prediction_id']}:")
        elif kind == "conclusion":
            self.show(f"\nConclusione: {message['summary']}")
            self.show(f"Ipotesi finale: {message['final_hypothesis_id'] or 'informazioni insufficienti'}")
            self.show("Evidenze: " + (", ".join(message["evidence"]) or "nessuna"))
            for key, label in (("limits", "Limite"), ("alternatives", "Alternativa")):
                for item in message[key]:
                    self.show(f"  {label}: {item}")
