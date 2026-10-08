# Revisione operativa locale — aggiornamento 8 ottobre 2026

La fase 11 chiude i controlli di distribuzione pendenti. Resta **rischio alto per un servizio pubblico**: identità/TLS e operazioni sul bersaglio non sono implementate o verificate. Il precedente audit del 6 ottobre attribuiva 62/100 prima della prova CI/Docker; quel numero non è un punteggio aggiornato, scientifico o una percentuale della roadmap.

**Perimetro verificato:** Zone 0.11, wheel isolata e Docker Linux, un server fidato su loopback, SQLite, bundle sulla stessa origine, ruoli operatore/agente, Arena e Integrity. Questo percorso locale è utilizzabile; non è autorizzato alcun deployment. Pagamenti/webhook non esistono e non sono oggetto della revisione.

Blocchi prima del servizio pubblico:

- Pilot LLM reale ancora assente: fixture e baseline non verificano il comportamento di un vero modello o il costo del provider.
- Token di ruolo locali e quote per account non risolvono identità pubbliche, anti-Sybil, TLS, proxy fidati o isolamento fra host. Non esporre il bind del container su Internet.
- Nessuna prova di carico sul bersaglio, policy di retention distruttiva, monitoraggio/avvisi o canale privato di sicurezza già attivo.

Misure presenti: migrazioni additive con verifica schema/checksum e rollback atomico, backup SQLite consistente con WAL e restore separato; conferme e receipt impediscono esecuzioni implicite/replay di lanci; log HTTP ridotti, statici limitati al bundle, CSP e proiezioni provider testate. Il ripristino preserva revoche/ritiri alla data del backup, poi richiede riconciliazione e rotazione prima di riaprire.

Evidenze: `backend.py`, `backend_store.py`, `arena.py`, `arena_store.py`, `integrity_store.py`, `migrations.py`, `operations.py`, `runtime_ops.py`, `static_web.py`, CLI, workflow, Docker/Compose e guide operative; suite offline, demo quattro condizioni/Arena/reveal/restore, lint/tipi/build/archivi e browser Edge con FastAPI e bundle reale. Comandi e risultati puntuali in [verification.md](verification.md).

Evidenze nuove: [sei job GitHub Actions verdi](https://github.com/zalaso/Zone/actions/runs/37821050036), Python 3.11/3.12 Linux/Windows, frontend e runtime Docker non root. La wheel pulita è verificata anche sul PC con Python 3.14.4. Riavvio e restore mantengono tutte le righe applicative e il replay; i test individuano variazioni con conteggi identici. SDK provider assenti nel runtime e report senza impronte private. Nessun upload a scanner esterno o test contro sistemi terzi. GitHub conserva soltanto codice pubblico per contenuto in un repository privato e log CI ridotti, non i pacchetti privati delle prove.

Evidenze mancanti: host di distribuzione del servizio, carico/incidenti e pilot LLM. Docker Desktop non è installato sul PC; il test del container è su Linux GitHub, non una prova della futura configurazione di hosting. Dipendenze transitive e immagini base non sono bloccate integralmente; non sono promesse build identiche. Il restore conserva lo snapshot, senza recuperare revoche/ritiri successivi o la cecità scientifica.

Prossimo passo: pilot con modello e budget autorizzati, poi identità multiutente e beta privata. Ripetere le prove di [distribuzione](distribution.md) sul bersaglio scelto prima di ospitare il servizio. La [checklist](release-checklist.md) distingue repository privato, pubblicazione del codice e servizio online.
