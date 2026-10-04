# Zone Arena locale — BYOA v1

La fase 7 aggiunge **Bring Your Own Agent** alla stessa macchina a stati, allo stesso simulatore e alla stessa valutazione scientifica. Il client esterno invia richieste, ipotesi, conclusione e submission; l'operatore decide ed esegue ogni esperimento. La UI ha una scheda **Zone Arena** per challenge, credenziali, decisioni, replay, risultati e classifiche. Non avvia un modello.

Arena v1 usa solo **esplorazione**. L'operatore può approvare o rifiutare, non modificare parametri o dare suggerimenti teorici. Domande e verifiche preregistrate restano disponibili nelle modalità del laboratorio. Questa restrizione rende il confronto tra agenti più leggibile; non prova di avere eliminato ogni variabile confondente. Il numero di chiamate al modello e le impostazioni del client esterno non sono attestati dal server.

## Prova completamente offline

Servono gli extra già usati dal backend, senza nuovi servizi o librerie. Dalla radice:

```powershell
.\.venv\Scripts\python.exe -m hidden_lab forge generate --level 1 --seed 87523 --budget 3 --private benchmark_data/arena-demo/world.json --manifest benchmark_data/arena-demo/manifest.json
.\.venv\Scripts\python.exe -m hidden_lab forge check --private benchmark_data/arena-demo/world.json --manifest benchmark_data/arena-demo/manifest.json
.\.venv\Scripts\python.exe -m hidden_lab arena demo --db benchmark_data/arena-demo/zone.sqlite3 --world benchmark_data/arena-demo/world.json
```

Scegli percorsi nuovi. La demo rifiuta un database esistente. Usa FastAPI TestClient in processo, il client BYOA, una baseline affine costruita soltanto da osservazioni pubbliche e un **operatore simulato esplicito**. Non apre socket, non legge credenziali, non chiama provider, non rivela il mondo. Chiude la challenge e revoca il token dopo scoring. Il file del mondo entra esclusivamente nel server; non viene passato alla baseline. I dati privati e il database sono in una cartella ignorata da Git.

## Avvio con operatore umano

In un primo terminale, usa un mondo Forge nuovo, senza seed pubblico per un pilot cieco:

```powershell
.\.venv\Scripts\python.exe -m hidden_lab forge generate --level 1 --budget 3 --private benchmark_data/arena-pilot/world.json --manifest benchmark_data/arena-pilot/manifest.json
$env:ZONE_OPERATOR_TOKEN = [Convert]::ToHexString([Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
Set-Clipboard $env:ZONE_OPERATOR_TOKEN
.\.venv\Scripts\python.exe -m hidden_lab serve --db benchmark_data/arena-pilot/zone.sqlite3 --world benchmark_data/arena-pilot/world.json --port 8765
```

In un secondo terminale:

```powershell
cd frontend
pnpm install --frozen-lockfile
pnpm dev
```

Apri `http://127.0.0.1:5173/`, scegli **Zone Arena**, inserisci il token operatore e premi **Connetti Arena**. Crea una challenge, registra un agente con nome e modello dichiarato e consegna il token agente al tuo client locale. La credenziale resta soltanto nella memoria della pagina, è mostrata mascherata e può essere dimenticata. Il token non deve entrare in prompt, URL, file del repository o registri. La registrazione non chiama il modello dichiarato.

Il client crea il proprio trial; premi **Aggiorna Arena** e aprilo. Per ogni richiesta occorrono **Approva richiesta Arena**, **Conferma esplorazione Arena**, **Esegui esperimento Arena**, in tre azioni separate. Il silenzio non approva. Il client deve attendere e rileggere lo stato, senza produrre altre richieste durante l'attesa. Puoi rifiutare o arrestare. Dopo la conclusione il server pubblica sei probe, con categoria pubblica; il client consegna le previsioni numeriche e, facoltativamente, AST sicuro e sigma. Il server congela la submission prima di valutare.

Chiudi la challenge quando tutti i trial hanno un risultato o sono arrestati. I partecipanti possono allora consultare la leaderboard. Il reveal richiede chiusura, token operatore e conferma esplicita; resta bloccato se esiste un'altra challenge aperta sullo stesso mondo. Un mondo già rivelato tramite il backend non può essere riusato per una nuova challenge. I mondi Build a Universe sono esclusi, perché l'autore conosce la legge.

## Contratto e client

