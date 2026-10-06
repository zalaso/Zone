# Operazioni locali — Zone 0.10

Il perimetro è un host fidato, un processo server e un operatore su loopback. Le modalità `local` e `staging-local` sono etichette operative: non attivano isolamento automatico o configurazioni di sicurezza diverse. Usare cartelle, database, pacchetti e token distinti. Nessun deployment pubblico è stato eseguito.

## Primo avvio dal checkout

Installare come in [CONTRIBUTING](../CONTRIBUTING.md), poi:

```powershell
$env:MPLBACKEND = 'Agg'
$env:MPLCONFIGDIR = Join-Path (Get-Location) 'benchmark_data/mpl-cache'
.\.venv\Scripts\python.exe -m hidden_lab ops demo --out benchmark_data/first-demo
cd frontend
pnpm install --frozen-lockfile
pnpm build
pnpm check:bundle
cd ..
$env:ZONE_OPERATOR_TOKEN = .\.venv\Scripts\python.exe -c 'import secrets; print(secrets.token_urlsafe(32))'
.\.venv\Scripts\python.exe -m hidden_lab serve --db benchmark_data/first-demo/restored.sqlite3 --port 8766 --web-dir frontend/dist
```

Aprire `http://127.0.0.1:8766`. Il token resta nella variabile del terminale e viene inserito nel campo operatore della UI, che non lo salva nello storage browser. Nel selettore scegliere un mondo **train/development**: il caso test usato dalla demo è stato rivelato e ritirato. Per cambiare porta sceglierne una libera; non arrestare processi di altri progetti.

La demo crea split Forge, verifica il pacchetto, esegue una baseline Arena con operatore simulato, chiude/revoca/rivela e verifica la proof sul manifest conservato; prepara il benchmark v0.3, esegue quattro trial fixture, aggrega e scrive il report; prova backup/restore e conteggio della crescita. È una fixture con seed noti, non un'indagine cieca né un LLM. Ogni ripetizione richiede un percorso nuovo. Report in `benchmark_data/first-demo/benchmark/report.md`; tutti i dati della cartella restano privati salvo esportazione esplicita della parte pubblica.

## Configurazione

| Impostazione | Uso |
| --- | --- |
| `ZONE_OPERATOR_TOKEN` | Obbligatorio per `serve`, almeno 32 caratteri, casuale; solo backend/operatore |
| `ZONE_ENV` / `--environment` | `local` predefinito o `staging-local`; cartelle e token separati a cura dell'operatore |
| `--db`, `--world`, `--integrity-pack` | Percorsi privati; mai directory statiche o mount del browser |
| `--web-dir` | Soltanto bundle compilato con `index.html`; estensioni consentite, nessun symlink |
| `--host`, `--port` | Default `127.0.0.1:8765`; `0.0.0.0` richiede `--container-local` e pubblicazione Docker su loopback |
| `--agent-provider`, `--agent-model`, `--allow-real-agent` | Tutti e tre richiesti per abilitare un agente reale; senza flag baseline offline |
| `--agent-max-calls`, `--agent-max-turns`, `--agent-timeout`, `--agent-max-corrections` | Default 20/15/30s/2; budget chiamate separato dal budget esperimenti |
| `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY` | Solo se si autorizza il relativo provider; mai CI, frontend o file tracciati |
| `ZONE_BACKEND_URL` | Proxy Vite per sviluppo; non serve con la build sulla stessa origine |
| `MPLBACKEND`, `MPLCONFIGDIR` | `Agg` per ambiente offline; cache scrivibile separata dai dati |

Zone non carica automaticamente file `.env`; Compose applica le proprie regole di interpolazione. Nessun valore predefinito per credenziali, nessuna chiave provider nell'immagine. Per modelli reali seguire [prima sessione](first-llm-session.md), con autorizzazione successiva e nome modello scelto esplicitamente. La demo non richiede credenziali provider.

## Health e log

