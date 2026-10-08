# Verifiche locali e distribuzione

## Fase 11 — 8 ottobre 2026

Zone **0.11.0**, protocolli benchmark v0.3/Arena v1/Integrity v1 e schema SQLite 2 invariati. Repository **privato** `zalaso/Zone`, creato dopo conferma dell'autore di budget Actions zero e blocco degli extra. [Esecuzione GitHub 37821050036](https://github.com/zalaso/Zone/actions/runs/37821050036), commit di codice `b32af33d34a62fa5ef43d529e53771d8f8751913`: **sei job completati con successo**, Python 3.11/3.12 su Ubuntu e Windows, frontend e container Linux. La documentazione dei risultati è aggiornata successivamente senza modificare il codice verificato. Nessuna API LLM, credenziale provider, modello scaricato, immagine pubblicata o deployment.

Prove locali: **207 test Python passati**, 184,889 s, nessuno skip; **15 test frontend** e **2 test Node**, Ruff, tipi, lint AST, build Vite, scansione bundle e controllo wheel/sdist verdi. I quattro nuovi test controllano rilevazione delle variazioni con conteggi invariati, report senza impronte private, rifiuto di destinazioni esistenti, rimozione di credenziali provider/PYTHONPATH e confine HTTP locale. La matrice CI esegue l'intera suite, la demo, il build/check archivi e una nuova installazione wheel per ogni combinazione.

Prova wheel reale locale in `benchmark_data/distribution-wheel-02`: virtualenv pulito, modulo caricato dal pacchetto installato, nessun SDK provider; server Uvicorn su loopback e bundle reale. Demo originale Forge/Arena/benchmark completa, poi riavvio e backup a server avviato/restore su file nuovo. Stesse righe di tutte le tabelle applicative e stesso replay API, schema 2, **25 eventi / 24 ricevute / 28 audit / 1 token revocato / 3 casi Integrity**. Il job Docker ripete lo stesso ciclo su volume temporaneo con UID 10001, root filesystem immutabile, capability rimosse, porta loopback e stato `healthy`; container e volume di prova rimossi. Nessun Docker Desktop installato sul PC. Seed noti e fixture software, nessuna misura di capacità scientifica.

La prima prova del nuovo verificatore ometteva l'header di versione Arena nella richiesta senza token: il server rifiutava il protocollo prima dell'autenticazione. Correzione del verificatore, nuova destinazione locale e nuova CI completa verdi; nessuna modifica al protocollo applicativo. La prima esecuzione GitHub `37820902594` è stata sostituita, non conta come prova verde. Il precedente smoke Edge rimane quello della fase 10: questa fase usa richieste HTTP reali e i test frontend, senza attribuirsi un nuovo smoke browser.

Comandi principali eseguiti dalla radice; rete soltanto per registri pubblici di dipendenze e GitHub, nessun modello:

```powershell
$env:MPLBACKEND = 'Agg'
$env:MPLCONFIGDIR = Join-Path (Get-Location) 'benchmark_data/phase11-mpl'
.\.venv\Scripts\python.exe -m ruff check hidden_lab tests tools
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
.\.venv\Scripts\python.exe -m unittest tests.test_distribution tests.test_deployment -q
$env:PYTHONUTF8 = '1'
.\.venv\Scripts\python.exe -m build --outdir dist/phase11
.\.venv\Scripts\python.exe tools/check_release.py --archives dist/phase11
.\.venv\Scripts\python.exe tools/verify_distribution.py --mode wheel --wheel dist/phase11/hidden_physics_lab-0.11.0-py3-none-any.whl --web-dir frontend/dist --out benchmark_data/distribution-wheel-02
cd frontend
pnpm typecheck
pnpm lint
pnpm test:quality
pnpm test
pnpm build
pnpm check:bundle
cd ..
gh repo create zalaso/Zone --private --description 'Zone: laboratory for discovering unfamiliar physical laws through controlled experiments'
git remote add origin https://github.com/zalaso/Zone.git
git push --set-upstream origin master
gh run view 37821050036 --repo zalaso/Zone --json status,conclusion,jobs
```

