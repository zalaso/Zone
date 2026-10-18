# Verifiche locali e distribuzione

> Historical/advanced engineering reference. For the version 1.0 supported installation start with [Getting started](getting-started.md), [AI connections](ai-connections.md) and [self-hosting](self-hosting.md). Earlier phase statuses describe that earlier revision, not missing release features or a current hosted service.


## Pilot web personale — preparazione e attivazione del 10 ottobre 2026

Suite completa finale: **282 test Python passati in 286,697 s**, nessuno skip; **21 test frontend**, **2 Node**, Ruff, lint AST, TypeScript/build Vite e scansione del bundle passati. Nuovi test: ciclo web con rifiuto, modifica prima della previsione, JSON malformato/correzione, errore dopo le misure, conclusione/scoring; isolamento proprietario/invitati/staff e proprietà della sessione; continuità offline; SDK reale su HTTP sintetico con utilizzo nativo; payload pubblici; inferenze concorrenti; trasferimento sintetico, ack perso e token già ruotati. Nessuna inferenza o credenziale reale nelle prove.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m ruff check hidden_lab tests tools
# In frontend: pnpm test; pnpm lint; pnpm test:quality; pnpm build; pnpm check:bundle
.\.venv\Scripts\python.exe -m tools.verify_identity_browser --out benchmark_data/web-plan-browser-offline
.\.venv\Scripts\python.exe -m build --wheel --no-isolation --outdir dist/web-plan-wheel
.\.venv\Scripts\python.exe -m tools.package_beta --wheel dist/web-plan-wheel/hidden_physics_lab-0.11.0-py3-none-any.whl --out dist/web-plan-beta
```

Le directory di output devono essere nuove per ripetere queste prove. Risultati locali ignorati da Git: `benchmark_data/web-plan-tests-final.txt`, `web-plan-browser-offline/report.json`; contesto hash `c479a687360d8ce2`. Immagine sul VPS: `zone-beta:c479a687360d8ce2-chatgpt`, digest `sha256:d89fd14fd5901f9c40d514b83fc041e5ed8eaae3b7ea25e5c5761bb2368b8a82`, build con `INSTALL_CHATGPT=1`. Test nel runtime non root Linux, rete disabilitata e tmpfs: SDK OpenAI 2.54.0, PyJWT 2.15.1/RSA, importazione sintetica, host VM preservato, directory 0700 e file 0600 verificati.

Backup prima del riavvio del solo Zone; tutte le 24 tabelle applicative più `sqlite_sequence` identiche e undici altri container invariati. Configurazione precedente in `/root/zone-web-plan-20261010-c479`; rapporto privo di segreti in `/opt/zone/ops/web-plan-preparation.json`. Questa preparazione era ancora offline, con mount OAuth vuoto. Dopo consenso esplicito, trasferimento reale completato via SSH, token locali rimossi e catalogo verificato senza generazione: `gpt-5.6-sol` disponibile. Attivato il Compose personale soltanto per `guido`, con backup sul VPS, container sano, 25 tabelle identiche e undici altri container invariati. Credenziale UID/GID 10001, file 0600. Configurazione precedente in `/root/zone-web-plan-activation-20261010-final`, risultato privo di segreti in `/opt/zone/ops/web-plan-activation.json`. **Nessuna inferenza web reale avviata: pilot nel browser e controllo Usage restano da verificare dall’autore**; dettagli in [pilot web](web-llm-pilot.md). Nessuna nuova esecuzione CI o pubblicazione di codice.

Il primo build di preparazione ha fallito lo smoke pubblico: asset HTTP 401 perché le directory del contesto estratto erano root-only. Ripristinata subito la vecchia immagine senza sostituire il database, aggiunto `chmod -R a=rX /app/web` prima del cambio utente e ricostruito con nuovo hash. Il controllo nel container finale, rete disabilitata e UID 10001, legge tutti e tre gli asset e ne verifica l'assenza di scrivibilità. Lo smoke HTTPS ripetuto sul nuovo build passa: TLS, cookie Secure/HttpOnly/SameSite, CSRF, reload, storage vuoto, mobile, tre lanci baseline fino allo scoring, isolamento e ruoli; dodici letture con quattro worker, tutte 200 in 2,438 s. È una prova leggera. Rapporto `benchmark_data/web-plan-hosted-offline-fixed/report.json`; i tre account sintetici sono stati disabilitati e il file delle chiavi eliminato. Readiness HTTPS e altri undici container ricontrollati. Zero inferenze reali in questo smoke, eseguito prima del trasferimento OAuth autorizzato.

Dopo l'attivazione: home HTTPS e readiness HTTP 200, `/v1/modes` senza credenziale HTTP 401. Un altro amministratore sintetico riceve `offline_baseline` e `real_model=false` anche con il provider personale attivo; account temporaneo poi disabilitato. Nessuna lettura della chiave reale dell'autore, nessuna chiamata di generazione o esperimento durante questi controlli. Esiti aggiunti al rapporto di attivazione sul VPS. L'accesso reale dell'autore e una risposta valida nel browser restano da provare dall'autore.

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

## Fase 12 — preparazione del pilot, 8 ottobre 2026

Fase **in corso**: quattro generazioni Qwen reali locali, zero esperimenti; nessuna chiamata Gemini, credenziale remota o modello scaricato. I due tentativi Qwen si arrestano per timeout; nel secondo, la prima risposta completa viene rifiutata per troppi punti. Diagnostica JSON minima riuscita. Evidenze, budget e procedura in [pilot LLM](pilot-llm.md).

Verifica finale locale: **215 test Python passati in 172,807 s**, zero skip nell'ambiente completo, Ruff e `git diff --check` verdi. I cinque nuovi test del launcher usano chiavi sentinella e un client chiaramente simulato; tre regressioni del pilot locale verificano timeout e dati pubblici. Un warning della cache font Matplotlib fuori workspace non impedisce i test. Frontend, Docker e CI non rieseguiti per queste modifiche: restano le prove della fase 11, non attestazioni del nuovo codice.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_free_gemini_pilot.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_local_pilot.py -v
.\.venv\Scripts\python.exe -m ruff check hidden_lab tests tools
.\.venv\Scripts\python.exe -m tools.free_gemini_pilot --help
.\.venv\Scripts\python.exe -m build --no-isolation --outdir dist/phase12-preparation
.\.venv\Scripts\python.exe tools/check_release.py --archives dist/phase12-preparation
git diff --check
```

