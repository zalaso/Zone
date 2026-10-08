# Checklist di pubblicazione successiva

Prepara una release pubblica; non autorizza pubblicazione, deployment o spese. Versione 0.11.0, MIT; contratti benchmark v0.3, Arena BYOA v1 e Integrity v1 invariati. Repository privato e CI autorizzati nella fase 11, dopo conferma budget Actions zero e blocco degli extra.

- [x] Suite Python, Ruff, frontend, TypeScript, lint AST, build e scansioni bundle/archivi verdi da checkout pulito.
- [x] `ops demo` su cartella nuova: proof contro manifest originario, quattro trial, report e restore verificati.
- [x] GitHub Actions sul repository privato: Linux/Windows Python 3.11/3.12 e container Linux verdi ([esecuzione](https://github.com/zalaso/Zone/actions/runs/37821050036)).
- [x] Docker build/runtime sul runner Linux: loopback, UID non root, health, volume e arresto senza perdita dati; wheel pulita verificata anche sul PC.
- [x] LICENSE, versioni, changelog, CONTRIBUTING, condotta, template e guide aggiornati. Dipendenze e tool mantengono le proprie licenze.
- [x] Git, cronologia e archivi rivisti: nessuna credenziale, DB, backup, suite test privata, nonce o registro provider. `examples/` è demo a legge nota, inadatta a test ciechi.
- [x] Immagine con soli codice/backend e bundle pubblico; dati nel volume. Scansioni euristiche non sostituiscono revisione degli artefatti.
- [x] Pin Actions e lock frontend verificati; pin diretti Python e tag base Docker non garantiscono build bit-identiche.

Prima di un servizio pubblico:

- [ ] Progettare hosting, identità, ruoli, TLS, origine/CORS, proxy fidati e difese da identità multiple. Token locali non sostituiscono questo lavoro.
- [ ] Misurare carico, disco, concorrenza e rate; definire capacità/persistenza. SQLite/un processo è il perimetro verificato, non un cluster.
- [ ] Backup/restore sul bersaglio, protezione/cifratura, riconciliazione revoche/ritiri, rollback e responsabilità operative.
- [ ] Retention, monitoraggio, rotazione log e avvisi. Nessuna purge automatica di eventi o receipt.
- [ ] Canale privato di sicurezza e aggiornamento SECURITY.md; privacy e condizioni d'uso richiedono una decisione del gestore.
- [ ] Riesaminare confini sul deploy reale: chiavi, mount, statici, backup, log e pacchetti test.
- [ ] Pilot LLM autorizzato, con modello esplicito e limiti, per protocollo/costi; separare qualità scientifica e test software.
- [ ] Autorizzazione dell'autore a pubblicazione/deployment e spesa: nessuno di questi passi è automatico.

Procedure in [operations.md](operations.md), prove in [verification.md](verification.md). Preparazione completata non significa servizio online.