Sul runner Linux: `docker build --tag zone:ci .` e `python tools/verify_distribution.py --mode docker --image zone:ci --out benchmark_data/container-verification`. Dati/log/impronte privati non caricati come artefatti CI. Report ridotto conservato localmente; istruzioni e limiti in [distribuzione](distribution.md). Restano pilot autorizzato, identità multiutente e verifica del futuro host/TLS/monitoraggio/carico. Dipendenze transitive e immagini base non sono integralmente fissate; nessuna promessa di build bit-identiche.

## Fasi 9–10 — 6 ottobre 2026

Zone 0.10.0, MIT scelta dall'autore. Verifica finale su Windows/Python **3.14.4**: **203 test Python passati** (123,317 s; nessuno skip), inclusi **22 nuovi test** operazioni/release/configurazioni; **15 test frontend** passati, **2 test Node** dei controlli qualità; Ruff, TypeScript, lint AST, build Vite e scansioni bundle/archivi verdi. La matrice CI Linux/Windows 3.11/3.12 è predisposta, non eseguita sul remoto. Docker non è disponibile sull'host: build/runtime immagine non verificati. Nessuna API reale, credenziale provider, modello scaricato, upload o deployment.

Migrazioni provate su schema precedente completo e parziale, riavvio/idempotenza e due inizializzazioni concorrenti; conservazione di eventi, quote, revoche, receipt, flag e ritiro. Errori di migrazione, relazioni invalide, vincoli rimossi, schema futuro/estraneo e checksum alterati vengono rifiutati senza adozione parziale. Backup WAL con scritture committate/non committate, timeout con cleanup, restore su file nuovo, tampering e rifiuto di sovrascrittura; retention di sola lettura. Health con DB assente/futuro/tabella mancante, nessuna chiamata modello, log/errori a campi consentiti anche su 429, statici senza file privati; CLI rifiuta bind non autorizzato e flag provider incompleti. Configurazioni CI/Compose testate per permessi, pin, loopback e runtime limitato. Wheel/sdist includono MIT e file consentiti, senza dati di esecuzione.

Demo finale `benchmark_data/phase10-final-demo`: pacchetto Forge e controllo, baseline Arena con **3 esperimenti / 3 osservazioni / 9 passi**, scoring, chiusura, revoca, reveal/proof sul manifest conservato; pacchetto benchmark con **4 trial** simulated completati, esperimenti 0/1/1/1, chiamate fixture 3/3/3/4, zero invalidi, aggregazione/report; backup/restore/check e retention. Stato ripristinato: schema 2, 25 eventi, 24 receipt, 28 audit, un token revocato, tre casi Integrity. Seed noti: fixture software, nessuna conclusione sulla capacità di un LLM.

Edge già installato, backend reale su 8766, bundle `frontend/dist` sulla stessa origine: sessione `a4e36d5e9bb2a604035af752cd58df49`, modifica a 0,5s, previsione su tre punti, zero esecuzioni prima del clic, osservazione/verifica, conclusione, submission, risultato, replay pubblico senza verità, reveal esplicito solo da operatore; contesto anonimo senza record privato, storage vuoto, nessun errore JavaScript e nessun overflow a 390px. Bundle 278,11 kB JS / 84,73 kB gzip. Server di prova arrestato; nessun servizio di altri progetti arrestato.

Correzioni durante la verifica: raccolta Vitest ristretta ai test `src`, lasciando separati i test Node; scansione bundle corretta per accettare il nome pubblico `ZONE_OPERATOR_TOKEN` senza accettare valori sospetti; controllo YAML per segreti GitHub reso distinto dal modulo Python `secrets` usato per generare il token sintetico CI. Le ripetizioni finali passano. La scansione resta euristica e non certifica tutti i testi arbitrari.

