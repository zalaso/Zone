# ADR 0010 — release locale e operazioni conservative

Data: 6 ottobre 2026. Stato: adottata nel perimetro locale.

L'autore ha scelto MIT. Le fasi 9–10 preparano la release 0.10.0 senza pubblicarla, conservando i contratti scientifici. Il percorso locale non richiede servizi a pagamento o nuovi strumenti del toolkit dell'autore.

CI offline con permessi di lettura, Actions fissate per SHA e timeout; container multistage con allowlist, utente non root e API/bundle sulla stessa origine. Nessun provider SDK o dato privato nell'immagine. Loopback resta il perimetro; identità pubbliche e cluster richiedono un altro progetto.

Migrazioni additive transazionali, adozione dello schema storico, ledger a checksum, rifiuto di schemi futuri/estranei. Nessun downgrade SQL o cancellazione automatica. Restore su file nuovo e codice compatibile. SQLite Online Backup API conserva uno snapshot consistente anche con WAL; checksum/manifest non autenticano dati contro un host ostile.

Liveness e readiness read-only separate, senza chiamate a provider. Log HTTP a campi consentiti. Retention è un inventario: eliminare eventi/receipt cambierebbe idempotenza e integrità. File privati esterni richiedono backup separato.

Backup conserva revoche/ritiri solo alla sua data: recupero con riconciliazione e rotazione token. Docker e CI remoto non eseguiti sull'host devono essere provati prima di pubblicare. TLS, identità, multi-worker, osservabilità remota e purge fuori dal perimetro; nessuna promessa di riproducibilità LLM o build identiche.
