# Stato di Zone — 6 ottobre 2026

**Fasi 0–10 implementate: Zone 0.10.0, MIT.** Le prove locali coprono laboratorio, Arena, benchmark e operazioni; rimangono la verifica Docker e CI nel loro ambiente, la pubblicazione e il pilot LLM reale. Zone non è ancora un servizio pubblico né un benchmark scientificamente validato con modelli reali.

| Area implementata | Cosa è disponibile |
| --- | --- |
| Audit e struttura | Git locale, confini pubblico/privato, architettura, decisioni e debito documentati |
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

Arena è stata verificata con la baseline affine offline e un operatore simulato, con messaggi BYOA sintetici nel browser reale, e con test di errori/concorrenza/privacy. Nel browser l'operatore approva, sceglie l'esplorazione ed esegue in tre azioni distinte. La demo offline ha eseguito tre esperimenti e nove passi della baseline, congelato e valutato la submission, chiuso la challenge e revocato il token. Il test browser ha eseguito un lancio, tre punti, conclusione/submission, classifiche, chiusura e revoca; verifica anche storage vuoto e mobile senza overflow.

Verifica finale: **203 test Python**, **15 test frontend**, **2 test Node dei controlli qualità**, Ruff, TypeScript, build Vite, scansioni archivi/bundle e smoke Edge sulla build con FastAPI; dettaglio e comandi in [verifiche](verification.md). Nessuna chiamata API reale, credenziale di provider usata, modello scaricato o deployment. Le guide per iniziare sono [Integrity](integrity.md), [Arena](arena.md), [modalità locali](public-modes.md) e [prima sessione LLM](first-llm-session.md).

## Cosa manca

1. **Verifica nell'ambiente di distribuzione.** Docker non è installato sull'host di sviluppo: immagine/runtime non eseguiti. CI predisposta ma non eseguita su GitHub, repository ancora locale. Prima della release provare entrambi; istruzioni in [operazioni](operations.md).
2. **Pubblicazione e servizio pubblico.** Checklist in [release](release-checklist.md): identità, TLS, carico, monitoraggio, backup sul bersaglio e canale sicurezza. Non è autorizzato né eseguito un deployment. Il container documentato resta su loopback.
3. **Pilot scientifico reale.** Provare almeno un'indagine con un modello reale e operatore umano, misurare costi e chiamate effettivi, controllare il protocollo sulle risposte del provider e poi progettare una valutazione su più mondi. Le prove offline non misurano capacità di scoperta. Le risposte LLM non sono esattamente riproducibili.

Limiti Arena: account e quote sono gestiti da un operatore locale; non esistono ancora identità pubbliche o difesa contro identità multiple. Il client esterno può dichiarare un modello, ma il server non verifica quel modello né le chiamate, i token o i costi; questi ultimi rimangono null. Il client minimo e il builder pubblico sono disponibili, ma un runner BYOA con un vero modello deve ancora essere validato in un pilot. Arena usa SQLite, solo esplorazione e un trial per agente/challenge; non accorpa metriche o mondi. Un esperimento interrotto consuma budget e viene arrestato, senza ricostruire o rieseguire la misura.

Il prossimo passo pratico è verificare Docker/CI, poi scegliere se pubblicare il codice o autorizzare un pilot. L'implementazione delle fasi 9–10 non attesta un servizio pubblico pronto né integrità dell'host/modello/partecipante. Migrazioni, backup e confini sono in [operazioni](operations.md); limiti scientifici nel [threat model](threat-model.md).

Integrity è stato verificato con un pacchetto Forge sui livelli 1–5, una demo Arena con tre esperimenti e nove passi di baseline, reveal/proof verificati contro il manifest conservato prima, e un pacchetto benchmark con quattro trial oracolo offline, aggregazione e report. Il browser reale ha attraversato embargo, flag operatore, esclusione dai ranghi con grezzi conservati, chiusura, revoca e reveal; la proof risalvata da JavaScript è stata verificata dalla CLI. Queste prove non misurano un LLM né rendono cieco il seed delle demo.