Build wheel/sdist e controllo dei confini passati, senza rete o installazioni; archivi locali di preparazione ancora alla versione 0.11.0, nessuna release pubblicata. Lo script di avvio è incluso nella sdist e non nella wheel. Il test integrato del launcher crea/valida davvero un mondo Forge offline, poi esercita domanda, approvazione simulata, osservazioni, ipotesi, previsione preregistrata, verifica e conclusione. Nessun test sintetico attesta accettazione del contratto da Gemini, quota Free Tier o qualità scientifica: restano verifiche del pilot reale con operatore.

### Primo tentativo Gemini e diagnostica separata

Dopo la preparazione, l'autore ha avviato `pilot12-gemini-fc1ebde5f608`: una chiamata `gemini-3.8-flash`, SDK 2.25.0, errore `server_error` in 120,843 s, utilizzo ignoto, zero messaggi validi e zero esperimenti. Il codice non consente di ricostruire lo status 5xx specifico o il corpo della risposta, volutamente esclusi dai registri. Non è registrato un timeout HTTPX locale. Nessuna nuova chiamata remota avviata da Codex per la diagnosi.

Aggiunta l'opzione `--diagnostic` al launcher: singola generazione JSON minima con stessa API/modello/timeout/output massimo; niente mondo, Session, esperimenti, retry o avvio automatico del pilot. Credenziale nascosta e ripristino ambiente invariati, risultato ridotto in un percorso privato nuovo, output grezzo escluso. Il test usa un client chiaramente simulato e verifica successo, errore server, JSON malformato, booleano sostituito con numero e risposta incompleta, con una sola chiamata e zero esperimenti in ogni caso.

Verifica finale dopo questa aggiunta: **216 test Python passati in 123,310 s**, Ruff, `--help` e `git diff --check` verdi. Cache Matplotlib diretta in `benchmark_data/test-cache`. Diagnostica reale ancora da eseguire esplicitamente dall'operatore; nessuna causa attribuita a credenziale, schema o thinking senza ulteriori evidenze. Comando e dettagli in [pilot LLM](pilot-llm.md).

### Diagnostica Gemini reale riuscita

L'autore ha eseguito la diagnostica minima e riportato l'esito, confermato leggendo il registro ridotto `benchmark_data/pilot12-gemini-887d2321bcc7/private/connectivity-result.json`: JSON valido in **4,251 s**, una chiamata, zero esperimenti, modello restituito `gemini-3.8-flash`. Conteggi nativi: prompt 34, risposta 5, ragionamento 107, totale 146; cache non restituita. Nessuna nuova chiamata avviata da Codex e nessuna modifica al codice in questo passaggio. Aggiornata solo documentazione; non ripetuta la suite già verde a 216 test. La prova conferma accesso e schema minimo tramite l'adapter, non il contratto completo o la capacità d'indagine; il primo errore 5xx resta senza causa conclusiva. Pilot completo successivo da avviare esplicitamente dall'operatore, con percorsi nuovi e impostazioni invariate.

### Richiesta completa ripetutamente fallita e modalità JSON esplicita

Ispezionati soltanto i metadati dei registri di due ulteriori sessioni avviate dall'autore: `pilot12-gemini-78027aca516a`, una chiamata `server_error` in 4,627 s; `pilot12-gemini-3115735d1e38`, una chiamata `server_error` in 6,109 s. Zero turni validi ed esperimenti. Totale Gemini osservato: tre tentativi completi falliti e una diagnostica minima riuscita. Lo schema vincolato è un sospetto operativo, non una causa provata. Nessuna chiamata API reale, credenziale reale o download usati da Codex per implementare la modalità alternativa.

Aggiunto `--gemini-output-mode json` a `investigate` e al launcher: JSON senza vincolo `response_json_schema`, contratto pubblico identico nel prompt, validazione applicativa e conferme invariate, nessun fallback/retry. Default schema conservato. La modalità è registrata nelle impostazioni di generazione; automatic function calling SDK disabilitato esplicitamente. Factory e client supportano la scelta esplicita; gli altri provider rifiutano il flag alternativo. Formato benchmark v0.3 invariato e sua CLI resta sul percorso schema.

