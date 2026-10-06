# Roadmap Zone

Visione: **Zone is a public laboratory where humans and artificial agents try to discover the laws of unfamiliar universes through experiments.** Si procede per percorsi verticali locali e verificabili; nessuna chiamata a pagamento, download di modelli, pubblicazione o deployment senza autorizzazione successiva.

Stati: **completata**, **in corso**, **da fare**, oppure **implementata con verifica pendente** quando manca l'ambiente. Ogni fase richiede test pertinenti, suite completa verde, documentazione e controllo del confine pubblico/privato. Le metriche restano separate.

| Fase | Criteri verificabili di completamento | Stato |
| --- | --- | --- |
| 0. Audit | Repository e test ispezionati; Git locale e `.gitignore`; architettura, debito e confini documentati. | Completata |
| 1. Benchmark | Quattro condizioni; probe e metriche per categoria; due baseline non LLM; appaiamento rigoroso; bootstrap con soglia e avvisi; compatibilità v0.1/v0.2; prova offline. | Completata |
| 2. World Forge | AST sicuro serializzabile, validato e deterministico; livelli 1–5 generati e filtrati; interfacce per 6–9; euristica di difficoltà esplicitata; nessun `eval`. | Completata |
| 3. Identificazione | Submission AST comune a umani/agenti; previsione numerica principale; equivalenza funzionale, complessità, dipendenze e calibrazione separate. | Completata |
| 4. Backend | FastAPI sottile, SQLite sostituibile, macchina a stati, replay, reveal controllato, input e rate limit; test senza rete. | Completata |
| 5. Laboratorio web | React/TypeScript/Vite accessibile; percorso completo dalla challenge al risultato e replay; bundle senza segreti. | Completata |
| 6. Modalità pubbliche | Scientist, Human vs AI con condizioni equivalenti, Watch an Agent, World of the Day locale e Build a Universe validato. | Completata |
| 7. Zone Arena | Protocollo BYOA versionato, token revocabili, quote, idempotenza, audit e leaderboard multidimensionale. | Completata |
| 8. Integrità | Suite train/development pubbliche e test privata; manifest/reveal; controlli di contaminazione, duplicati e abuso; threat model. | Completata |
| 9. Qualità open source | MIT scelta dall'autore, CONTRIBUTING, condotta, template, changelog, 0.10.0, demo, container e CI offline. | Implementata; verifica Docker/CI remota pendente |
| 10. Preparazione pubblicazione | Health, migrazioni, log, backup/restore, ambienti, checklist/guide e demo locale completa. Deployment non eseguito. | Completata nel perimetro locale |

## Criteri immediati

La fase 1 include due baseline che producono trial senza accesso ai probe prima del freeze, intervalli bootstrap deterministici e assenti sotto otto mondi appaiati, lettura delle suite v0.1/v0.2 e CLI offline completa. La fase 2 ha un generatore World Forge v1 con seed, AST per livelli 1–5, simulazione RK4, controlli numerici e scientifici euristici, manifest ridotto, CLI offline e interfacce esplicite per livelli 6–9. I mondi AST non entrano nelle suite benchmark v0.3: quelle mantengono schema e validazione originari. La fase 3 usa un sottoinsieme di submission scientifica comune per operatori e agenti benchmark v0.3; il percorso locale World Forge rilascia i probe dopo la conclusione e confronta l'AST su una griglia privata. La fase 4 aggiunge una API FastAPI locale con eventi SQLite, token di ruolo, CAS su versione, replay, freeze e reveal esplicito. La fase 5 fornisce il client web locale per l'intero ciclo umano dal lancio al risultato, con replay e bundle pubblico. Le metriche sono separate e descritte in `docs/identification.md`; il backend in `docs/backend.md` e la UI in `docs/frontend.md`. Le modalità della fase 6 sono in `docs/public-modes.md`; il consolidamento e le prove browser in `docs/verification.md`. La fase 7 espone BYOA v1 con ownership, token con scadenza e revoca, quote SQLite persistenti, receipt idempotenti, audit e classifiche distinte per challenge; guide in `docs/arena.md` e stato complessivo in `docs/status.md`.

## Decisioni e limiti

Le decisioni tecniche sono in `docs/decisions/`. Il repository Git è locale. Backend e frontend sono vincolati a loopback; non esistono ancora deployment o servizio pubblico. La fase 6 aggiunge le modalità locali e un agente gestito sul server, offline per default; nessun test con LLM reale prova capacità di scoperta. La fase 7 è un’Arena locale con operatore: non certifica il modello del client esterno, i suoi costi o l’integrità competitiva. La fase 8 aggiunge i controlli locali di integrità; la fase 9 è implementata con verifica Docker/CI pendente e la fase 10 è completata nel perimetro locale. CI remoto e runtime Docker restano da provare nel relativo ambiente. La pubblicazione del codice e qualsiasi spesa restano fuori dallo sviluppo autorizzato.

La fase 8 è documentata in [Integrity](docs/integrity.md) e nel [threat model](docs/threat-model.md): catalogo locale fidato, split impegnati, ritiro dopo reveal, score in embargo, flag append-only, duplicati euristici e limiti per account. Nessuna attestazione del modello o dei costi BYOA; nessun trial LLM reale.

Le fasi 9–10 portano Zone alla versione 0.10.0 con MIT, CI offline, container locale, schema SQLite 2 e operazioni conservative. Prove locali: 203 test Python, 15 frontend, 2 controlli Node e smoke Edge sulla build. Guide in [operazioni](docs/operations.md), [checklist](docs/release-checklist.md) e [revisione operativa](docs/production-readiness.md). Docker assente e CI remota non eseguita: implementazione disponibile, verifica di distribuzione ancora necessaria.
