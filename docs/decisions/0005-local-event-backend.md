# ADR 0005 — Backend locale con eventi e reveal esplicito

Stato: adottata nella fase 4; estende la decisione 0001.

FastAPI resta un adapter HTTP opzionale. Le regole di protocollo, l'integratore e il valutatore scientifico restano moduli indipendenti dal web. Un riduttore ricostruisce la macchina a stati dagli eventi pubblici; `SessionRepository` delimita la persistenza e SQLite è la prima implementazione. Ogni comando usa `expected_version` e un append atomico: due richieste concorrenti non possono applicare la stessa versione.

L'esecuzione è deliberatamente in due commit: `execution_started` consuma subito il budget, poi il simulatore produce l'osservazione. Un crash fra i commit non avvia automaticamente un secondo esperimento. L'operatore può arrestare esplicitamente la sessione; non viene fabbricata una misura mancante. Anche la submission è salvata prima dello scoring; un scoring interrotto può essere ricalcolato senza sperimentazione.

Il token operatore proviene dall'ambiente, il token agente è generato per sessione e memorizzato solo come hash. Nessun cookie o CORS; avvio limitato a loopback. I registri pubblici sono proiettati per lista positiva e il record privato è restituito solo dopo risultato o arresto, conferma esplicita e autenticazione operatore. Il rate limit è locale e per processo: quote distribuite, revoca, utenti pubblici e protezione competitiva sono demandati alle fasi 7–8.