Test scritti prima dell'implementazione: tre inizialmente falliti per assenza della modalità e del flag, poi verdi. Cinque test definitivi verificano payload pubblico/schema nel prompt e default preesistente, rifiuto su altri provider, richieste fisiche invalide e audit, ciclo completo con modifica prima della previsione, SDK reale con HTTPX MockTransport che osserva la richiesta serializzata senza parametro schema. Confermata assenza di chiave nei payload/registri; test con credenziali fittizie.

Verifica finale: **221 test Python passati in 120,007 s**, Ruff, help CLI/launcher e `git diff --check` verdi. Comandi: `python -m unittest discover -s tests`, `python -m unittest discover -s tests -p test_gemini_json_mode.py -v`, `python -m unittest discover -s tests -p test_free_gemini_pilot.py -v`, `python -m ruff check hidden_lab tests tools`; Python dell'ambiente `.venv`, cache Matplotlib nel workspace. Frontend/Docker/CI non rieseguiti per questa aggiunta. La modalità JSON resta da verificare con Gemini reale; non è dichiarata risolta la causa del 5xx. Comando di avvio in [pilot LLM](pilot-llm.md).

## Fase 12 — accesso con il piano ChatGPT, 8 ottobre 2026

L’autore ha successivamente completato un esperimento Gemini in modalità JSON: richiesta valida in 7,319 s, approvazione e lancio espliciti, tre misure; errore alla chiamata 2 in 5,377 s. Registri conservati senza rilancio, nessuna ipotesi/previsione/conclusione. Sei chiamate Gemini complessive nelle prove dell’autore. Il nuovo percorso scelto è OAuth ufficiale **Sign in with ChatGPT**, distinto dal provider OpenAI con chiave API.

Implementati `chatgpt login/status/select/models/logout/pilot` e `investigate --provider chatgpt`. PyJWT 2.15.1 installato nell’ambiente locale per la verifica delle firme; extra `.[chatgpt]`, SDK OpenAI 2.54.0. Nessun modello scaricato, login reale o inferenza ChatGPT effettuati durante lo sviluppo. Il programma non legge il login di Codex e non cambia il billing dell’account. Benchmark v0.3, backend, Arena e frontend mantengono i provider e i formati precedenti.

**18 nuovi test offline** verificano payload pubblico, PKCE, state/nonce, firme e claims, browser/callback e scambio OAuth simulati, rinnovo atomico e revoca, isolamento account, lock, DPAPI Windows con soli dati sintetici, catalogo, SDK reale su HTTP fittizio, stream completo/incompleto/interrotto/errore, limiti locali, rifiuto di tool call, correzione e confine informativo. Il ciclo comprende domanda/risposta, approvazione, modifica prima della previsione, osservazioni, ipotesi, preregistrazione e conclusione; test separati coprono rifiuto e errore dopo un esperimento. Il pilot attraversa Forge reale e client chiaramente simulato, senza rete. Chiave API, organizzazione, progetto e URL alternativi nell’ambiente non vengono usati dal provider ChatGPT.

La prima esecuzione dei test ha rilevato moduli mancanti prima dell’implementazione. DPAPI non era disponibile nel sandbox: verificata fuori sandbox esclusivamente su dati sintetici. Un primo test del pilot usava l’input originale del terminale anziché quello fittizio; corretto il test e verificato il ciclo. Nessuna chiamata al modello per diagnosticare questi errori.

Prima verifica dell’integrazione: **239 test Python passati in 140,101 s**; test ChatGPT mirati **18 passati in 5,215 s** dopo il controllo dei header di progetto/organizzazione. Ruff e `git diff --check` verdi; help CLI verificato. Wheel/sdist locali costruiti e confini degli archivi verificati con `tools.check_release`. Rimane versione di sviluppo 0.11.0, nessuna pubblicazione. CI, Docker e frontend non rieseguiti per questa aggiunta.

Comandi eseguiti (PowerShell, Python `.venv`; dipendenze e test DPAPI con l’accesso locale necessario):

```powershell
.\.venv\Scripts\python.exe -m pip install --retries 0 'PyJWT[crypto]>=2.10,<3'
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_chatgpt.py
$env:MPLCONFIGDIR = Join-Path (Get-Location) 'benchmark_data/test-cache'
.\.venv\Scripts\python.exe -m unittest discover -s tests
.\.venv\Scripts\python.exe -m ruff check hidden_lab tests tools
.\.venv\Scripts\python.exe -m hidden_lab chatgpt --help
.\.venv\Scripts\python.exe -m hidden_lab chatgpt pilot --help
.\.venv\Scripts\python.exe -m hidden_lab investigate --help
.\.venv\Scripts\python.exe -m build --no-isolation --outdir dist/phase12-chatgpt
.\.venv\Scripts\python.exe -m tools.check_release --archives dist/phase12-chatgpt
git diff --check
```

