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
