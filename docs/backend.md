# Backend locale — fasi 4–7

Il backend espone con FastAPI il laboratorio già esistente. Simulazione, validazione dei messaggi e valutazione scientifica restano nei moduli Python del core; la fase 6 aggiunge un agente del server con baseline offline predefinita e adapter reali soltanto su configurazione esplicita. Vedi [modalità e nuove route](public-modes.md). SQLite conserva il record privato del mondo, gli eventi append-only, l'hash del token agente e i risultati. `SessionRepository` delimita le operazioni di persistenza e `create_app(repository=...)` permette di sostituire SQLite senza cambiare le route. Non è ancora un servizio pubblico multiutente.

## Avvio locale

Installa l'extra e genera un mondo Forge come in [World Forge](world-forge.md). Usa un token casuale solo nel processo locale:

```powershell
.\.venv\Scripts\python.exe -m pip install -e '.[backend]'
$env:ZONE_OPERATOR_TOKEN = [Convert]::ToHexString([Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
.\.venv\Scripts\python.exe -m hidden_lab serve --db benchmark_data/backend/zone.sqlite3 --world benchmark_data/forge-demo/world.json --port 8765
```

Il comando ascolta soltanto su `127.0.0.1`, non apre browser e non avvia modelli o chiamate API. La cartella `benchmark_data/` è ignorata da Git. Conserva il token per le richieste dell'operatore: non inserirlo in file del repository o nei messaggi inviati a un LLM. Alla riapertura puoi omettere `--world` se il record è già in SQLite; se lo passi di nuovo, il backend ne verifica l'identità. Il database contiene segreti fisici: va trattato come file privato.

