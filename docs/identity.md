# Identità su invito — fase 13

> Historical/advanced engineering reference. For the version 1.0 supported installation start with [Getting started](getting-started.md), [AI connections](ai-connections.md) and [self-hosting](self-hosting.md). Earlier phase statuses describe that earlier revision, not missing release features or a current hosted service.


Zone dispone di due modalità esplicite: `local` conserva il comportamento del laboratorio personale; `accounts` richiede un account per tutte le API `/v1`, comprese le letture. Non è stato avviato un servizio esterno. TLS, host, monitoraggio, carico e recupero sul bersaglio restano nella fase 14.

## Perimetro e criteri di accettazione

Questa fase introduce account invitati, tre ruoli, chiavi revocabili, sessioni browser, proprietà delle risorse, quote persistenti e amministrazione. Nessun servizio di identità esterno, password, email, registrazione aperta o costo aggiuntivo. Il filesystem del server e chi lo amministra restano fidati.

I controlli richiesti sono: nessun accesso anonimo ai dati in modalità account; nessun bypass tramite i token locali precedenti; nessuna lettura o modifica fra membri diversi; quote riservate prima del lavoro e aggiornate atomicamente; revoca applicata alle richieste successive; nessun dato account o segreto nei payload del modello; compatibilità scientifica e locale, migrazione e restore senza perdita di dati. I test usano soltanto account sintetici e client offline.

| Ruolo | Laboratorio | Arena | Amministrazione |
| --- | --- | --- | --- |
| `member` | Crea indagini e confronti; propone, autorizza ed esegue solo nelle proprie sessioni | Client BYOA con token dell’agente associato al proprio account; lo staff esegue | Nessuna |
| `operator` | Supervisiona le sessioni di tutti, comprese quelle storiche | Gestisce challenge, token e operazioni sui trial | Non gestisce gli account, non crea mondi e non rivela verità private |
| `admin` | Supervisione, creazione mondi e reveal esplicito dopo l’arresto/valutazione | Supervisione e reveal secondo il protocollo | Inviti, ruoli, quote, rotazione, revoca, associazioni e audit |

La proprietà riguarda il contenitore dell’indagine. Il ruolo scientifico `agent` o `operator` di un evento continua a indicare chi propone o autorizza. Un membro umano può ricoprire entrambi nelle proprie sessioni; il modello riceve solo il contratto scientifico e non riceve una credenziale account. In modalità account i token locali di sessione, pur presenti nelle risposte per compatibilità, non attribuiscono accesso e non vengono usati dal browser. Le storie Human vs AI restano separate e il freeze umano resta necessario.

Gli operatori sono personale fidato con supervisione globale, non partecipanti senza privilegi. Train/development e manifest restano contenuti scientifici condivisi con gli account autenticati. Le classifiche Arena chiuse sono condivise; storie e trial richiedono anche la credenziale Arena corretta. I punteggi di test in embargo restano nascosti secondo Integrity v1.

## Chiavi e sessioni

La chiave di accesso è casuale, con 256 bit di entropia, prefisso `zk_`; non è un token del provider. Viene mostrata una volta da CLI o dall’amministrazione web. Il database conserva solo SHA-256, adatto a queste chiavi ad alta entropia: non è un sistema di hashing di password. Durata configurabile fra 60 secondi e 30 giorni, default 30 giorni. Consegnare la chiave tramite un canale sicuro. Non incollarla in chat, prompt, URL, registri o argomenti di processo.

Il browser scambia la chiave con un identificatore opaco in cookie `HttpOnly; Secure; SameSite=Strict; Path=/`, senza Domain e con prefisso `__Host-` su HTTPS. Sessione massima di 8 ore, inattività massima 30 minuti, massimo 8 sessioni per account; scadenza della chiave, disabilitazione o rotazione invalidano anche i cookie. Ruolo/quote aggiornati chiudono le sessioni browser. Il logout revoca il cookie corrente; per revocare anche la chiave API usare rotazione o disabilitazione.

Le scritture con cookie richiedono l’origine esatta configurata e `X-Zone-CSRF`. Il token CSRF resta nella memoria della pagina e si recupera con `/auth/me`; nessuna credenziale viene salvata negli storage JavaScript. Origini estranee e richieste cross-site sono respinte; nessun CORS. L’autenticazione API usa `Authorization: Bearer <chiave>` e non richiede CSRF, poiché non è una credenziale inviata automaticamente dal browser. Cookie e Bearer nella stessa richiesta sono rifiutati. L’host deve coincidere con quello configurato. Il login richiede sempre l’header Origin.

La revoca protegge le richieste successive; non annulla lavoro già autorizzato e iniziato. Un errore non ripete un esperimento. Le proprietà non sono trasferibili fra account. La disabilitazione non cancella eventi o risultati. Il recupero locale dell’amministratore è riservato a chi controlla il database, non esiste un endpoint HTTP di recupero o bootstrap.