Comandi eseguiti dalla radice (le ripetizioni della demo usavano cartelle nuove):

```powershell
$env:MPLBACKEND = 'Agg'
$env:MPLCONFIGDIR = Join-Path (Get-Location) 'benchmark_data/test-cache'
.\.venv\Scripts\python.exe -m ruff check hidden_lab tests tools
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
.\.venv\Scripts\python.exe -m hidden_lab ops demo --out benchmark_data/phase10-final-demo
.\.venv\Scripts\python.exe -m hidden_lab ops --help
.\.venv\Scripts\python.exe -m hidden_lab serve --help
.\.venv\Scripts\python.exe -m build --no-isolation --outdir dist
.\.venv\Scripts\python.exe tools/check_release.py --archives dist
.\.venv\Scripts\python.exe -m hidden_lab forge generate --level 1 --seed 87523 --budget 3 --private benchmark_data/phase10-browser/world.json --manifest benchmark_data/phase10-browser/manifest.json
# Token sintetico nell'ambiente; agente offline predefinito:
.\.venv\Scripts\python.exe -m hidden_lab serve --db benchmark_data/phase10-browser/zone.sqlite3 --world benchmark_data/phase10-browser/world.json --port 8766 --web-dir frontend/dist
# In un altro terminale:
cd frontend
pnpm typecheck
pnpm lint
pnpm test:quality
pnpm test
pnpm build
pnpm check:bundle
$env:ZONE_SMOKE_BASE_URL = 'http://127.0.0.1:8766'
$env:ZONE_SMOKE_OPERATOR_TOKEN = '<stesso token sintetico del backend di prova>'
$env:ZONE_BROWSER_EXECUTABLE = 'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
node scripts/smoke.mjs
cd ..
git diff --check
```

Ruff 0.14.10, build 1.3.0 e PyYAML 6.0.3 installati come strumenti di sviluppo; frontend eseguito con wrapper pnpm locale già disponibile (11.19.0), mentre packageManager/CI/container fissano pnpm 10.28.0. Nessun browser/modello scaricato. CI e Docker vanno provati secondo [operations.md](operations.md); pubblicazione futura segue la [checklist](release-checklist.md). File: licenza/metadata/guide/template, workflow e container; nuovi moduli schema/migrations/operations/runtime_ops/static_web/demo_workflow, integrazione CLI/repository/backend; controlli frontend e smoke, 22 test aggiuntivi e pulizia di import inutilizzati segnalati da Ruff. Formati e confine provider benchmark v0.3 restano invariati.

## Consolidamento fasi 0–5 — 4 ottobre 2026

La suite Python completa ha eseguito 129 test senza errori. La suite frontend della fase 5 comprende sei test e la build esegue il controllo TypeScript prima di Vite.

`frontend/scripts/smoke.mjs` verifica il browser reale con backend FastAPI, SQLite e Vite avviati su loopback; nessun endpoint è simulato. La prova usa Edge già installato e un token esclusivamente di test. Il percorso comprende creazione della sessione, modifica della durata, modalità verifica, ipotesi, tre punti preregistrati, controllo che nessun esperimento sia partito prima del clic dell'operatore, esecuzione, misure, conclusione, sei probe, submission, risultato, reveal solo dopo conferma, riapertura del replay pubblico in un contesto browser privo di credenziali. Controlla assenza di storage dei token, assenza di verità privata nel replay e overflow a 390 pixel. La prova è passata. Gli screenshot sono nella cartella ignorata `benchmark_data/web-qa/`.

Per ripetere il test usa un backend di prova separato, con un mondo Forge valido, e Vite sulla porta 5173. Nel terminale del test, dalla cartella `frontend`:

```powershell
$env:ZONE_SMOKE_OPERATOR_TOKEN = '<token del tuo backend locale di prova>'
$env:ZONE_BROWSER_EXECUTABLE = 'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
pnpm test:browser
```