Al momento della prima verifica OAuth: nessuna indagine LLM conclusa, fase 12 allora in corso. Il primo pilot ChatGPT dell’autore documentato sotto conferma accesso alle inferenze, non un ciclo valido. OAuth verifica il permesso del piano, non la quota o un costo zero. La preview non supporta `max_output_tokens`: limite locale di 64 KiB e controllo dello stream esplicitati, non un tetto ai token generati. Timeout HTTP per lettura e controllo del tempo agli eventi; nessuna promessa di un termine assoluto preciso. Nessun fallback o retry di inferenza, ripresa delle sessioni non implementata. Istruzioni per l’operatore in [Zone con il piano ChatGPT](chatgpt-plan.md).

## Fase 12 — diagnosi dello stream ChatGPT, 8 ottobre 2026

Sessione reale dell’autore `sessions/pilot12-chatgpt-98d67609c131`: `gpt-5.6-sol`, tre risposte `completed`, tutte `invalid_response` con errore pubblico `JSON non valido.`, zero turni validi ed esperimenti; arresto `invalid_response_limit`. Durate 7,504 / 6,404 / 6,114 s. Utilizzo nativo complessivo: input 3459, output 480, totale 3939 token; ragionamento 166 (già incluso nell’output), cache 0. Il testo non è stato conservato: impossibile attribuire con certezza la causa dei tre invalidi. Non sono stati letti token OAuth o verità fisiche private.

