# Revisione operativa locale — 6 ottobre 2026

Production audit: **62/100, rischio alto per un servizio pubblico**; verifica Docker/CI remoto e progetto delle identità/TLS sono i principali passi prima del lancio. È un giudizio qualitativo secondo la skill locale production-audit, non un punteggio scientifico o una percentuale della roadmap.

**Perimetro verificato:** checkout Zone 0.10, un server fidato su loopback, SQLite, bundle sulla stessa origine, ruoli operatore/agente, Arena e Integrity. Questo percorso locale è utilizzabile; non è autorizzato alcun deployment. Pagamenti/webhook non esistono e non sono oggetto della revisione.

Blocchi prima del servizio pubblico:

- Immagine Docker non costruita/eseguita sull'host, privo di Docker. Workflow remoto mai eseguito: non attribuire lo stato verde alle sole configurazioni YAML.
- Token di ruolo locali e quote per account non risolvono identità pubbliche, anti-Sybil, TLS, proxy fidati o isolamento fra host. Non esporre il bind del container su Internet.
- Nessuna prova di carico sul bersaglio, policy di retention distruttiva, monitoraggio/avvisi o canale privato di sicurezza già attivo.

Misure presenti: migrazioni additive con verifica schema/checksum e rollback atomico, backup SQLite consistente con WAL e restore separato; conferme e receipt impediscono esecuzioni implicite/replay di lanci; log HTTP ridotti, statici limitati al bundle, CSP e proiezioni provider testate. Il ripristino preserva revoche/ritiri alla data del backup, poi richiede riconciliazione e rotazione prima di riaprire.

Evidenze: `backend.py`, `backend_store.py`, `arena.py`, `arena_store.py`, `integrity_store.py`, `migrations.py`, `operations.py`, `runtime_ops.py`, `static_web.py`, CLI, workflow, Docker/Compose e guide operative; suite offline, demo quattro condizioni/Arena/reveal/restore, lint/tipi/build/archivi e browser Edge con FastAPI e bundle reale. Comandi e risultati puntuali in [verification.md](verification.md).

Evidenze mancanti: CI Linux/Windows 3.11/3.12 remota, runtime container, host di distribuzione, carico/incidenti e pilot LLM. Nessun upload a scanner esterno o test contro sistemi terzi. La verifica corrente usa Python 3.14.4 Windows; la matrice progettata non è stata simulata come se fosse già passata.

Prossima verifica concreta: su un host con Docker eseguire build, bootstrap, restore, health e UI come in [operations.md](operations.md); poi eseguire CI sul repository pubblicato con autorizzazione dell'autore. La [checklist](release-checklist.md) distingue pubblicazione del codice e servizio online.