Il test crea una sessione e la rivela: usare un database di prova. Non scarica browser, modelli o chiama provider. I risultati verificano il software, non capacità scientifiche di un LLM. Il controllo del bundle esclude token delle fixture, `secret_grid`, `probe_truth`, `hidden_lab` e percorsi dei dati privati. Non equivale a un audit di accessibilità certificato o a una verifica di sicurezza per deployment pubblico.

## Modalità locali — fase 6, 4 ottobre 2026

Suite completa: **143 test Python passati** (193,916 s), **9 test frontend passati**, controllo TypeScript e build Vite passati. I 14 test delle modalità sono stati rieseguiti sul codice finale (46,531 s), includendo il rifiuto della submission dopo arresto. Il bundle finale pesa circa 264 kB JavaScript, 81 kB gzip; la scansione non trova token delle fixture, `benchmark_data`, `secret_grid` o `probe_truth`. `git diff --check` passa.

`frontend/scripts/smoke-modes.mjs` ha attraversato il browser reale, Vite, FastAPI e SQLite, usando esclusivamente `offline_baseline`: Watch an Agent con tre esperimenti e nove messaggi/chiamate; Human vs AI con freeze umano iniziale, agente su storia separata e due risultati; World of the Day persistito; validazione e registrazione di un AST dell'autore, poi avvio della relativa sessione Scientist. Nessun evento o endpoint è simulato nel browser. Il client dell'agente è una baseline pubblica senza accesso alla verità, distinta da un LLM.

Confronto finale della prova: `8cae20d90cad43ae5d6440faedc2f012`; sessione Watch an Agent: `b464d39e5afd5a2f68c5b7dca2d90ea0`. La risposta umana della prova dichiara zero misure e usa previsioni zero: serve a verificare il freeze e il report, **non** a misurare capacità umane. Il confronto è stato controllato anche a 390 pixel, senza overflow. Screenshot desktop, mobile e confronto sono nella cartella ignorata `benchmark_data/web-qa/`.

La prova browser storica è stata ripetuta dopo le modifiche backend (sessione `d480be7d506b0ec97dfaf6726aeb8cb2`): modifica, previsione preregistrata, esecuzione esplicita, risultato, reveal e replay riaperto senza credenziali passano. I selettori del test distinguono il titolo di risultato della pagina da quello nel replay. Le pagine non conservano token in local/session storage.

I test Python aggiuntivi verificano ordine misura → ipotesi, modifica visibile prima della previsione, rifiuto, input malformato e correzione limitata, errori senza retry di esperimenti, timeout con risposta tardiva ignorata, doppio clic e risposta obsoleta, limiti persistenti di chiamate e turni, parità dei limiti del confronto, scoring/reveal differiti, confronto incompatibile rifiutato, proiezione pubblica in tutte le fasi, conteggi nativi e impostazioni senza campi extra, giorno UTC stabile al riavvio, AST invalidi rifiutati e mondi dell'autore esclusi dal confronto. L'arresto dopo conclusione o freeze conserva la submission, impedisce nuove consegne/scoring e permette di chiudere entrambe le indagini prima del reveal.

Comandi eseguiti per la verifica finale, dalla radice (con server e Vite locali avviati per le prove browser):

```powershell
$env:MPLCONFIGDIR = Join-Path (Get-Location) 'benchmark_data/test-cache'
.\.venv\Scripts\python.exe -m unittest discover -s tests
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_public_modes.py
.\.venv\Scripts\python.exe -m hidden_lab serve --help
cd frontend
pnpm test
pnpm build
$env:ZONE_SMOKE_OPERATOR_TOKEN = '<token del backend di prova>'
node scripts/smoke-modes.mjs
node scripts/smoke.mjs
cd ..
git diff --check
```