Un test con SDK reale e HTTP/SSE simulato riproduce una perdita di testo: delta JSON validi seguiti da `response.completed` senza snapshot di testo producevano `reply.text == ''`. Comando prima della correzione:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_chatgpt.py -k text_deltas -v
```

Esito RED: un test fallito, confronto fra stringa vuota e contenitore JSON valido. Il test passa dopo la raccolta dei delta e del testo finalizzato. Il client aspetta comunque il completamento, usa il riepilogo come alternativa, rifiuta contenuti discordanti e non concatena due volte la stessa risposta. I limiti locali valgono durante la raccolta. Refusal e tool call rilevati prima del riepilogo non possono sparire nel completamento vuoto. La [documentazione ufficiale sullo stream](https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference) mostra il consumo di `response.output_text.delta` con controllo di `response.completed`.

Sette regressioni aggiunte: testo senza snapshot, duplicazione, ordine delle parti e done senza delta, errore/EOF dopo testo parziale, discordanza/limite, refusal/tool intermedi e diagnostica ridotta. Il ciclo completo con modifica e previsione ora usa delta senza snapshot. I JSON invalidi e i blocchi Markdown continuano a essere rifiutati; diagnostica senza testo, credenziali o estratti dell’errore. Le nuove impostazioni registrano `text_extraction_version=2`.

Nessuna nuova chiamata reale durante la diagnosi. Alla fine della diagnosi la correzione era dimostrata soltanto offline e restava necessario un nuovo avvio esplicito dell’operatore; il successo successivo è documentato sotto. La causa del vecchio pilot non è ricostruibile. I vecchi registri sono conservati.

Verifica successiva alla correzione: **246 test Python passati in 139,124 s**. Tredici test del trasporto streaming passati in 4,631 s; ripetizione mirata della regressione originaria verde in 3,015 s. Ruff completo e `git diff --check` passati. La suite usa esclusivamente HTTP e identità sintetiche; per DPAPI viene eseguita fuori dal sandbox Windows, senza accedere all’archivio dell’account reale. CI, Docker e frontend non rieseguiti per questa correzione CLI.

```powershell
$env:MPLCONFIGDIR = Join-Path (Get-Location) 'benchmark_data/test-cache'
.\.venv\Scripts\python.exe -m unittest discover -s tests
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_chatgpt.py -k SubscriptionStreamingTests
.\.venv\Scripts\python.exe -m ruff check .
git diff --check
```

## Fase 12 — primo pilot reale completato, 8 ottobre 2026

L’autore ha completato `sessions/pilot12-chatgpt-f94542b8deee` con `gpt-5.6-sol` sul piano ChatGPT: **8 chiamate accettate, 8 turni validi, 3 esperimenti autorizzati, una previsione preregistrata e conclusione**. Zero risposte invalide, correzioni o errori provider. Lettore `text_extraction_version=2`, tutti i testi validi ricavati dallo stream. Conclusione al messaggio 22, nell’ultima chiamata consentita; nessun arresto per limite.

Controllo offline dei registri originali: sequenza eventi continua; otto coppie started/accepted; ogni avvio preceduto da approvazione e modalità; request_id eseguiti una sola volta; previsione al messaggio 11 prima dell’avvio al 12 e delle misure al 13. Tre osservazioni riuscite, budget residuo finale 0. Nove campioni, dei quali tre sono stati iniziali già impostati. RMSE della singola verifica 3,4851396216797643 × 10^-16 m, errore massimo 5,79553433516819 × 10^-16 m; identificazione della legge non valutata.

Utilizzo nativo: input 19219, output 2174, totale 21393 token; ragionamento 551 già incluso nell’output, cache 0. Tempo delle chiamate 63,351 s, singole chiamate 5,748–10,290 s; tempo dell’operatore escluso. L’autore ha confermato il controllo in ChatGPT Usage: sola quota dell’abbonamento, nessun credito extra. È una conferma umana dell’account, non una certificazione monetaria dei registri.

**Fase 12 completata nel perimetro del primo pilot locale.** Un mondo con tempi 0–0,2 s e una verifica non validano il benchmark, Arena o una legge unica. Domande, modifiche, rifiuti e guasti restano coperti dai test offline, non esercitati in questo pilot. Nessuna nuova inferenza o credenziale reale usata dall’agente di sviluppo durante il controllo, nessuna verità fisica privata consultata. Nessun codice modificato in questa revisione documentale; suite della correzione precedente 246 verde, non rieseguita per il solo resoconto. Dettagli e impronte dei file originali in [risultati del pilot ChatGPT](pilot-chatgpt-result.md).

## Fase 13 — identità su invito, 9 ottobre 2026

**263 test Python passati in 184,159 s**, inclusi 17 nuovi test multiutente; **20 test frontend**, **2 controlli Node**, TypeScript, Ruff, build Vite, scansioni bundle/archivi e `git diff --check` verdi. Python 3.14.4 su Windows. Per i test SQLite/TestClient e DPAPI è stato necessario uscire dal sandbox Windows; soltanto file temporanei e identità sintetiche, nessun archivio OAuth reale. Il primo tentativo nel sandbox falliva per permessi sui temporanei e non è contato come verifica riuscita.

Copertura nuova: tutte le API private protette; nessun bypass con token locali; proprietà di sessioni, risultati, audit e confronti; ruoli/ultimo admin; cookie, CSRF, Origin/Host, scadenza assoluta e inattività; login limitato, rotazione, disabilitazione e recupero; logout con quota zero; sessioni concorrenti e rollback del confronto; quote esperimenti e modello riservate prima del lavoro; guasto di rete senza retry; ciclo completo con payload pubblico; doppia credenziale Arena; backup/restore con revoche, ownership e rate; migrazione v2 e adozione storica; rifiuto del downgrade e readiness indisponibile se manca una tabella account. I checksum delle migrazioni 1–2 restano invariati; schema corrente 3.

Demo `benchmark_data/phase13-identity-offline/report.json`: quattro account sintetici, indagine `scored`, **due esperimenti e sette chiamate alla baseline affine**, isolamento e revoca verificati; tutte le tabelle identiche dopo backup/restore. Seed noto, nessuna misura di apprendimento o chiamata a un LLM reale.

Browser Edge reale su server Uvicorn loopback e bundle finale: `benchmark_data/phase13-browser-final/report.json`, immagini desktop/mobile nella stessa cartella, ispezionate. Login/cookie, ricarica, creazione sessione e lancio solo dopo decisione/modalità/comando, quota aggiornata, CSRF respinto, altro account respinto, invito amministrativo, rotazione e rimozione dei dati dopo revoca; storage JavaScript vuoto, cookie non leggibile da JavaScript, mobile senza overflow. La prima prova non conservava il dettaglio dell’errore; la seconda ha localizzato il blocco sulla selezione dell’account nella console admin. Etichetta accessibile esplicita e regressione frontend aggiunte; le prove successive passano. Le chiavi sintetiche sono rimaste in memoria; la diagnostica del runner espone solo fase e numero di riga, senza errori grezzi che possano riportare valori dei campi.

Compatibilità: `ops demo` completata in `benchmark_data/phase13-regression-demo`, Forge e Integrity validi, Arena con 3 lanci/9 passi offline, scoring, chiusura/revoca/reveal; quattro trial benchmark `prior_only`, `passive_fixed`, `passive_sequential`, `active`, tutti completati con zero invalidi, aggregazione e report. Esperimenti 0/1/1/1, chiamate fixture 3/3/3/4. Restore schema 3, 25 eventi, 24 receipt, 28 audit Arena e un token revocato. Metriche e protocolli scientifici invariati.

Comandi eseguiti dalla radice, salvo quelli frontend:

```powershell
$env:MPLCONFIGDIR = Join-Path (Get-Location) 'benchmark_data/test-cache'
.\.venv\Scripts\python.exe -m unittest discover -s tests
.\.venv\Scripts\python.exe tools/verify_identity.py --out benchmark_data/phase13-identity-offline
.\.venv\Scripts\python.exe -m tools.verify_identity_browser --out benchmark_data/phase13-browser-final
.\.venv\Scripts\python.exe -m hidden_lab ops demo --out benchmark_data/phase13-regression-demo
.\.venv\Scripts\python.exe -m hidden_lab identity --help
.\.venv\Scripts\python.exe -m hidden_lab serve --help
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m build --no-isolation --outdir dist/phase13-final
.\.venv\Scripts\python.exe tools/check_release.py --archives dist/phase13-final
git diff --check
```

Da `frontend`, usando soltanto dipendenze già presenti:

```powershell
node node_modules/vitest/vitest.mjs run
node node_modules/typescript/bin/tsc -b
node node_modules/vite/bin/vite.js build
node scripts/check-source.mjs
node scripts/check-bundle.mjs
node --test scripts/quality.test.mjs
```

Il tentativo iniziale con `pnpm test/build` era impedito dal sandbox/runtime; nessuna nuova dipendenza è stata installata. I comandi diretti sopra passano. Wheel/sdist locali contengono i moduli identità e mantengono esclusi database, sessioni e credenziali. Numero pacchetto ancora 0.11.0: questi archivi sono build di sviluppo locale, non una nuova release pubblicata o verificata nella CI remota. CI e Docker della fase 11 non rieseguiti per la fase 13. Nessun push, deploy, download di modelli, accesso a credenziali provider o inferenza reale.

File della fase 13: nuovi `hidden_lab/identity.py`, `identity_store.py`, `identity_cli.py`, `tests/test_identity.py`, `frontend/src/Identity.tsx`, `Identity.test.tsx`, `frontend/scripts/smoke-identity.mjs`, `tools/verify_identity.py`, `verify_identity_browser.py` e `docs/identity.md`. Estesi backend/store, Arena store/client, migrazioni/schema, CLI/server e readiness; App/Arena/API/main frontend, test API e migrazioni. Aggiornati README, ROADMAP, CHANGELOG e guide stato, operazioni, Arena e revisione operativa. Le modifiche locali precedenti della fase 12 sono conservate.

**Fase 13 completata localmente.** Restano fase 14 (beta privata con host/TLS, monitoraggio, carico e restore sul bersaglio) e fase 15 (pubblicazione/policy/apertura). Le identità sono invitate, senza SSO/MFA o anti-Sybil generale. Il pilot reale della fase 12 resta distinto dalla validazione multiutente e scientifica del benchmark. [Avvio e limiti](identity.md), [panoramica](status.md).

## Beta Tailscale — 9 ottobre 2026

267 test Python, 20 frontend e due test Node; Ruff, TypeScript, Vite e controllo bundle passati. Nuovi test per contesto di deploy con elenco esplicito, rifiuto di file estranei e limiti/accesso privato. Build wheel e pacchetto: `python -m build --wheel --no-isolation --outdir dist/phase14-wheel`; `python -m tools.package_beta --wheel dist/phase14-wheel/hidden_physics_lab-0.11.0-py3-none-any.whl --out dist/phase14-beta`. Release artefatti `3b121592ffb981e6`.

Sul VPS, verifica offline in container con `tools/verify_identity.py`: due lanci e sette passi baseline, isolamento/revoca e restore identico. Sul servizio ospitato, `python -m tools.verify_hosted_beta --ssh-host YOUR_SSH_ALIAS --origin https://zone.example-tail.ts.net:8444 --out benchmark_data/phase14-vps/https-smoke`: Edge reale desktop/mobile, cookie Secure/HttpOnly, storage vuoto, CSRF, conferma esplicita, reload, tre lanci baseline fino allo scoring, isolamento/ruoli, dodici letture concorrenti con quattro worker. Le chiavi dei soli account sintetici sono state caricate in memoria via SSH, mai stampate; gli account sono poi stati disabilitati. Il comando richiede fixture nuove prima di essere ripetuto.