`GET /health/live` verifica che il processo risponda. `GET /health/ready` legge un database esistente, controlla versione/checksum delle migrazioni e accesso alle tabelle centrali; restituisce 503 se indisponibile, futuro o incompleto. Non crea un database mancante, non esegue esperimenti né chiama un provider. Un database senza mondi può essere ready: il builder può aggiungerli. Non misura spazio libero, capacità di scrittura o salute del provider. Questi endpoint non richiedono token e sono soggetti al limite di lettura.

I log `zone.operations` sono JSON con soli `event`, `request_id`, `method`, template `route`, `status`, `duration_ms`. Per richieste senza route: `unmatched`. `X-Zone-Request-Id` collega risposta e log. Non sono registrati query, corpi, header, IP, token, stack trace o verità. Uvicorn non registra gli access log raw; i messaggi di avvio restano locali. Un errore interno restituisce un testo ridotto: leggere lo stato/replay prima di ritentare. Il logging ridotto non sostituisce l'audit scientifico privato né conserva dettagli per ogni diagnosi.

Header CSP, nosniff, no-store, referrer e frame policy accompagnano anche gli errori HTTP. Il bundle è servito dopo le route API; nessuna directory di dati è montata. Non usare `--web-dir .` o directory di sviluppo. La scansione delle estensioni non riconosce un segreto scritto intenzionalmente in JavaScript: l'operatore deve approvare il contenuto del bundle.

## Migrazioni e verifica

Versione schema corrente **2**: migrazione 1 adotta lo schema locale fasi 4–8; migrazione 2 aggiunge indici. Il ledger `schema_migrations` conserva nome, SHA-256 SQL e data. Le migrazioni sono additive, atomiche e serializzate da `BEGIN IMMEDIATE`. L'avvio migra automaticamente; per un database importante, arrestare prima il server e fare backup/verifica espliciti:

```powershell
.\.venv\Scripts\python.exe -m hidden_lab ops status --db benchmark_data/first-demo/arena.sqlite3
.\.venv\Scripts\python.exe -m hidden_lab ops check --db benchmark_data/first-demo/arena.sqlite3
.\.venv\Scripts\python.exe -m hidden_lab ops backup --db benchmark_data/first-demo/arena.sqlite3 --out benchmark_data/backups/before-migration.sqlite3
.\.venv\Scripts\python.exe -m hidden_lab ops migrate --db benchmark_data/first-demo/arena.sqlite3
.\.venv\Scripts\python.exe -m hidden_lab ops check --db benchmark_data/first-demo/arena.sqlite3
```

`status/check/migrate` richiedono un file esistente. Schema futuro, colonne/tabelle/trigger inattesi, ledger alterato o relazioni invalide vengono rifiutati. `check` include `integrity_check` e `foreign_key_check`. I database precedenti senza ledger vengono riconosciuti e adottati senza cancellare eventi, receipt, quote, revoche o flag. Non modificare SQL già applicato; aggiungere una nuova migrazione. Non fare downgrade modificando `user_version` o il ledger.

## Backup, restore e recupero