Sono disponibili anche `pnpm test:browser:modes` e `pnpm test:browser`. Lo smoke delle modalità rallenta i clic per rispettare il rate limit delle scritture; usare un backend di prova con baseline offline, senza flag per provider reali. Non modificare i sorgenti durante la prova, per evitare che un reload Vite interrompa il flusso; su questa macchina un tentativo intermedio ha incontrato un timeout del browser, mentre la ripetizione completa è passata. Nessun timeout ha ripetuto un esperimento.

Nessuna API reale, credenziale reale, modello scaricato o deployment. Il benchmark v0.3 conserva codice e formato; i suoi test di regressione sono inclusi nella suite. Il pilot con provider reale, la capacità di scoperta, l'integrità competitiva e la distribuzione pubblica rimangono non verificati. I comandi del pilot sono in [modalità locali](public-modes.md).

## Zone Arena — fase 7, 4 ottobre 2026

Verifica finale: **164 test Python passati** (122,627 s), di cui **21 test Arena**, **13 test frontend passati**, controllo TypeScript e build Vite passati. Bundle finale circa 276,53 kB JavaScript, 84,29 kB gzip. Scansione del bundle senza token delle fixture, `benchmark_data`, `generator_seed`, `secret_grid` o `probe_truth`; `git diff --check` passa.

I test Arena coprono ciclo e freeze, otto classifiche separate, categorie dei probe, ranghi ex aequo, valori mancanti e trial arrestati, ownership e blocco di tutte le route storiche, ruoli, versione, chiavi idempotenti e conflitti, token emessi una volta e assenti da SQLite/audit, revoca/scadenza/rotazione, quote persistenti al riavvio e conteggio degli invalidi, crash senza retry del simulatore, ripresa esplicita del solo scoring, due app concorrenti sullo stesso file, simulazione unica durante richieste simultanee e arresto che scarta la misura tardiva. Verificano configurazioni incompatibili, quote di sessioni/esperimenti, ID malformati, payload provider proiettati in scoperta e submission, chiusura/reveal e blocco del reveal storico durante una challenge aperta.

La sequenza documentata `forge generate` → `forge check` → `arena demo` è passata su un mondo nuovo, seed 87523, livello 1, budget 3. Sessione `8c2769d5e8f6ac4108229687707bfece`: tre esperimenti, tre osservazioni, nove chiamate della baseline affine pubblica, submission valutata, challenge chiusa e token revocato. RMSE numerico 0,03099668; interpolation 0,01514973; extrapolation 0,04113483. Questi numeri verificano il percorso offline su quel mondo; non valutano un LLM. La demo usa un operatore simulato esplicito e non fa reveal.

`frontend/scripts/smoke-arena.mjs` è passato in Edge già installato, con Vite, FastAPI e SQLite reali, dopo riavvio del backend sul codice finale. I messaggi dell'agente sono **sintetici**; nessun modello viene chiamato. Sessione `2256f2312e9ff8efb8164b46c7ade653`, challenge `52a72aa64743785f5bf9c1a8dc4415ba`: registrazione UI, trial BYOA, approvazione, modalità e lancio separati, tre misure, ipotesi, conclusione, sei probe, submission, classifiche, chiusura e revoca con successivo `401`. Il test controlla `404` sul replay storico della sessione Arena, storage credenziali vuoto, assenza di verità privata nella pagina, errori browser assenti e nessun overflow a 390 pixel. Screenshot desktop/mobile nella cartella ignorata `benchmark_data/web-qa/`.

La prova browser storica è stata rieseguita con successo (sessione `acb441c6bfe487ede8e0a61a46958604`): modifica, previsione preregistrata, esecuzione, scoring, reveal, replay e mobile. Le modalità della fase 6 hanno test di regressione nella suite completa. Le prove browser usano un database separato; il test storico rivela il suo mondo, quindi Arena deve essere verificata prima o su un mondo differente.

Comandi eseguiti, dalla radice, con server/Vite locali per gli smoke:

