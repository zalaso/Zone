# ADR 0004 — Identificazione dopo il freeze

Stato: adottata nella fase 3.

Le previsioni numeriche sui probe restano obbligatorie e primarie. La legge candidata e le incertezze sono facoltative, così i risultati storici benchmark v0.1–v0.3 rimangono leggibili. La rappresentazione condivisa è un AST serializzato come stringa JSON, validato con l'interprete già usato da World Forge; questo evita l'esecuzione di codice e mantiene uno schema provider limitato a quattro varianti esatte della submission v0.3.

La verifica funzionale usa 128 stati deterministici derivati da materiale privato, metà nel dominio sperimentale e metà fuori. Espone l'errore per categoria e un giudizio di equivalenza empirica con soglia assoluta e relativa; non pretende equivalenza matematica generale. Complessità sintattica, dipendenze numeriche e calibrazione probabilistica sono risultati distinti, non componenti di un punteggio composito. La valutazione delle dipendenze può essere incerta in presenza di cancellazioni locali o soglie.

Il benchmark v0.3 mantiene il formato storico dei mondi e aggiunge solo campi facoltativi alla risposta finale. La CLI locale Forge richiede una sessione conclusa, pubblica i probe e registra la submission prima di usare la verità. I seed scelti per demo sono prevedibili: il percorso non è ancora una prova competitiva resistente a contaminazione o enumerazione. Quell'integrità appartiene alla fase 8.
