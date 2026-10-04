# Stato di Zone — 4 ottobre 2026

**Fasi 0–7 completate come percorsi locali verificati. Fasi 8–10 da fare.** Zone ha un laboratorio funzionante e un'Arena BYOA locale; non è ancora un servizio pubblico né un benchmark scientificamente validato con modelli reali.

| Area implementata | Cosa è disponibile |
| --- | --- |
| Audit e struttura | Git locale, confini pubblico/privato, architettura, decisioni e debito documentati |
| Benchmark v0.3 | Quattro condizioni; confronto principale active/passive_sequential; metriche interpolation/extrapolation; risultati grezzi, appaiamento rigoroso, baseline offline e bootstrap con soglia |
| World Forge v1 | Generazione con seed, AST sicuro e simulatore per livelli 1–5, pipeline numerica di validazione; interfacce 6–9 senza generatore |
| Identificazione | Previsioni numeriche, AST facoltativo, equivalenza funzionale empirica, complessità, dipendenze e calibrazione separate |
| Backend | FastAPI locale, SQLite, CAS, eventi, replay, freeze, scoring separato e reveal controllato |
| Laboratorio web | React/TypeScript; richieste, modifiche/rifiuti, domande, ipotesi, previsioni, esecuzione esplicita, risultati e replay |
| Modalità pubbliche locali | Scientist, Human vs AI, Watch an Agent, World of the Day, Build a Universe |
| Zone Arena BYOA v1 | Challenge, ownership, protocollo versionato, credenziali revocabili con scadenza, quote persistenti, idempotenza, audit, otto classifiche indipendenti, dashboard operatore e client minimo |

Arena è stata verificata con la baseline affine offline e un operatore simulato, con messaggi BYOA sintetici nel browser reale, e con test di errori/concorrenza/privacy. Nel browser l'operatore approva, sceglie l'esplorazione ed esegue in tre azioni distinte. La demo offline ha eseguito tre esperimenti e nove passi della baseline, congelato e valutato la submission, chiuso la challenge e revocato il token. Il test browser ha eseguito un lancio, tre punti, conclusione/submission, classifiche, chiusura e revoca; verifica anche storage vuoto e mobile senza overflow.

Verifica finale: **164 test Python**, **13 test frontend**, controllo TypeScript e build Vite; dettaglio e comandi in [verifiche](verification.md). Nessuna chiamata API reale, credenziale di provider usata, modello scaricato o deployment. Le guide per iniziare sono [Arena](arena.md), [modalità locali](public-modes.md) e [prima sessione LLM](first-llm-session.md).

## Cosa manca

1. **Fase 8 — integrità competitiva.** Split train/development pubblici e test privati, gestione della contaminazione, manifest/reveal sistematici, rilevazione duplicati e abuso, threat model. I controlli locali di ownership e reveal di Arena non sostituiscono questa fase.
2. **Fase 9 — qualità open source.** Scelta della licenza da parte dell'autore, CONTRIBUTING, condotta, template, changelog, versione coerente, demo/container e CI per test/lint/type check.
3. **Fase 10 — preparazione alla distribuzione.** Health check, migrazioni versionate, logging, backup/ripristino, ambienti, gestione della crescita di receipt/eventi, checklist e guide di distribuzione. Non è autorizzato né eseguito un deployment.
4. **Pilot scientifico reale.** Provare almeno un'indagine con un modello reale e operatore umano, misurare costi e chiamate effettivi, controllare il protocollo sulle risposte del provider e poi progettare una valutazione su più mondi. Le prove offline non misurano capacità di scoperta. Le risposte LLM non sono esattamente riproducibili.

Limiti Arena: account e quote sono gestiti da un operatore locale; non esistono ancora identità pubbliche o difesa contro identità multiple. Il client esterno può dichiarare un modello, ma il server non verifica quel modello né le chiamate, i token o i costi; questi ultimi rimangono null. Il client minimo e il builder pubblico sono disponibili, ma un runner BYOA con un vero modello deve ancora essere validato in un pilot. Arena usa SQLite, solo esplorazione e un trial per agente/challenge; non accorpa metriche o mondi. Un esperimento interrotto consuma budget e viene arrestato, senza ricostruire o rieseguire la misura.

Il prossimo passo della roadmap è la **fase 8**, prima di trattare le classifiche come risultati competitivi pubblicabili.