```powershell
$env:MPLCONFIGDIR = Join-Path (Get-Location) 'benchmark_data/test-cache'
.\.venv\Scripts\python.exe -m unittest discover -s tests
.\.venv\Scripts\python.exe -m hidden_lab forge generate --level 1 --seed 87523 --budget 3 --private benchmark_data/arena-demo/world.json --manifest benchmark_data/arena-demo/manifest.json
.\.venv\Scripts\python.exe -m hidden_lab forge check --private benchmark_data/arena-demo/world.json --manifest benchmark_data/arena-demo/manifest.json
.\.venv\Scripts\python.exe -m hidden_lab arena demo --db benchmark_data/arena-demo/zone.sqlite3 --world benchmark_data/arena-demo/world.json
cd frontend
pnpm test
pnpm build
$env:ZONE_SMOKE_OPERATOR_TOKEN = '<token del backend locale di prova>'
$env:ZONE_BROWSER_EXECUTABLE = 'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
node scripts/smoke-arena.mjs
node scripts/smoke.mjs
cd ..
git diff --check
```

È disponibile anche `pnpm test:browser:arena`. Per ripetere la preparazione o la demo scegli nuovi percorsi. Una build intermedia ha rilevato il tipo TypeScript troppo restrittivo per una chiave idempotente non UUID; il client ora accetta tutte le stringhe previste dal contratto e build/test finali passano. Non sono state usate credenziali di provider, chiamate API reali, download di browser/modelli o deployment. Il pilot BYOA con un vero modello, i consumi esterni e l'integrità competitiva restano non validati; [stato e prossimi passi](status.md).


## Integrity — fase 8, 4 ottobre 2026

Verifica finale: **181 test Python passati** (103,596 s), inclusi **17 test Integrity**, **15 test frontend**, controllo TypeScript e build Vite. Bundle 278,11 kB JavaScript / 84,73 kB gzip: la scansione non trova credenziali sintetiche, sentinelle private, `probe_truth`, `secret_grid`, `generator_seed` o percorsi dei pacchetti privati. `git diff --check` passa.

I test aggiuntivi coprono split disgiunti e deterministici, manifest senza verità/hash grezzi test/nonce, commitment e pin originario, tampering della proof, conservazione della forma numerica dopo una riserializzazione JavaScript, duplicati fisici indipendenti da ID e ordine AST, JSON ambiguo/non finito/grande, binding benchmark v0.3 e quattro condizioni, aggregazione mista rifiutata. Il backend verifica riserva test, alias validi e importazioni preesistenti rifiutati atomicamente, embargo su submission/replay/stato, flag operatore immutabili con risultati grezzi conservati, gate di chiusura/reveal, ritiro e provenienza storica, reimportazione, sentinelle nei payload provider, rate persistenti su lookup invalidi/receipt/token ruotati/riavvii, scadenza della finestra e soglia di 20 invalidi.

Sono passati i comandi completi di [Integrity](integrity.md): preparazione/controllo Forge livelli 1–5, budget 3, seed demo 800123; demo Arena con primo caso test, tre esperimenti/tre osservazioni/nove passi di baseline, freeze/scoring, chiusura, reveal/proof e revoca; verifica CLI contro manifest `129aa6e48cd66402a1d728c3ff810ab716532f7669f9856feb713f6b5c965eb2`. Sessione definitiva della demo: `fd6ec3e7748f70cfc3c5cf20b5f73d44`; RMSE complessivo 0,02668079, interpolation 0,01306409, extrapolation 0,03539856. Questi valori sono solo un controllo del software.

Pacchetto benchmark v0.3: seed demo 810456, budget 1, manifest `05283f452baf7530a442080aa65100e212d29357b0d40ad6a7fe15da31323d3c`. Quattro trial `simulated`, uno per condizione sul caso `wda7c7b64c387cfd5`, completati senza invalidi; esperimenti rispettivamente 0/1/1/1 e chiamate fixture 3/3/3/4. Aggregazione e report passano e riportano la provenienza. Il fixture conosce la legge; non è apprendimento e non entra in una valutazione scientifica cieca.

