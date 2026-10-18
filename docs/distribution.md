# Fase 11 — verifica della distribuzione

> Historical/advanced engineering reference. For the version 1.0 supported installation start with [Getting started](getting-started.md), [AI connections](ai-connections.md) and [self-hosting](self-hosting.md). Earlier phase statuses describe that earlier revision, not missing release features or a current hosted service.


Zone 0.11.0 conserva benchmark v0.3, Arena BYOA v1, Integrity v1 e schema SQLite 2. Questa fase prova il software distribuito, non la capacità scientifica di un LLM. Nessuna chiamata a provider o download di modelli.

Il repository remoto è privato, `zalaso/Zone`. L'autore ha confermato budget GitHub Actions zero e blocco degli extra prima dell'avvio della CI. Si usano runner standard, senza credenziali provider, segreti Actions o pubblicazione di immagini. Non è un deployment.

## Cosa controlla la prova

`tools/verify_distribution.py` richiede una cartella nuova. In modalità `wheel` crea un virtualenv senza pacchetti di sistema, installa wheel ed extra backend con i vincoli diretti, ed esegue dalla cartella privata nuova, senza importare codice dalla radice del checkout. Verifica la provenienza del modulo dal virtualenv e l'assenza degli SDK OpenAI, Anthropic e Gemini. In modalità `docker` usa un'immagine già costruita, con volume e container dai nomi casuali; verifica UID 10001, filesystem immutabile e stato Docker precisamente `healthy`.

Entrambe le modalità eseguono la demo esistente: Forge, Arena, tre esperimenti e nove chiamate baseline, chiusura, revoca, reveal/proof, benchmark nelle quattro condizioni, aggregazione e report. Poi avviano un server HTTP reale su una porta libera di loopback e controllano health, header, API e accesso negato senza token. Con il bundle verificano anche la pagina iniziale e il diniego dei percorsi privati.

La prova confronta **tutte le righe di tutte le tabelle applicative**, non soltanto conteggi o health. Controlla il replay Arena prima e dopo riavvio, effettua un backup mentre il server è avviato, ripristina su un database nuovo e ripete i confronti. Eventi, punteggi, ricevute, quote, token revocati e casi ritirati devono restare identici. I test unitari dimostrano che una modifica del contenuto viene rilevata anche senza variazione dei conteggi. La concorrenza delle scritture durante backup/WAL resta coperta dalla suite operativa esistente: qui il backup avviene su un server avviato senza esperimenti in corso.

Token casuale solo nell'ambiente del processo; chiavi provider e PYTHONPATH ereditati sono rimossi. Il report stampato usa una lista di campi consentiti: versione, schema, conteggi e risultati dei confronti. Non stampa verità, ID di sessioni, token o impronte dei dati privati. I log di comandi e server rimangono nella cartella privata di verifica, ignorata da Git. Su Windows proteggere la cartella tramite ACL; non condividere i log grezzi. La CI non carica artefatti privati.

I processi nativi avviati dalla prova vengono arrestati; venv e dati restano disponibili. Container e volume creati esclusivamente dalla prova vengono rimossi in uscita, anche in caso di errore: questo volume contiene soltanto fixture ed è temporaneo. I volumi dell'operatore e Compose non sono toccati. Conservare prima del teardown eventuali dati necessari alla diagnosi di un errore Docker; non usare questa procedura su un database operativo.

## Ripetere sul PC

Da PowerShell nella radice, con ambiente di sviluppo installato:

```powershell
.\.venv\Scripts\python.exe -m build --outdir dist
.\.venv\Scripts\python.exe tools/check_release.py --archives dist
.\.venv\Scripts\python.exe tools/verify_distribution.py --mode wheel --wheel dist/hidden_physics_lab-0.11.0-py3-none-any.whl --web-dir frontend/dist --out benchmark_data/distribution-wheel-01
```

Per una nuova prova cambiare il percorso finale. L'installazione può scaricare dipendenze Python, non modelli. Il bundle deve essere già compilato (`pnpm build` nella cartella frontend). Su Linux sostituire il percorso del Python con `.venv/bin/python`.

Su un host con Docker già disponibile:

```powershell
docker build --tag zone:ci .
.\.venv\Scripts\python.exe tools/verify_distribution.py --mode docker --image zone:ci --out benchmark_data/distribution-docker-01
```

La prova Docker di questa fase viene eseguita sul runner Linux GitHub; Docker Desktop non viene installato sul PC. Per utilizzare successivamente il container locale seguire [operazioni](operations.md).

## CI e limiti

Il workflow `.github/workflows/ci.yml` esegue Python 3.11/3.12 su Linux e Windows, lint e suite completa, demo, build/controllo wheel e sdist e installazione pulita con riavvio/restore. Un job separato verifica frontend (tipi, lint, test, build, scansione); un altro costruisce ed esegue Docker con il bundle. Actions sono fissate a commit, permessi `contents: read`, timeout e concorrenza limitati. Dipendenze transitive e immagini base non sono fissate a digest: nessuna promessa di build identiche.

Le prove da runner pulito distinguono regressioni del checkout e problemi dei registri dei pacchetti. Un workflow presente ma non eseguito non costituisce evidenza; risultati e collegamenti alle esecuzioni sono registrati in [verifiche](verification.md). Il budget zero confermato può interrompere Actions se la quota inclusa si esaurisce; non autorizza spese extra.

Restano pilot LLM autorizzato, identità multiutente, hosting/TLS, monitoraggio, prove di carico sul bersaglio e beta pubblica. La fixture ha seed noti e non rappresenta un'indagine cieca; restore e riavvio non ricreano cecità dopo reveal né recuperano scritture successive allo snapshot.
