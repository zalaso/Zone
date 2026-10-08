# Stato di Zone — 8 ottobre 2026

**Fasi 0–11 completate nel perimetro locale: Zone 0.11.0, MIT.** CI Linux/Windows, Docker Linux e installazione pulita con riavvio/restore sono verificati. Il repository remoto è privato; rimangono pilot LLM, identità multiutente, beta ospitata e apertura pubblica. Zone non è ancora un servizio pubblico né un benchmark scientificamente validato con modelli reali.

| Area implementata | Cosa è disponibile |
| --- | --- |
| Audit e struttura | Git locale e remoto privato, confini pubblico/privato, architettura, decisioni e debito documentati |
| Benchmark v0.3 | Quattro condizioni; confronto principale active/passive_sequential; metriche interpolation/extrapolation; risultati grezzi, appaiamento rigoroso, baseline offline e bootstrap con soglia |
| World Forge v1 | Generazione con seed, AST sicuro e simulatore per livelli 1–5, pipeline numerica di validazione; interfacce 6–9 senza generatore |
| Identificazione | Previsioni numeriche, AST facoltativo, equivalenza funzionale empirica, complessità, dipendenze e calibrazione separate |
| Backend | FastAPI locale, SQLite, CAS, eventi, replay, freeze, scoring separato e reveal controllato |
| Laboratorio web | React/TypeScript; richieste, modifiche/rifiuti, domande, ipotesi, previsioni, esecuzione esplicita, risultati e replay |
| Modalità pubbliche locali | Scientist, Human vs AI, Watch an Agent, World of the Day, Build a Universe |
| Integrity v1 | Split train/development pubblici e test privato; commitment salati, proof canonica, catalogo con ritiro e flag, embargo dei punteggi, duplicati euristici e rate account persistenti; threat model |
| Zone Arena BYOA v1 | Challenge, ownership, protocollo versionato, credenziali revocabili con scadenza, quote persistenti, idempotenza, audit, otto classifiche indipendenti, dashboard operatore e client minimo |
| Qualità open source | MIT scelta dall'autore, CONTRIBUTING, condotta/sicurezza, template, changelog, versioni coerenti, CI offline, lint/tipi e scansioni archivi/bundle |
| Operazioni | Migrazioni schema 1–2, health live/ready, log a campi consentiti, backup live consistente, restore nuovo, inventario crescita, demo completa e guide/container locale |
| Distribuzione | Sei job CI verdi; Linux/Windows Python 3.11/3.12, frontend, Docker non root e wheel isolata senza SDK; dati e replay invariati dopo riavvio e restore |

Arena è stata verificata con la baseline affine offline e un operatore simulato, con messaggi BYOA sintetici nel browser reale, e con test di errori/concorrenza/privacy. Nel browser l'operatore approva, sceglie l'esplorazione ed esegue in tre azioni distinte. La demo offline ha eseguito tre esperimenti e nove passi della baseline, congelato e valutato la submission, chiuso la challenge e revocato il token. Il test browser ha eseguito un lancio, tre punti, conclusione/submission, classifiche, chiusura e revoca; verifica anche storage vuoto e mobile senza overflow.

Verifica fase 11: **207 test Python**, **15 test frontend**, **2 test Node dei controlli qualità**, Ruff, TypeScript, build Vite e scansioni archivi/bundle. [CI reale](https://github.com/zalaso/Zone/actions/runs/37821050036) verde con sei job; dettaglio e comandi in [verifiche](verification.md) e [distribuzione](distribution.md). Lo smoke Edge con FastAPI è quello della fase 10. Nessuna chiamata API a provider LLM, credenziale di provider usata, modello scaricato o deployment. Le guide per iniziare sono [Integrity](integrity.md), [Arena](arena.md), [modalità locali](public-modes.md) e [prima sessione LLM](first-llm-session.md).

## Cosa manca

1. **Fase 12, pilot scientifico reale.** Un'indagine con modello e operatore umano, costi e chiamate misurati e protocollo controllato. Richiede modello e budget autorizzati. Le prove offline non misurano scoperta; le risposte LLM non sono esattamente riproducibili.
2. **Fase 13, identità multiutente.** Account, ruoli e isolamento per utenti esterni; token locali non bastano.
3. **Fase 14, beta privata ospitata.** Host/TLS, monitoraggio, carico, backup e recupero sul bersaglio con utenti invitati. Nessun deployment eseguito.
4. **Fase 15, apertura pubblica.** Pubblicazione del codice/release, policy, canale sicurezza e servizio dopo la beta. Checklist in [release](release-checklist.md); il container attuale resta su loopback.

Limiti Arena: account e quote sono gestiti da un operatore locale; non esistono ancora identità pubbliche o difesa contro identità multiple. Il client esterno può dichiarare un modello, ma il server non verifica quel modello né le chiamate, i token o i costi; questi ultimi rimangono null. Il client minimo e il builder pubblico sono disponibili, ma un runner BYOA con un vero modello deve ancora essere validato in un pilot. Arena usa SQLite, solo esplorazione e un trial per agente/challenge; non accorpa metriche o mondi. Un esperimento interrotto consuma budget e viene arrestato, senza ricostruire o rieseguire la misura.

Il prossimo passo pratico è la fase 12, con autorizzazione esplicita a modello e budget. La distribuzione verificata non attesta un servizio pubblico pronto né integrità dell'host/modello/partecipante. Migrazioni, backup e confini sono in [operazioni](operations.md); limiti scientifici nel [threat model](threat-model.md).

Integrity è stato verificato con un pacchetto Forge sui livelli 1–5, una demo Arena con tre esperimenti e nove passi di baseline, reveal/proof verificati contro il manifest conservato prima, e un pacchetto benchmark con quattro trial oracolo offline, aggregazione e report. Il browser reale ha attraversato embargo, flag operatore, esclusione dai ranghi con grezzi conservati, chiusura, revoca e reveal; la proof risalvata da JavaScript è stata verificata dalla CLI. Queste prove non misurano un LLM né rendono cieco il seed delle demo.
