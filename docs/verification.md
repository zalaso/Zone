# Verifiche locali

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