Le prove automatiche usano [FastAPI TestClient](https://fastapi.tiangolo.com/tutorial/testing/) in processo, senza socket o server avviato. L'extra `backend` installa anche HTTPX per questi test. Non sono state effettuate chiamate a modelli reali.

## Contratto HTTP v1

Ogni mutazione accetta solo `application/json` UTF-8 (massimo 64 KiB), rifiuta chiavi JSON duplicate e campi inattesi e richiede `X-Zone-Token`. Le operazioni su una sessione richiedono `expected_version`, pari all'ultimo `seq` visto: una versione obsoleta restituisce `409`. Il token operatore viene letto da `ZONE_OPERATOR_TOKEN` e non salvato nel database; `POST /v1/sessions` restituisce **una sola volta** un token agente casuale, di cui è memorizzato solo l'hash. Un token agente non può decidere, eseguire o rivelare il mondo. I token sono header, non cookie; CORS non è abilitato.

| Metodo e route | Ruolo | Scopo |
| --- | --- | --- |
| `GET /v1/worlds` | pubblico | Manifest ridotti; mai configurazioni o probe. |
| `POST /v1/sessions` | operatore | Corpo `{"world_id":"..."}`; crea sessione, apparato pubblico e token agente. |
| `GET /v1/sessions/{id}` | pubblico | Stato, versione, budget e riferimenti pendenti. |
| `GET /v1/sessions/{id}/events?after=0` | pubblico | Replay di massimo 100 eventi; continuare da `next_after`. |
| `POST /v1/sessions/{id}/messages` | agente/operatore secondo il tipo | Corpo `{"expected_version":1,"message":{...}}`; riusa il protocollo esistente. |
| `POST /v1/sessions/{id}/run` | operatore | Corpo `{"expected_version":N,"request_id":"e1"}`; solo dopo approvazione e modalità esplicita. |
| `POST /v1/sessions/{id}/stop` | operatore | Corpo `{"expected_version":N,"reason":"operator_stop"}` o `"interrupted_execution"`. |
| `POST /v1/sessions/{id}/submission` | agente | Corpo `{"expected_version":N,"submission":{...}}`; dopo `conclusion`, prima del reveal. |
| `POST /v1/sessions/{id}/score` | operatore | Riprende solo una valutazione rimasta pendente dopo submission salvata. |
| `GET /v1/sessions/{id}/result` | pubblico, dopo scoring | Metriche numeriche e di identificazione, senza verità dei probe. |
| `POST /v1/sessions/{id}/reveal` | operatore | Corpo `{"expected_version":N,"confirm":"reveal"}`; solo dopo scoring o arresto. |
| `GET /v1/sessions/{id}/reveal` | operatore, dopo reveal | Rilegge record privato e audit. |

I messaggi di scoperta sono quelli documentati nel README: richiesta di esperimento, ipotesi, domanda, risposta, decisione, modalità, previsione e conclusione. Una conclusione valida registra nello stesso commit un `probe_challenge` con soli stati e categorie. La submission usa il [contratto scientifico comune](identification.md): previsioni numeriche obbligatorie, AST e incertezze facoltativi. Il backend salva l'evento di submission **prima** di consultare la verità e registra il risultato in un secondo commit. Un'interruzione nel mezzo lascia `scoring_pending`: `/score` ricalcola deterministicamente senza richiamare un modello né eseguire esperimenti.

## Arresti, replay e confini

`run` salva `execution_started` e consuma il budget **prima** di invocare il simulatore. Il secondo commit salva osservazione ed eventuale verifica preregistrata. Dopo un crash fra i due commit il replay mostra `execution_started`; nessun `run` successivo può ripetere il lancio. L'operatore può fermare la sessione con `interrupted_execution`, quindi fare reveal esplicito. La ripresa o riconciliazione fisica di un lancio interrotto resta futura: il server non inventa una misura.

Gli eventi pubblici sono proiettati con una lista positiva di campi. Record del mondo, seed, legge, accelerazioni vere e griglia funzionale rimangono in SQLite e vengono restituiti solo dalla route di reveal con token operatore e conferma. Il reveal è permanente per quella sessione; non è disponibile prima di un risultato o di un arresto. Le risposte di errore non includono eccezioni del simulatore o segreti.

Il rate limit locale è per IP e processo: 120 letture, 30 scritture e 10 richieste `run` per 60 secondi, con `429` e `Retry-After`. Non sostituisce quote distribuite, identità utente, TLS, backup o protezione contro un host compromesso. Il server resta vincolato a loopback. La fase 7 aggiunge [Arena BYOA v1](arena.md) con token revocabili e quote persistenti nel proprio namespace; i token storici del laboratorio mantengono il comportamento originario. Autenticazione pubblica e deployment restano futuri; i controlli locali di integrità sono nella fase 8. Gli ID delle sessioni sono casuali e rendono i registri leggibili tramite link, ma non sono un controllo di accesso per informazioni riservate: solo eventi già pubblici sono leggibili senza token.

## Arena

Le sessioni Arena richiedono ownership e header di versione anche per la lettura: le route storiche `/v1/sessions` le rifiutano con `404`. Le challenge Arena aperte bloccano il reveal di quel mondo anche nelle sessioni del laboratorio. Le route Arena sono abilitate con `SQLiteRepository`; la sua interfaccia tradizionale resta utilizzabile senza Arena con un repository alternativo. La [guida Arena](arena.md) documenta protocollo, quote, receipt, audit e limiti.

## Catalogo Integrity

`serve --integrity-pack PATH` importa pacchetti validati senza resettare ritiro o flag; SQLite conserva la verità privata. Train/development hanno endpoint pubblici, il test ha solo ID/commitment; i casi test sono riservati ad Arena. Il reveal è controllato nella transazione di append: challenge chiuse e nessuna indagine aperta sulla stessa legge, poi ritiro. Alias, importazioni contaminate e sessioni storiche sul test vengono rifiutati. Schema e formati benchmark restano compatibili. Dettagli, quote account e confini in [Integrity](integrity.md). Vite consente `ZONE_BACKEND_URL` per un backend loopback su porta diversa, senza modificare il default 8765.
