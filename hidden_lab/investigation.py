"""Ciclo fidato: l'agente propone, solo la persona autorizza l'esecuzione."""

import time

from .agent_contract import build_request
from .provider_base import ADAPTER_VERSION, ProviderError
from .protocol import ValidationError, decode, observation_times, require_keys, validate_message
from .terminal import OperatorStop


class Investigation:
    def __init__(self, session, client, settings, terminal):
        self.session = session
        self.client = client
        self.settings = settings
        self.terminal = terminal
        self.calls = 0
        self.turns = 0
        session.record_private("agent_settings.jsonl", {
            "provider": client.provider, "sdk_version": getattr(client, "sdk_version", None),
            "transport_version": getattr(client, "http_version", None),
            "adapter_version": ADAPTER_VERSION, "settings": settings.to_dict(),
            "generation_settings": client.generation_settings,
        })

    def next_message(self, phase):
        for attempt in range(self.settings.max_corrections + 1):
            if self.turns >= self.settings.max_turns:
                self.session.stop("turn_limit")
                return None
            if self.calls >= self.settings.max_calls:
                self.session.stop("call_budget")
                return None
            request = build_request(self.session.events, self.settings, phase,
                                    self.settings.max_calls - self.calls, self.settings.max_turns - self.turns)
            if request.size_bytes() > self.settings.max_input_bytes:
                self.session.stop("input_limit")
                return None
            self.calls += 1
            audit = {"call_index": self.calls, "turn_index": self.turns + 1, "correction_attempt": attempt,
                     "public_seq": len(self.session.events), "phase": phase, "requested_model": self.settings.model,
                     "provider": self.client.provider, "adapter_version": ADAPTER_VERSION,
                     **request.contract_fingerprints()}
            self.session.record_private("model_calls.jsonl", {**audit, "outcome": "started", "usage": None})
            self.terminal.show(f"\nModello: chiamata {self.calls}/{self.settings.max_calls}; attendo la risposta...")
            start = time.monotonic()
            try:
                reply = self.client.complete(request)
            except ProviderError as exc:
                self.session.record_private("model_calls.jsonl", {**audit, "outcome": "provider_error",
                                            "error_code": exc.code, "usage": None,
                                            "http_status": exc.http_status,
                                            "provider_error_code": exc.provider_code,
                                            "elapsed_seconds": round(time.monotonic() - start, 3)})
                detail = f", HTTP {exc.http_status}" if exc.http_status is not None else ""
                self.terminal.show(f"Errore del provider ({exc.code}{detail}). Nessun tentativo automatico; i lanci precedenti restano registrati.")
                self.session.stop("provider_error")
                return None
            try:
                if reply.issue:
                    raise ValidationError("Risposta incompleta o rifiutata dal provider: emetti un messaggio valido e completo.")
                envelope = decode(reply.text)
                require_keys(envelope, ("message",))
                message = validate_message(envelope["message"])
                if message["type"] not in request.allowed_types:
                    raise ValidationError("Messaggio non consentito nella fase corrente. Consulta next_action.allowed_types.")
                if message["type"] == "experiment_request" and len(observation_times(message["experiment"])) > self.settings.max_points:
                    raise ValidationError(f"Questa sessione ammette al massimo {self.settings.max_points} punti di osservazione.")
                self.session.submit(message, actor="agent")
            except ValidationError as exc:
                self.session.record_error(str(exc))
                self.session.record_private("model_calls.jsonl", {**audit, **reply.metadata, "outcome": "invalid_response",
                                            "elapsed_seconds": round(time.monotonic() - start, 3)})
                self.terminal.show(f"Risposta non valida: {exc}")
                if self.client.provider == "chatgpt":
                    diagnostics = reply.metadata.get("provider_details") or {}
                    labels = {"empty": "testo ricevuto vuoto", "markdown_fence": "testo racchiuso in blocchi Markdown",
                              "invalid": "testo ricevuto non conforme alla sintassi JSON", "valid": "sintassi JSON valida, contratto non rispettato"}
                    label = labels.get(diagnostics.get("json_syntax"))
                    if label:
                        self.terminal.show(f"Diagnostica: {label}. Dettagli strutturali nel registro model_calls.jsonl.")
                if attempt < self.settings.max_corrections:
                    self.terminal.show("Richiedo una correzione entro i limiti rimasti.")
                continue
            self.session.record_private("model_calls.jsonl", {**audit, **reply.metadata, "outcome": "accepted",
                                        "elapsed_seconds": round(time.monotonic() - start, 3)})
            self.turns += 1
            self.terminal.message(message)
            return message
        self.session.stop("invalid_response_limit")
        return None

    def answer_question(self, message):
        answer = self.terminal.answer_text("Risposta (testo pubblico, 'esci' termina): ")
        self.session.submit({"type": "operator_answer", "question_id": message["question_id"], "answer": answer}, actor="operator")

    def handle_request(self, message):
        request_id = message["request_id"]
        choice = self.terminal.choose("Decisione [a=approva / m=modifica / r=rifiuta / esci]: ", ("a", "m", "r"))
        decision = {"type": "operator_decision", "request_id": request_id,
                    "action": {"a": "approve", "m": "modify", "r": "reject"}[choice]}
        if choice == "m":
            decision["modified_experiment"] = self.terminal.modify(message["experiment"], self.settings.max_points)
        decision["reason"] = self.terminal.answer_text("Motivazione pubblica della decisione: ")
        self.session.submit(decision, actor="operator")
        if choice == "r":
            self.terminal.show("Richiesta rifiutata: nessun esperimento eseguito.")
            return
        mode = self.terminal.choose("Modalità [e=esplorazione / v=verifica con previsione / esci]: ", ("e", "v"))
        self.session.submit({"type": "execution_mode", "request_id": request_id,
                             "mode": "exploration" if mode == "e" else "verification"}, actor="operator")
        if mode == "v":
            while not self.session.closed:
                reply = self.next_message("predict")
                if reply is None or reply["type"] == "conclusion":
                    return
                if reply["type"] == "prediction":
                    break
                if reply["type"] == "operator_question":
                    self.answer_question(reply)
            if self.session.closed:
                return
        self.terminal.show("\nConfigurazione definitiva:")
        self.terminal.experiment(self.session.requests[request_id]["experiment"])
        self.terminal.choose("Autorizzi questo lancio? [esegui/esci]: ", ("esegui",))
        # Nessuna chiamata al provider dentro run. Una risposta di rete persa
        # in seguito non rientra mai in questo ramo e non ripete l'esperimento.
        observation = self.session.run(request_id)
        if observation["status"] == "ok":
            self.terminal.points(observation["points"], "\nMisure osservate:")
        else:
            self.terminal.show(observation["error"]["message"])
        last = self.session.events[-1]["message"]
        if last["type"] == "verification" and last["metrics"] is not None:
            self.terminal.show(f"Errore RMSE: {last['metrics']['position_rmse']:.6g} m. Identificazione della legge non valutata.")
        self.terminal.show(f"Esperimenti: {observation['executed_count']}; budget residuo: {observation['remaining_budget']}.")

    def run(self):
        labels = {"openai": "OPENAI REALE: le chiamate API possono avere un costo",
                  "chatgpt": "CHATGPT REALE: uso del piano autorizzato; nessun fallback API a pagamento",
                  "anthropic": "ANTHROPIC REALE: le chiamate API possono avere un costo",
                  "gemini": "GEMINI REALE: le chiamate API possono avere un costo",
                  "ollama": "OLLAMA LOCALE: il modello viene eseguito sul tuo computer; nessun download automatico",
                  "simulated": "CLIENT SIMULATO: copione, nessun LLM e nessuna chiamata di rete"}
        label = labels[self.client.provider]
        self.terminal.show(label)
        self.terminal.show(f"Provider: {self.client.provider}; modello: {self.settings.model}; massimo {self.settings.max_calls} chiamate e {self.settings.max_turns} turni validi.")
        if self.client.provider == "chatgpt":
            self.terminal.show("La preview ChatGPT non accetta max_output_tokens: limite locale di risposta 64 KiB, quota del piano separata. Controlla Usage e disabilita eventuali crediti extra nelle impostazioni ChatGPT.")
        self.terminal.show("Suggerimenti teorici dell'operatore entrano nella storia pubblica e possono influenzare i risultati.")
        try:
            self.terminal.choose("Avvia l'indagine? [avvia/esci]: ", ("avvia",))
            if self.client.provider == "ollama":
                try:
                    self.client.preflight(self.settings.model)
                except ProviderError as exc:
                    self.terminal.show(f"Errore locale Ollama ({exc.code}). Avvia il servizio e verifica il modello con 'ollama list'; nessun download eseguito.")
                    return False
            while not self.session.closed:
                message = self.next_message("choose_next")
                if message is None:
                    break
                if message["type"] == "experiment_request":
                    self.handle_request(message)
                elif message["type"] == "operator_question":
                    self.answer_question(message)
        except (OperatorStop, KeyboardInterrupt):
            self.session.stop("operator_stop")
        if self.session.conclusion is None:
            reason = self.session.events[-1]["message"].get("reason", "operator_stop")
            self.terminal.show(f"Indagine interrotta ({reason}), senza conclusione del modello. Registri conservati.")
        self.terminal.show(f"Fine: {self.calls} chiamate, {self.turns} turni validi, {self.session.executed_count} esperimenti.")
        return self.session.conclusion is not None
