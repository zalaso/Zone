# Changelog

## 0.10.0 — 6 ottobre 2026, release locale preparata

Consolida le fasi 0–8 e completa l'implementazione delle fasi 9–10: licenza MIT scelta dall'autore, guide di contribuzione e sicurezza, template, versioni Python/frontend coerenti, CI offline e container locale. Nessuna release remota, immagine pubblicata o deployment eseguito.

- Migrazioni SQLite additive versionate con checksum, adozione dello schema precedente e rollback transazionale in caso di errore.
- CLI `ops`: stato, verifica, migrazione, backup live consistente, restore su file nuovo, conteggio della crescita e demo completa offline.
- Health live/ready, log HTTP a campi consentiti, errori interni ridotti e header browser; API e bundle compilato possono condividere l'origine.
- Controlli Ruff, TypeScript, lint AST e scansioni del bundle/archivi; istruzioni per ambienti separati, ripristino e pubblicazione successiva.

Benchmark v0.3, Integrity v1 e Arena BYOA v1 mantengono i formati esistenti e le metriche separate. Il passaggio da 0.4.0 Python / 0.5.0 frontend a 0.10.0 uniforma la versione del progetto; non rinumera i protocolli. Le versioni precedenti erano revisioni locali, non release pubblicate. Dettagli storici in [verifiche](docs/verification.md).
