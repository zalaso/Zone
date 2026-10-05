# Architettura attuale di Zone

Questa pagina descrive il codice locale, non una piattaforma web già distribuita. Il laboratorio funziona senza rete. Il benchmark v0.3 è stato verificato con fixture e baseline offline, non con trial LLM reali.

## Confini

| Area | Moduli | Responsabilità e confine |
| --- | --- | --- |
| Contratto pubblico | `protocol.py`, `agent_contract.py`, `benchmark_contract.py` | Valida messaggi e costruisce payload con liste positive di campi. Non importa il simulatore né file privati. |
| Core fisico | `simulator.py`, `evaluation.py`, `world_ast.py`, `world_forge.py` | Configurazione riservata, accelerazione, integrazione RK4, rumore e confronto delle traiettorie. World Forge genera leggi AST private e le filtra prima dell'uso. Nessun SDK o framework web. |
| Sessione locale | `session.py`, `investigation.py`, `terminal.py`, `cli.py` | Macchina a stati, decisione umana esplicita, esecuzione, registri pubblico/privato, CLI. |
| Benchmark | `benchmark_suite.py`, `benchmark_trial.py`, `benchmark_metrics.py`, `benchmark_report.py`, `benchmark_cli.py`, `benchmark_baselines.py` | Suite versionata e manifest, trial nelle quattro condizioni, freeze, probe, metriche, due baseline offline e report. |
| Provider LLM | `provider_base.py`, `provider_factory.py`, `llm.py`, `anthropic_client.py`, `gemini_client.py`, `ollama_client.py` | Traducono una richiesta canonica in API di provider. Non ricevono `Session` né accesso a strumenti. |
| Fixture | `fake_client.py`, `benchmark_fake.py` | Prove offline; il fixture benchmark è un oracolo privato e non rappresenta apprendimento. |
| Backend web locale | `backend.py`, `backend_state.py`, `backend_store.py`, `server_cli.py`, `web_agent.py`, `local_worlds.py` | FastAPI opzionale, stato ricostruito dagli eventi SQLite, CAS, ruoli, proiezione pubblica, scoring e reveal esplicito. Agente gestito opzionale; solo richieste pubbliche arrivano al client. |
| Integrity | `integrity_suite.py`, `integrity_store.py`, `integrity_cli.py` | Pacchetti split v1, commitment salati/proof, firma fisica euristica privata, catalogo SQLite con ammissione, ritiro e flag. Nessun provider. |
| Arena | `arena.py`, `arena_store.py`, `arena_client.py` | BYOA con ownership, quote/rate persistenti e receipt; embargo del test e classifiche con provenienza. |
| Frontend | `frontend/src/` | React/TypeScript/Vite per il ciclo locale e replay; consuma DTO dell'API e mantiene i token solo in memoria. |

Il flusso CLI è: messaggio validato → `Session.submit()` → decisione dell'operatore → `Session.run()` → simulatore → osservazione pubblica. L'API applica le stesse forme di messaggio tramite `LabState`, salva gli eventi in SQLite e proietta soltanto DTO pubblici. `Investigation` costruisce ogni chiamata CLI dalla sola storia pubblica e non è importato dal backend. `web_agent` costruisce richieste canoniche dalla sola storia della sessione web; il client non riceve `LabState` o record privati. Le modalità e il costruttore sono descritti in `docs/public-modes.md`. Nel benchmark: suite privata → trial → storia pubblica e submission congelata → verità dei probe privata → metriche → aggregazione offline. `execution_started` è scritto prima della simulazione; un errore successivo non autorizza un secondo lancio.

## Stato e debito tecnico osservato

- Il simulatore supporta le quattro famiglie storiche e mondi AST privati dei livelli 1–5. `world_forge.py` genera candidati e li verifica con esperimenti e probe; `world_forge_cli.py` produce file privati e manifest ridotti. Le suite benchmark v0.3 continuano a usare solo le quattro famiglie storiche. La fase 3 accetta un AST serializzato come dato JSON in una submission facoltativa; `identification.py` lo interpreta su una griglia privata e mantiene separate le metriche. Le formule testuali arbitrarie rimangono inerti.
- Il benchmark v0.3 ha `prior_only`, `passive_fixed`, `passive_sequential` e `active`, probe distinti per interpolazione/estrapolazione e risultati v0.1/v0.2 leggibili. Il confronto principale è quello sequenziale/attivo. Il fixture conosce la legge: serve soltanto a testare il percorso. Le baseline usano solo la storia pubblica.
- La CLI storica usa log JSONL sincronizzati: non sono una transazione atomica e non hanno ripresa dopo crash. Il backend locale usa invece eventi SQLite append-only, replay e confronto di versione; conserva `execution_started` prima del simulatore e non ripete un lancio interrotto. Il frontend React locale legge solo API pubbliche e richiede token inseriti a runtime per le azioni. Non esistono ancora utenti pubblici o deployment.
- Le chiamate a modelli reali non sono state validate. Il costo API remoto non è stimato senza dati di prezzo e fatturazione; resta disponibile l'utilizzo nativo restituito dal provider. I client offline registrano costo API nullo, che non comprende costi di calcolo locali.
- `README.md` e `docs/first-llm-session.md` documentano il laboratorio CLI; questa pagina e `ROADMAP.md` delimitano il lavoro verso la piattaforma pubblica.

## Regola di riservatezza

Configurazione, seed, legge e accelerazioni vere del test restano nei file privati del trial, nel database privato del backend o nella memoria del processo fidato. Train/development Integrity pubblicano deliberatamente i record completi, separati dal test. Il manifest test Integrity usa commitment salati senza hash grezzi del mondo/probe, mentre i manifest storici restano diagnostici; un probe appare solo dopo la conclusione. I test con sentinelle controllano la proiezione dei payload. Questo è un confine applicativo, non un isolamento del processo locale: i pacchetti `test` vanno tenuti esclusivamente sul server. Il catalogo locale applica gate atomici e ritiro, ma non protegge contro il gestore o host compromesso. Vedi `docs/integrity.md` e `docs/threat-model.md`.