Riferimenti progettuali: [sessioni OWASP](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html), [CSRF OWASP](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html), [Python secrets](https://docs.python.org/3/library/secrets.html). Queste misure non costituiscono una certificazione di sicurezza.

## Quote

| Risorsa | Default | Contabilizzazione |
| --- | --- | --- |
| Sessioni | 30 totali | Include entrambe le sessioni di un confronto e i trial Arena |
| Esperimenti | 100 totali | Consumo quando si registra `execution_started`, anche se il lancio fallisce |
| Chiamate al modello gestito | 50 totali | Prenotazione prima della chiamata, incluse correzioni, timeout e errori |
| Letture / scritture / lanci | 120 / 30 / 10 per minuto | Finestre SQLite condivise fra processi e persistenti al riavvio |
| Login | 10 per minuto e IP | IP conservato come hash; anche tentativi falliti |

Quote modificabili dall’amministratore; non si azzerano con logout, rotazione, riavvio o modifica. Non sono budget monetari o quote giornaliere. Per ampliare un budget si aumenta il tetto totale. I limiti scientifici della sessione e quelli Arena continuano ad applicarsi: vale il vincolo più restrittivo. Il logout è escluso dalla quota di scritture dell’account, così una quota zero non impedisce di chiudere il cookie. Restano anche i limiti per IP del processo, che possono limitare utenti dietro lo stesso proxy. Il proxy e i limiti dell’host andranno configurati nella beta.

Gli esperimenti e le chiamate sono addebitati al proprietario anche quando interviene lo staff. Il personale che usa sessioni storiche senza proprietario consuma le proprie quote. La creazione dei due partecipanti di un confronto è atomica: se manca quota, nessuna sessione e nessun consumo parziale. Le quote delle chiamate si riferiscono al modello gestito dal server: il laboratorio non può contabilizzare né certificare le chiamate e i costi di un client BYOA esterno.

## Primo avvio locale con account

Richiede l’extra `backend`, dipendenze frontend installate e bundle compilato. Dalla radice del repository, PowerShell. Questi comandi sono per un laboratorio di prova locale: nessuna inferenza reale. Usare percorsi nuovi.

```powershell
cd C:\path\to\Zone
.\.venv\Scripts\python.exe -m hidden_lab forge generate --level 1 --budget 3 --private benchmark_data\accounts\world.json --manifest benchmark_data\accounts\manifest.json
.\.venv\Scripts\python.exe -m hidden_lab identity init --db benchmark_data\accounts\zone.db --handle guido
.\.venv\Scripts\python.exe -m hidden_lab serve --db benchmark_data\accounts\zone.db --world benchmark_data\accounts\world.json --auth-mode accounts --public-origin http://127.0.0.1:8765 --local-cookies --web-dir frontend\dist
```

Aprire `http://127.0.0.1:8765`, inserire la chiave mostrata dal bootstrap, aprire **Amministrazione account** e creare gli inviti. Non reindirizzare l’output di `identity init` in un log. Il vecchio `ZONE_OPERATOR_TOKEN` non è necessario in questa modalità. Senza opzioni provider si usa la baseline affine, chiaramente indicata come offline. La CLI ChatGPT con il piano continua a essere un percorso distinto dal modello gestito web.

`--local-cookies` è un’eccezione esplicita consentita solo per HTTP loopback. Per una futura beta servono origine HTTPS e cookie Secure, senza questa opzione; il server dovrà stare dietro un proxy fidato sulla stessa origine. La CLI mantiene il bind locale; l’opzione container esistente non è un’autorizzazione a esporre il servizio. Non usare `vite dev` su un’altra origine per simulare la sicurezza della distribuzione.

Nella UI: **Aggiorna utilizzo** rilegge quote e consumo; **Le mie sessioni** elenca le proprie risorse. I replay scientifici continuano a chiamarsi “pubblici” perché sono visibili al modello: l’accesso HTTP è comunque limitato al proprietario e allo staff. Il membro non deve incollare token di ruolo per continuare la propria indagine.

## Amministrazione e migrazione

Schema SQLite **3**, migrazione additiva `invited_accounts`; benchmark v0.3, Arena v1 e Integrity v1 invariati. I checksum delle migrazioni 1–2 non cambiano. Prima di migrare un database personale: fermare il server e fare un backup privato con la versione corrente compatibile. Il bootstrap inserisce il primo admin solo se non esistono account. Un database con account rifiuta l’avvio locale; un processo locale ancora attivo interrompe le nuove API dopo il bootstrap. Non esiste un’opzione di downgrade all’accesso anonimo.

Le vecchie sessioni non vengono attribuite automaticamente. Sono accessibili solo allo staff. Un admin può adottare esplicitamente una sessione singola tramite `POST /v1/admin/sessions/{id}/assign` con `{"account_id":"..."}`; consuma una quota sessione del destinatario. Confronti e trial Arena storici non sono adottabili, per evitare un’attribuzione parziale delle risorse collegate. Le nuove risorse acquisiscono il proprietario nella transazione di creazione.

Recupero locale di un amministratore esistente, anche dopo scadenza della chiave:

```powershell
.\.venv\Scripts\python.exe -m hidden_lab identity recover-admin --db benchmark_data\accounts\zone.db --handle guido
```

Emette una nuova chiave, riabilita l’admin e revoca i suoi cookie. Non consente di promuovere un membro. L’ultimo admin attivo non può essere disabilitato o demansionato via HTTP. La gestione account non permette cancellazione o azzeramento dei contatori.

API sulla stessa origine; tutti i percorsi sotto `/v1`:

| Metodo e percorso | Funzione |
| --- | --- |
| `GET /auth/config` | Solo modalità, pubblico |
| `POST /auth/login` | Scambio chiave/cookie; solo login pubblico |
| `GET /auth/me`, `POST /auth/logout` | Profilo ridotto/CSRF e logout |
| `GET /my/sessions?after=0` | Proprie risorse, pagine di 100 |
| `GET/POST /admin/accounts` | Elenco paginato / invito |
| `POST /admin/accounts/{id}` | Corpo esatto: ruolo, enabled booleano, tutte le quote |
| `POST /admin/accounts/{id}/rotate` | Nuova chiave, `ttl_seconds` esplicito |
| `POST /admin/accounts/{id}/arena/{agent_id}` | Associa un agente nuovo, prima dei trial; corpo `{}` |
| `POST /admin/sessions/{id}/assign` | Adozione esplicita di una vecchia sessione singola |
| `GET /admin/audit?after=0` | Audit paginato senza chiavi, cookie, CSRF, corpi o verità fisiche |

Gli account paginati espongono ID, handle, ruolo, stato, scadenza, quote e consumo; mai hash delle credenziali. I log HTTP conservano solo campi consentiti e template delle route, non ID negli URL grezzi. Gli eventi scientifici non contengono account ID o chiavi. Non registrare volontariamente segreti nel testo libero di ipotesi, motivazioni o risposte: quel testo viene condiviso con il modello.

Per BYOA si aggiunge `Authorization: Bearer <chiave account>` agli header Arena v1 e al token `za_` già esistente. `ArenaClient(transport, token, account_key=...)` supporta esplicitamente la doppia credenziale, senza inserirla in `model_request`. Prima dei trial lo staff registra l’agente, l’admin lo associa al destinatario e gli consegna il token. Una credenziale `za_` di un altro account è rifiutata, anche se valida. La console web Arena è riservata allo staff; il membro usa il client BYOA.

Backup e database includono hash, proprietà e audit: restano dati privati. Il restore preserva lo snapshot, non le revoche successive. Prima di riaprire un backup vecchio, riconciliare revoche e ruotare le chiavi; conservare quel backup in luogo protetto. I file SQLite non devono entrare nel bundle, nel repository o negli artefatti pubblici.

## Verifica e limiti

```powershell
$env:MPLCONFIGDIR = Join-Path (Get-Location) 'benchmark_data/test-cache'
.\.venv\Scripts\python.exe -m unittest discover -s tests
.\.venv\Scripts\python.exe tools\verify_identity.py --out benchmark_data\identity-demo-new
.\.venv\Scripts\python.exe -m tools.verify_identity_browser --out benchmark_data\identity-browser-new
```

Ogni cartella di demo deve essere nuova. La prova in processo crea quattro account sintetici, esegue un’indagine con due lanci e sette chiamate alla baseline offline, controlla isolamento/rotazione/revoca e confronta tutte le tabelle dopo restore. Il seed della demo è noto: nessuna evidenza su un LLM reale o sull’apprendimento. La prova browser richiede Edge già installato (oppure `ZONE_BROWSER_EXECUTABLE` per un Chromium locale), bundle compilato e Playwright già installato; non scarica browser. Avvia e arresta un server solo loopback, non riusa dati dell’utente.

Questa fase non introduce SSO, MFA, verifica di identità personale, recupero via email, anti-Sybil generale o infrastruttura distribuita. Non controlla quanto spende un agente esterno e non dà accesso pubblico ad Arena. Va ripetuta la verifica sul futuro host con TLS, utenti invitati e condizioni operative della fase 14. Il primo pilot reale della fase 12 resta una sola indagine CLI, non una validazione del benchmark o del percorso multiutente con LLM reale.