Smoke finale in Edge già installato, Vite/FastAPI/SQLite reali e messaggi BYOA sintetici: challenge `3d16a9aa1a0a911b5b8c436b9585561c`, sessione `9fde40e6550807433737439750ebc538`. Un lancio, tre punti, ipotesi, conclusione e submission; score agente nullo prima della chiusura; flag `known_law` dalla UI, grezzi mantenuti e ranghi vuoti; chiusura, score visibile, revoca con 401, reveal da operatore e proof verificata successivamente dalla CLI. Nessun errore browser, storage vuoto, nessun overflow a 390 pixel. Screenshot in `benchmark_data/web-qa` ignorata da Git.

La prima verifica della proof salvata da JavaScript ha rilevato conversioni `0.0` → `0` che cambiavano il commitment. Il formato definitivo preserva `record_json` come stringa canonica; test dedicato e nuova proof browser/CLI passano. Una prova iniziale si è fermata prima del trial perché la porta 8765 apparteneva a un altro progetto, lasciato in esecuzione. Backend di test su 8766 e proxy Vite configurato con `ZONE_BACKEND_URL`; solo i server di prova sono stati arrestati.

Comandi finali, dalla radice (i percorsi delle ripetizioni erano nuovi):

```powershell
$env:MPLCONFIGDIR = Join-Path (Get-Location) 'benchmark_data/test-cache'
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
.\.venv\Scripts\python.exe -m unittest tests.test_integrity -q
.\.venv\Scripts\python.exe -m hidden_lab serve --help
# Preparazione, controllo, demo, quattro trial, aggregazione e report: docs/integrity.md.
# Backend di prova con token sintetico nell'ambiente e un DB dedicato:
.\.venv\Scripts\python.exe -m hidden_lab serve --db benchmark_data/integrity-forge-demo/browser-v2.sqlite3 --integrity-pack benchmark_data/integrity-forge-demo/private/pack.json --port 8766
cd frontend
pnpm test
pnpm build
$env:ZONE_BACKEND_URL = 'http://127.0.0.1:8766'
pnpm dev --host 127.0.0.1
# In un altro terminale nella cartella frontend, stesso token di prova del backend:
$env:ZONE_SMOKE_OPERATOR_TOKEN = '<token sintetico del backend di prova>'
$env:ZONE_SMOKE_INTEGRITY = '1'
$env:ZONE_SMOKE_PROOF_OUT = '../benchmark_data/web-qa/integrity-reveal-v3.json'
$env:ZONE_BROWSER_EXECUTABLE = 'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
node scripts/smoke-arena.mjs
cd ..
.\.venv\Scripts\python.exe -m hidden_lab integrity verify-reveal --manifest benchmark_data/integrity-forge-demo/public/manifest.json --proof benchmark_data/web-qa/integrity-reveal-v3.json --expected-manifest-hash 129aa6e48cd66402a1d728c3ff810ab716532f7669f9856feb713f6b5c965eb2
git diff --check
```

Per ripetere lo smoke, usare DB, caso test e proof nuovi: il reveal ritira il caso e la scrittura della proof non sovrascrive file esistenti. Un seed demo noto non è adatto a un pilot cieco. Nessuna API reale o credenziale provider, download di modelli, pubblicazione o deployment; nessun runner BYOA reale validato. Il [threat model](threat-model.md) conserva esplicitamente fiducia nell'operatore/host, equivalenza solo euristica, contaminazione esterna e identità multiple non rilevate.

File interessati: nuovi `integrity_suite.py`, `integrity_store.py`, `integrity_cli.py`, `tests/test_integrity.py`, `docs/integrity.md`, `docs/threat-model.md` e ADR 0008; integrazioni in CLI/server, repository/backend, Arena/store/demo, trial/CLI/report benchmark; UI/types/API/test Arena, Vite e smoke; README, ROADMAP, architettura, guide Arena/backend/benchmark, stato e verifiche.
