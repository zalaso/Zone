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