Riavvio del solo container Zone e restore sul bersaglio su un database nuovo: confronto di tutte le 24 tabelle uguale. Backup e manifest restano soltanto sul VPS per scelta dell’autore; nessun database trasferito sul PC. Timer backup/salute attivi. Pulizia limitata a cache di build Docker più vecchia di 24 ore e archivi APT; 1.660.903.424 byte recuperati. Undici container preesistenti e le rotte Serve 443/8443 invariati. Zero chiamate LLM. Le prove di carico sono leggere e sintetiche, non una misura di capacità; restano utenti invitati e carico rappresentativo. [Guida operativa](private-beta.md).

## Beta web su invito — 10 ottobre 2026

`python -m unittest discover -s tests`: **271 test passati in 224,392 s**; Ruff e `node --check frontend/scripts/smoke-beta.mjs` passati. Nuovi controlli per upstream sul bridge privato, runtime limitato, archivio sorgente e destinazione delle chiavi sintetiche: il verificatore confronta l’origine richiesta con quella configurata sul VPS prima di inviare credenziali. Nessun cambiamento al bundle applicativo o al simulatore.

`python -m tools.verify_hosted_beta --public --origin https://zone.example.org --out benchmark_data/public-beta-20261010/https-smoke`: Edge reale desktop/mobile, cookie Secure/HttpOnly/SameSite Strict, storage vuoto, CSRF, lancio esplicito, reload, isolamento e ruoli. Ciclo baseline completo: tre esperimenti fino allo scoring. Dodici letture con quattro worker: tutte 200 in 1,425 s; non è una prova di capacità. Account temporanei poi disabilitati e chiavi rimosse, senza usare la chiave personale dell’autore.

Prove anonime da PC verso l’IP Internet: certificato valido, HTTP 308 verso HTTPS, header di sicurezza, API protette 401, origine estranea 403, payload troppo grande 413, `.env`/database 404 e porte 8876/8877 non raggiungibili. Caddy validato e ricaricato senza restart, con sei rotte originarie conservate; undici altri container invariati, quattro siti controllati. Backup preventivo e confronto delle 24 tabelle prima/dopo la ricreazione del solo Zone: identiche. Monitoraggio HTTPS aggiunto; altre rotte Tailscale invariate, sola vecchia rotta Zone 8444 ritirata. Backup soltanto sul VPS, come scelto dall’autore.