`GET /v1/arena/contract` pubblica istruzioni, schema di risposta, versione dei messaggi, ruoli e politica. `GET /v1/arena/challenges` pubblica solo apparato e regole. Le altre route richiedono `X-Zone-Arena-Version: 1` e `X-Zone-Token`; le mutazioni anche `Idempotency-Key`, 8–128 caratteri `[A-Za-z0-9_.:-]`. Versione mancante o diversa: `426`. Le mutazioni della sessione richiedono `expected_version`, pari al `version` appena letto. Corpo JSON UTF-8 massimo 64.000 byte, senza campi inattesi o chiavi duplicate.

| Route, sotto `/v1/arena` | Ruolo | Corpo / risultato |
| --- | --- | --- |
| `POST /challenges` | operatore | `world_id`, `name`; opzionali `max_messages` (3–100, default 30), `max_points` (2–25, default 9) |
| `POST /agents` | operatore | `name`, `model`; opzionali `kind`, `quotas`, `ttl_seconds`; restituisce il token una volta |
| `GET /agents` | operatore | Metadati, quote consumate, ID dei token, scadenza e revoca; mai credenziali |
| `POST /agents/{id}/tokens` | operatore | `{}` o `ttl_seconds`; token aggiuntivo senza azzerare le quote |
| `POST /tokens/{id}/revoke` | operatore | `{}`; revoca immediata e persistente |
| `POST /sessions` | agente | `{"challenge_id":"..."}`; un trial per agente/challenge |
| `GET /sessions/{id}` | proprietario / operatore | Stato e replay pubblico ordinato, quote e risorse; nessuna storia altrui |
| `GET /challenges/{id}/trials` | agente / operatore | Propri trial, oppure tutti per l'operatore |
| `POST /sessions/{id}/messages` | ruolo del messaggio | `expected_version`, `message`, validazione core |
| `POST /sessions/{id}/run` | operatore | `expected_version`, `request_id` |
| `POST /sessions/{id}/submission` | agente proprietario | `expected_version`, `submission` |
| `POST /sessions/{id}/score` | operatore | `expected_version`; solo ripresa di scoring pendente |
| `POST /sessions/{id}/stop` | operatore | `expected_version`, `reason`: `operator_stop` / `interrupted_execution` |
| `POST /challenges/{id}/close` | operatore | `{}`; tutti i trial devono essere terminati |
| `GET /challenges/{id}/leaderboard` | operatore; agente dopo chiusura | Metriche, classifiche distinte e trial grezzi |
| `GET /audit?after=0` | operatore | Massimo 100 record, continuare da `next_after` |
| `POST /sessions/{id}/reveal` | operatore | `expected_version`, `confirm: "reveal"`; registra la decisione |
| `GET /sessions/{id}/reveal` | operatore dopo reveal | Record privato e audit scientifico |

Submission minima:

```json
{"predictions":[{"probe_id":"p01","ax":0,"ay":0}]}
```

Occorre una riga per **ogni** probe, nel suo ordine; i valori devono essere finiti nei limiti core. `law_ast_json` e `uncertainty_sigma` sono opzionali e seguono [identificazione](identification.md). Non si eseguono formule o codice del modello.

`hidden_lab.arena_client.ArenaClient` usa un transport HTTPX con timeout esplicito, oppure TestClient. Esempio di collegamento per un client esterno, senza chiamata a un modello:

```python
import os
import uuid
import httpx
from hidden_lab.arena_client import ArenaClient

with httpx.Client(base_url="http://127.0.0.1:8765", timeout=30) as transport:
    arena = ArenaClient(transport, os.environ["ZONE_ARENA_TOKEN"])
    trial = arena.write("sessions", {"challenge_id": "<ID challenge>"}, str(uuid.uuid4()))
    snapshot = arena.read("sessions/" + trial["session_id"])
```

`model_request(snapshot, settings, remaining_calls)` costruisce un `ModelRequest` tramite il builder pubblico esistente e gli adapter multi-provider già presenti. Ammesso solo in `discovering` o `awaiting_submission`. Il payload include apparato, contratto, storia pubblica e budget; una proiezione positiva esclude metadati account, token e campi privati aggiunti al DTO. Non passare `snapshot` intero al provider. Il modello non riceve README, codice, record del mondo, seed, schedule privata o oggetti Session. Il processo del client resta sotto il controllo del partecipante: l'API non può attestare cosa un programma BYOA faccia fuori dal laboratorio.

Un pilot con un vero modello richiede ancora un runner del partecipante con budget di chiamate, timeout, correzioni limitate e impostazioni registrate. Può riusare gli adapter esistenti; non è stata eseguita una chiamata reale durante lo sviluppo di Arena. La baseline e i messaggi sintetici dei test verificano il software, non la capacità di scoperta.

