# Threat model locale — Integrity v1

Gli asset sono leggi/seed/probe test privati, correttezza della sequenza degli esperimenti, submission congelate, provenienza dei risultati e credenziali. Il perimetro è il server loopback con SQLite e client HTTP/browser esterni. I payload dei provider sono dati pubblici costruiti con liste positive. Nessuna API del modello riceve filesystem, terminale, oggetto Session o accesso al database.

Il gestore del laboratorio, host, codice, ambiente e database sono **fidati**. Il partecipante e il suo runner possono essere ostili; nome modello, spesa e comportamento del runner non sono attestati. La persona che svolge anche il ruolo di operatore può vedere i risultati durante l'embargo e la verità dopo il reveal: per valutazioni cieche separare questi ruoli e impedire al partecipante l'accesso all'host privato. I dataset train/development sono pubblici deliberatamente. Si presume SHA-256 resistente alle collisioni e seed/nonce riservati ad alta entropia.

| Minaccia | Controllo implementato | Limite residuo |
| --- | --- | --- |
| Legge/seed nel prompt o nel frontend | Proiezioni positive, DTO test opachi, test con sentinelle, bundle controllato | Il client può aggiungere contenuti esterni; host compromesso fuori perimetro |
| Ricostruzione da hash a bassa entropia o seed pubblici | Commitment salati; derivazione con domini SHA-256; seed radice privato | Seed demo noto, root/nonce divulgato o accesso ai file elimina il segreto |
| Sostituzione del mondo dopo il trial | Manifest conservato prima, commitment del record completo, proof verificabile | Senza pin originario manifest+proof possono essere sostituiti; nessuna firma esterna |
| Leakage anticipato tramite punteggio/replay | Embargo per agente su stato, replay e receipt; leaderboard dopo chiusura | Operatore fidato vede lo score; agenti possono colludere fuori dal servizio |
| Reveal mentre altri investigano | Gate nella transazione SQLite su challenge e sessioni della stessa legge; ritiro persistente | Conoscenza di un altro database/servizio non rilevata automaticamente |
| Riuso test tramite Scientist, builder o alias | Ammissione del catalogo, rifiuto alias e importazioni con indagini preesistenti, una challenge/caso | Equivalenza fisica controllata solo strutturalmente e su griglia finita |
| Contaminazione teorica o divulgazione esterna | Split disgiunti, flag immutabili, esclusione dai ranghi senza perdere grezzi | Auto-dichiarazione/operatore; non si rileva il training del provider o conoscenza occulta |
| Retry/concorrenza alterano budget o misura | CAS, receipt persistenti, prenotazione prima del lancio, nessun retry automatico | Crash consuma un esperimento e può lasciare una misura assente |
| Flood tramite nuove chiavi/token | Quote e rate account persistenti; soglia invalidi; limiti IP/body/AST/esecuzione | Operatore escluso dai rate account; finestra fissa permette burst al confine; identità multiple gestite dall'operatore |
| Codice/formule ostili | AST con operatori ammessi e limiti; nessun eval o strumento del modello; SQL parametrizzato | Non è un sandbox contro codice locale modificato dall'host |
| Manipolazione risultati/audit | Eventi append-only via API, freeze, report incompatibili rifiutati, metriche ricalcolate | SQLite e file CLI modificabili dal gestore; audit non firmato né immutabile contro l'host |
| Furto token | Hash token Arena nel DB, revoca/scadenza, emissione una volta, memoria browser | Nessun TLS pubblico; segreti nell'ambiente/host possono essere letti da processi autorizzati |

Non sono implementati autenticazione pubblica, mitigazione DDoS, anti-Sybil, attestazione di modelli, rilevamento del training sui dati, protezione da estensioni browser ostili, isolamento di rete dei client, trasparenza esterna del registro o verifica generale delle equazioni. Il laboratorio non è ancora distribuibile come servizio competitivo pubblico. Le fasi 9–10 implementano qualità e operatività locali (vedi [operazioni](operations.md)); un deployment richiede un ulteriore controllo del perimetro pubblico e autorizzazione.

Le prove offline, inclusa una baseline che usa solo misure pubbliche, verificano i controlli del software. Il fixture benchmark conosce la legge ed è un oracolo: il suo risultato non è una scoperta scientifica. Nessun trial LLM reale è stato validato nello sviluppo.