Configurazione pubblica in `deploy/compose.public.yaml` e `deploy/zone.caddy`; app invariata `zone-beta:3b121592ffb981e6`. Zero chiamate LLM, modello scaricato, credenziale provider o spesa aggiuntiva. [Guida al servizio](public-beta.md).

## Workspace personale e redesign — 10 ottobre 2026, prove locali

Candidata distinta dalla beta sul VPS: registrazione autonoma attivabile, recupero monouso con revoca delle sessioni/connessioni, API personali cifrate, connettore in uscita per ChatGPT/Ollama, Arena personale e design chiaro/scientifico. Schema additivo 4; checksum delle migrazioni 1–3 preservati. Nessun deployment, credenziale reale, chiamata provider o modello scaricato durante questo sviluppo.

Prove eseguite:

- Suite Python completa: 291 test passati; nove nuovi test per account/CSRF/recupero, cifratura e proprietà, connessione fissata e revoca, ciclo con client API simulato, JSON malformato e rete, connettore monouso con lease, limite mondi atomico, modifica prima della previsione, quote distinte e Arena personale. Le suite precedenti restano comprese.
- Frontend: 25 test passati, TypeScript/build Vite, lint AST e scansione del bundle; due test Node sui controlli di qualità passati. Quattro nuovi test coprono registrazione/recupero, API personali senza inferenza al salvataggio, preparazione ChatGPT locale e conferme separate in Arena.
- Edge reale su loopback: registrazione, codice di recupero mostrato una volta, preparazione di un connettore senza avviarlo, ritorno alla baseline, Arena fino allo scoring con due esperimenti autorizzati, riapertura dalla lista sessioni e logout. Desktop 1440×1000 e mobile 390×844 senza overflow; screenshot ispezionati in `benchmark_data/workspace-browser`. Nessun errore JavaScript e storage persistente del browser vuoto.
- `ops demo` in `benchmark_data/workspace-regression-demo`: Forge/Integrity validi; Arena offline, tre lanci/nove passi, scoring/chiusura/revoca/reveal; benchmark con quattro condizioni, aggregazione e report, zero invalidi; backup/restore/check schema 4. Nessun cambiamento alla metodologia benchmark v0.3.
- Wheel e sdist costruiti senza isolamento/download e verificati per versioni/MIT/elenco dei file ammessi. Non è stata eseguita una nuova distribuzione Docker/CI remota della candidata. La versione del pacchetto resta quella di sviluppo locale, non una nuova release pubblicata.

Comandi di verifica, dalla root salvo diversa indicazione:

```powershell
.\.venv\Scripts\python.exe -m ruff check hidden_lab tests tools
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
.\.venv\Scripts\python.exe -m hidden_lab ops demo --out benchmark_data\workspace-regression-demo
.\.venv\Scripts\python.exe -m build --no-isolation --outdir benchmark_data\workspace-package
.\.venv\Scripts\python.exe tools\check_release.py --archives benchmark_data\workspace-package
.\.venv\Scripts\python.exe -m tools.preview_workspace --out benchmark_data\workspace-preview --port 8767
# In un secondo terminale, nella cartella frontend:
pnpm run build
pnpm run test
pnpm run lint
pnpm run check:bundle
pnpm run test:quality
node scripts/smoke-workspace.mjs
```

La prima esecuzione dei test Python dentro la sandbox Windows è fallita per accesso negato alle directory temporanee, prima della verifica funzionale; riesecuzione fuori dalla sandbox con dati sintetici riuscita. Durante lo sviluppo sono state corrette fixture che presumevano una richiesta prima dell’ipotesi iniziale della baseline, etichette dei selettori Arena e una query frontend ambigua; le verifiche finali sopra includono le correzioni.

File di questo intervento: `hidden_lab/public_accounts.py`, `connections.py`, `connector_contract.py`, `connector_cli.py`, `public_arena.py`; integrazione in backend, repository, identity, Arena/store, provider factory e tre client API, CLI/server, schema/migrazioni e readiness. UI in `PublicAccess.tsx`, `Workspace.tsx`, `Connections.tsx`, `PersonalArena.tsx`, `workspace.css`, Identity/App/main e tipi Arena. Prove in `tests/test_public_workspace.py`, `Workspace.test.tsx`, `smoke-workspace.mjs` e adattamento della verifica schema. Preview in `tools/preview_workspace.py`; configurazione extra workspace, build container opzionale, CI offline, packaging dei documenti di design e pulizia delle variabili di test. Contesto prodotto in PRODUCT/DESIGN; istruzioni in [workspace pubblico](public-workspace.md), README, ROADMAP, status e changelog. Le modifiche locali precedenti sono state conservate.

Limiti: nessun collegamento reale di questo nuovo percorso validato durante lo sviluppo; nessuna validazione scientifica aggiuntiva. Il piano ChatGPT usa il connettore locale; inferenza hosted senza connettore richiede l’adesione prevista da OpenAI. Prima dell’apertura restano prove dell’autore, capacità/recupero sul VPS, informazioni agli utenti e distribuzione candidata. Non è promessa riproducibilità esatta delle risposte LLM.


## Esperienza guidata — 10 ottobre 2026

