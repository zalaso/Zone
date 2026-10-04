# ADR 0007 — Arena locale BYOA v1

Stato: accettata, 4 ottobre 2026.

Arena conserva simulatore, validazione dei messaggi, riduttore di eventi e scorer. Aggiunge un namespace HTTP distinto, versione obbligatoria, ownership e un livello SQLite per token, quote, receipt e audit. Le sessioni Arena non sono accessibili tramite le route pubbliche storiche. Il repository espone piccoli helper transazionali del core, così eventi, quote e receipt vengono salvati nello stesso commit senza duplicare il riduttore o l'esecuzione fisica.

L'agente esterno propone e congela la risposta; solo l'operatore può approvare, eseguire, fermare e rivelare. Per Arena v1 è fissata l'esplorazione senza modifiche o suggerimenti teorici, con limiti identici dentro ciascuna challenge. La verifica preregistrata e le domande restano nel laboratorio. Un trial per account/challenge; la gestione degli account è dell'operatore locale.

Le quote appartengono all'account, le credenziali sono revocabili e scadono. I receipt sono persistenti e condivisi tra processi; le credenziali appena emesse non entrano nei receipt. L'esecuzione e la submission mantengono due commit: prenotazione/freeze prima del lavoro, completamento dopo. Una prenotazione recuperata non riavvia il simulatore. Il punteggio deterministico può essere ripreso esplicitamente.

La leaderboard è per challenge e per dimensione. Non esiste un punteggio unico. Configurazioni incompatibili causano errore, trial arrestati rimangono nel report e valori non osservabili sono null. I costi del client esterno e il modello dichiarato non vengono presentati come misure certificate.

La fase non introduce autenticazione multiutente o deployment. La protezione è sul confine HTTP locale; SQLite e chi controlla l'host restano fidati. Integrity split, contaminazione generale, antiabuso e pubblicazione appartengono alle fasi successive. La prova offline e quella browser non costituiscono un pilot con un modello reale.