Il backup usa [SQLite Online Backup API](https://docs.python.org/3.13/library/sqlite3.html#sqlite3.Connection.backup), anche con scritture concorrenti/WAL. Non copiare a mano il solo `.sqlite3` di un server in attività. La copia viene verificata; il manifest adiacente conserva versione, data e SHA-256, senza percorsi o verità. Destinazioni nuove, timeout 1–60s, copie incomplete rimosse. Su POSIX i file sono creati con permessi 0600; su Windows verificare ACL della cartella. Non c'è cifratura o autenticazione crittografica: proteggere coppia DB/manifest su supporto controllato, eventualmente cifrato dall'operatore.

```powershell
.\.venv\Scripts\python.exe -m hidden_lab ops backup --db benchmark_data/first-demo/arena.sqlite3 --out benchmark_data/backups/snapshot.sqlite3 --timeout 60
.\.venv\Scripts\python.exe -m hidden_lab ops restore --backup benchmark_data/backups/snapshot.sqlite3 --out benchmark_data/recovery/zone.sqlite3 --timeout 60
.\.venv\Scripts\python.exe -m hidden_lab ops check --db benchmark_data/recovery/zone.sqlite3
.\.venv\Scripts\python.exe -m hidden_lab serve --db benchmark_data/recovery/zone.sqlite3 --port 8766 --environment staging-local --web-dir frontend/dist
```

Il restore non sovrascrive l'originale e conserva stato **alla data dello snapshot**. Per rollback: arrestare il server, conservare una copia dello stato attuale, ripristinare su file nuovo, usare codice compatibile con quella versione schema e verificare replay/receipt in staging. Il ripristino di uno snapshot vecchio può perdere revoche e ritiri successivi: prima di riaprire ruotare token operatore/agente e riconciliare i casi già rivelati con il catalogo e le proof conservati fuori dal database. Non riaprire test in caso di dubbio. Un mondo rivelato non torna scientificamente cieco dopo un restore.

Questo strumento salva il database backend, non tutte le suite private, nonce, registri CLI o file di prova esterni. Conservare separatamente quei file e il pin del manifest originario con gli stessi controlli di accesso. Provare periodicamente il restore in un ambiente separato; non è stata creata un'automazione schedulata.

## Crescita e retention

```powershell
.\.venv\Scripts\python.exe -m hidden_lab ops retention --db benchmark_data/first-demo/arena.sqlite3
```

Mostra byte del file e conteggi di eventi, chiamate, receipt, audit, token e casi; non cancella nulla. La dimensione non include eventuali WAL/SHM. Quota e rate limit limitano parte dell'abuso, non tutta la crescita. Per questa versione conservare il DB attivo, scegliere durata/rotazione dei log a livello host, archiviare backup con accesso controllato e sorvegliare spazio disco. Non rimuovere receipt o eventi attivi: si perderebbero idempotenza, audit e integrità. Una futura purge deve avere policy e test propri. Nessun supporto dichiarato per cluster, worker multipli, filesystem condivisi o failover.

## Container locale

[Dockerfile](../Dockerfile) usa build multistage e utente 10001; [.dockerignore](../.dockerignore) ammette solo file espliciti. Il runtime ha backend e bundle, senza provider SDK o dati privati. [Compose](../compose.yaml) pubblica `127.0.0.1:8766`, volume dati privato, filesystem immutabile, `/tmp` temporaneo e capability rimosse. Il flag `--container-local` non può verificare il mapping di rete: non cambiare la porta in un bind pubblico.

Con Docker già disponibile, da PowerShell nella radice:

```powershell
$env:ZONE_OPERATOR_TOKEN = .\.venv\Scripts\python.exe -c 'import secrets; print(secrets.token_urlsafe(32))'
docker compose build
docker compose run --rm zone ops demo --out /data/demo
docker compose run --rm zone ops restore --backup /data/demo/backup.sqlite3 --out /data/zone.sqlite3
docker compose up -d
Invoke-RestMethod http://127.0.0.1:8766/health/ready
# Verifica UI e API; poi arresta senza eliminare il volume:
docker compose down
```

Non ripetere bootstrap su destinazioni esistenti. Per backup successivi: `docker compose run --rm zone ops backup --db /data/zone.sqlite3 --out /data/snapshot-02.sqlite3`; conservare coppia DB/manifest anche fuori dal volume con accesso controllato. Non usare `down --volumes` su dati da conservare.

**Docker non era installato sull'host di sviluppo: build e runtime del container non sono stati eseguiti localmente.** La CI prepara la prova di build, demo, restore, health e asset su Linux; finché non gira sul repository pubblicato non è evidenza di successo. Tag base e dipendenze transitive non sono bloccati per digest: nessuna promessa di build identiche. La [documentazione ufficiale Docker](https://docs.docker.com/build/building/multi-stage/) descrive la build multistage.