Intervento locale sulla candidata 0.11.0: nessun deploy, login provider o inferenza reale. Sorgenti scientifici, protocollo, schema e backend conservati.

| Requisito | Implementazione e prova |
| --- | --- |
| Capire Zone senza preparazione tecnica | Landing con esempio dimostrativo controllabile, onboarding e accesso manuale senza AI. Browser Edge reale. |
| Capire ogni percorso e le impostazioni | Sei guide con obiettivo, prerequisiti, passi e risultati; glossario ricercabile, approfondimenti e aiuti ai campi. Test della ricerca e dei percorsi. |
| Profilo più utile | Quote aggiornate automaticamente e su richiesta, residui separati, connessione selezionata, accesso alle sessioni e istruzioni di recupero. Prove unit e mobile. |
| Visualizzare il mondo e le attese | Grafica World Forge e animazioni distinte per generazione, chiamata AI e lancio; solo durata trascorsa, nessun avanzamento interno inventato. Browser con risposte locali ritardate solo nel test. |
| Vedere l’esperimento dell’agente | Posizione/velocità prima del lancio, campioni e previsione dopo la risposta, controlli riproduci/pausa/cursore. Solo eventi pubblici fino al cursore; modifiche rispettate, nuovi lanci senza misure ereditate. Test unit e browser. |
| Formule leggibili | KaTeX 0.19.0 in MathML nativo, delimitatori LaTeX, macro isolate e limiti, comandi non fidati inerti, fallback testuale. Test injection e browser con CSP invariata. |
| Nessuna confusione tra sessioni | Configurazione e indagine attiva separate; bozze e decisione azzerate alla creazione/apertura/cambio partecipante. Regressione dedicata e Human vs AI completo. |
| Mobile e accessibilità del movimento | 390×844, 768×1024 e desktop 1440×1000; nessun overflow. Movimento ridotto verificato sugli indicatori; tabelle e replay manuale disponibili. |

**Esiti frontend:** 35 test Vitest passati, compilazione TypeScript/Vite passata, lint AST e scansione bundle passati, 2 controlli Node passati; diff senza errori di whitespace. Bundle suddiviso in app (circa 347 kB) e renderer (circa 262 kB), senza font remoti o asset KaTeX aggiuntivi. Le dimensioni non sono un benchmark prestazionale.

**Browser offline:** `pnpm run test:browser:experience` passato con Forge realmente validato dal server locale, proposta/modifica, previsione preregistrata, formula MathML, lancio esplicito, replay, guida e profilo, baseline AI e confronto Human vs AI fino al risultato. Nessuna richiesta esterna del prodotto o violazione CSP; un tentativo di iniezione dello script Kaspersky del sistema è stato bloccato nel solo browser di test. `pnpm run test:browser:workspace` passato con registrazione, recupero monouso, connettore preparato senza avviarlo, Arena offline con due lanci espliciti, scoring, riapertura e logout. Nessuno storage browser persistente.

Durante la verifica è stato corretto un difetto reale: la decisione Modifica di una sessione precedente restava attiva nel modulo Human vs AI. Il backend la respingeva senza lanciare; ora le bozze sono azzerate e la regressione è coperta. Il controllo di configurazione usa un pulsante con aria-expanded per evitare corse fra eventi toggle nativi e completamento delle richieste. I test browser attendono la conferma del server tramite UI e rispettano i limiti: non interrogano lo stato a ogni fotogramma. Due test browser consecutivi sullo stesso server possono esaurire il limite comune per IP; attendere almeno 60 secondi tra i due comandi.

La prima suite Python completa ha eseguito 291 test con 2 errori di timeout (30 s) nel subprocess di credenziali mancanti Anthropic/Gemini durante le verifiche concorrenti. Lo stesso test isolato è passato in 11.404 s con chiavi vuote e nessuna inferenza. **Riesecuzione completa passata: 291 test in 171.236 s, zero errori o fallimenti**, registro `benchmark_data/experience-python-final.log`. Non sono stati aumentati i timeout o indeboliti i test.

File di questo intervento: nuovi `frontend/src/Guide.tsx`, `Profile.tsx`, `LabVisuals.tsx`, `ScientificText.tsx`, `LabExperience.test.tsx` e `frontend/scripts/smoke-experience.mjs`; aggiornati App e relativi test, Workspace, Connections, PublicAccess, PersonalArena, Modes, view, workspace.css, package.json, lockfile e vite.config. Adattati smoke.mjs, smoke-modes.mjs e smoke-workspace.mjs alle sezioni espandibili e alle attese. Documentazione in README, DESIGN, CHANGELOG e `docs/laboratory-experience.md`. Artefatti e immagini in `benchmark_data/experience-browser/`; nessuna credenziale fotografata.

Limiti: il grafico unisce campioni con scale indipendenti, non integra una legge né mostra una traiettoria fisica continua. Il modello riceve dati numerici, non il grafico come immagine. Le formule non vengono eseguite; la resa MathML richiede un browser moderno. Nessuna nuova validazione con provider reali, verifica WCAG completa o pubblicazione sul VPS. Restano le prove dell’autore prima della distribuzione; il piano ChatGPT pubblico continua a usare il connettore locale.
