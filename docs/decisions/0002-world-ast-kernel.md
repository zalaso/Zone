# 0002 — Interprete AST prima del generatore

Stato: accettata per il nucleo locale della fase 2.

Le leggi future saranno dati JSON validati e interpretati da un insieme chiuso di operazioni numeriche. `world_ast.py` non usa `eval`, `exec`, import dinamici o formule testuali. Il parser impone chiavi, arità, finitezza, limiti di profondità e numero di nodi; la valutazione limita il modulo dei risultati. Gli oggetti AST sono immutabili e serializzabili canonicamente.

La separazione iniziale dalle quattro famiglie storiche ha permesso di stabilizzare l'interprete prima della generazione. La fase successiva, documentata nella decisione 0003, lo collega al simulatore senza modificare il formato delle suite benchmark v0.3. La stessa grammatica potrà in seguito servire a valutare submission di leggi, con un sottoinsieme pubblico separato dalla verità privata.

Il livello dichiarato impone una classe di espressioni, ma non misura da solo la difficoltà effettiva; degenerazione, somiglianza con leggi più semplici e osservabilità richiedono filtri empirici prima che un mondo possa essere accettato.