## Quote, idempotenza e audit

Quote default per **account agente**: 4 trial, 100 richieste di scrittura autenticate, 12 esperimenti. Configurabili alla registrazione tramite `quotas: {"sessions":4,"requests":100,"experiments":12}`, entro 100/10.000/400. Richieste invalide, incluso JSON malformato con header validi, consumano la quota richieste; replay dello stesso receipt non la consuma. Le letture sono limitate dal rate limit IP esistente. Le quote non si azzerano al riavvio, all'emissione di un token o alla revoca. Un trial nuovo richiede quote residue sufficienti per budget e massimo messaggi della challenge. Account creati dall'operatore sono identità locali, non una difesa contro identità multiple.

Token casuali: soltanto hash SHA-256 nel database, durata default 24 ore, configurabile 60 secondi–30 giorni. Scadenza e revoca vengono ricontrollate nelle transazioni. L'emissione restituisce il segreto una volta: il receipt persistente contiene `token: null`. Se la risposta con la credenziale si perde, revoca quel token tramite il suo ID ed emettine un altro. Non è recuperabile dal database.

I receipt sono indicizzati per account e hash della chiave. Stessa chiave, stesso percorso e corpo normalizzato: risposta registrata; stessa chiave con contenuto diverso: `409`. La rotazione del token mantiene questo spazio di idempotenza, ma un token revocato non può leggere receipt. Mutazioni, quote e receipt sono atomici in SQLite e funzionano tra due istanze dell'app sullo stesso file. CAS impedisce scritture su versioni obsolete.

`run` registra e addebita `execution_started` prima del simulatore. Un receipt `202` è persistito prima di uscire dalla transazione; completamento di osservazione e receipt `200` avvengono insieme. Crash, timeout o perdita della risposta non possono rieseguire il lancio: un replay `202` restituisce la prenotazione, non riavvia il lavoro. Rileggi lo stato; se resta `execution_started`, arresta con `interrupted_execution`. La stessa regola congela la submission prima dello scoring; solo `/score` può riprendere una valutazione pendente. Le risposte dei receipt sono snapshot: `GET /sessions/{id}` dà lo stato e i conteggi aggiornati. Il client e la UI non fanno retry automatici.

L'audit append-only registra sequenza, tempo, account/operatore, route o completamento, stato HTTP e hash della chiave. Registra anche risposte invalide autenticate e interruzioni del lavoro. Non memorizza corpi, credenziali, eccezioni private o valori di verità. Rifiuti prima dell'autenticazione e blocchi del rate limit non entrano nell'audit Arena; quote già esaurite non creano nuovi receipt illimitati. Non è un audit crittografico contro chi modifica SQLite.

## Leaderboard e limiti

Ogni challenge fissa hash del mondo e dei probe, versione Arena/scorer/griglia, budget, massimo messaggi, massimo punti e politica di esecuzione. I trial salvano il riferimento alla stessa configurazione. Cambiamenti o incongruenze rifiutano il report con `422`. Non si mescolano mondi o challenge. La legge privata è controllata tramite hash del record, non inclusa nel DTO.

Otto classifiche indipendenti: RMSE numerico complessivo, interpolation, extrapolation, RMSE funzionale AST, nodi AST, dipendenze omesse, dipendenze spurie, NLL di calibrazione. Valori minori prima, parità allo stesso rango; metriche mancanti escluse. **Nessun punteggio combinato.** Una complessità minore, da sola, non identifica una legge corretta. Restano disponibili i punteggi grezzi, errori massimi/normalizzati per categoria, calibrazione, stato d'arresto, numero di osservazioni/esperimenti/messaggi e richieste invalide per trial. I consumi account sono presentati separatamente. Costi, token e chiamate al modello del client esterno sono `null`, perché non osservabili dal server; il modello è una dichiarazione non verificata.

Arena si appoggia a `SQLiteRepository`; un repository diverso continua a funzionare per il laboratorio, ma deve fornire una persistenza Arena dedicata per esporre queste route. Server e frontend restano su loopback. Non ci sono ancora identità pubbliche, TLS, storage distribuito, migrazioni versionate, pulizia dei receipt o protezioni contro un host/client compromesso. L'integrità competitiva completa, split pubblici/privati, contaminazione, duplicati e abuso sono **fase 8**. Qualità open source e preparazione alla distribuzione sono **fasi 9–10**. Nessun deployment è stato effettuato.
