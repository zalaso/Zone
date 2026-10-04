# Identificazione delle leggi — fase 3

La **previsione numerica dell'accelerazione sui probe pubblici** rimane la misura principale. Dopo la conclusione dell'indagine si possono aggiungere una legge candidata come AST JSON e una deviazione standard per ciascun probe. La valutazione conserva dimensioni separate: errore predittivo, equivalenza funzionale empirica, complessità, dipendenze dalle variabili di stato e calibrazione. Non produce un punteggio unico e non richiede che l'AST candidato sia testualmente identico alla legge privata.

La submission comune ai file dell'operatore e ai messaggi `benchmark_submission` degli agenti v0.3 contiene `predictions` (obbligatorio), `law_ast_json` e `uncertainty_sigma` (facoltativi). Nel benchmark restano obbligatori anche `final_hypothesis_id`, `law_description`, `limits` e `alternatives`; gli altri campi appartengono al protocollo di scoperta, non al valutatore scientifico. Le suite e i risultati v0.1/v0.2 restano leggibili e non accettano i nuovi campi. La suite v0.3 mantiene i suoi mondi storici: non viene rigenerata da World Forge.

Esempio del sottoinsieme comune, con un solo probe illustrativo:

```json
{
  "predictions": [{"probe_id": "p01", "ax": 0, "ay": -9.8}],
  "law_ast_json": "{\"level\":1,\"ax\":{\"op\":\"const\",\"value\":0},\"ay\":{\"op\":\"const\",\"value\":-9.8}}",
  "uncertainty_sigma": [0.5]
}
```

`law_ast_json` è una **stringa che contiene un oggetto JSON AST**, con grammatica e limiti documentati in [World Forge](world-forge.md). È una serializzazione di dati, interpretata da `world_ast.py`: non si eseguono formule, Python o codice generato dal modello. Sono ammessi massimo 8.000 byte di AST, 64 nodi, profondità 12 e solo livelli 1–5. `uncertainty_sigma` contiene una deviazione standard isotropa positiva, in m/s², per ciascun vettore `(ax, ay)`, nello stesso ordine dei probe; intervallo [0,001, 1.000]. Tutti i numeri devono essere finiti. Le previsioni devono coprire esattamente i probe e mantenere l'ordine pubblicato.

## Una prova locale senza API

I percorsi di output devono essere nuovi. Prima genera un mondo Forge e avvia un'indagine `shell` o `investigate`; nella sessione registra infine una `conclusion`. Il comando `identify challenge` rifiuta una sessione che non termina con tale messaggio e verifica che la configurazione privata della sessione corrisponda al mondo. Per esempio, dopo avere creato `benchmark_data/forge-demo/world.json`, `benchmark_data/forge-demo/config.json` e `sessions/forge-demo` come nella [guida World Forge](world-forge.md):

```powershell
.\.venv\Scripts\python.exe -m hidden_lab identify challenge --world benchmark_data/forge-demo/world.json --session sessions/forge-demo --out benchmark_data/forge-demo/challenge.json
```

Il file `challenge.json` contiene solo ID, categorie e stati dei probe, senza accelerazioni vere. Crea un `submission.json` con il formato sopra e **una previsione per ogni probe del challenge**. Un esempio minimale per provare il percorso, che predice zero e quindi non rappresenta una scoperta, si può produrre senza leggere il mondo privato:

```powershell
$challenge = Get-Content benchmark_data/forge-demo/challenge.json -Raw | ConvertFrom-Json
$submission = @{
    predictions = @($challenge.probes | ForEach-Object { @{probe_id=$_.probe_id; ax=0.0; ay=0.0} })
    law_ast_json = '{"level":1,"ax":{"op":"const","value":0},"ay":{"op":"const","value":0}}'
    uncertainty_sigma = @($challenge.probes | ForEach-Object { 1.0 })
}
$submission | ConvertTo-Json -Depth 20 | Set-Content -Encoding utf8 benchmark_data/forge-demo/submission.json
.\.venv\Scripts\python.exe -m hidden_lab identify check --challenge benchmark_data/forge-demo/challenge.json --submission benchmark_data/forge-demo/submission.json
.\.venv\Scripts\python.exe -m hidden_lab identify score --world benchmark_data/forge-demo/world.json --session sessions/forge-demo --challenge benchmark_data/forge-demo/challenge.json --submission benchmark_data/forge-demo/submission.json --out benchmark_data/forge-demo/score-1
```

`check` valida solo il contratto e non calcola la verità. `score` ricontrolla challenge e sessione, salva prima la submission canonica in `public/submission.json`, poi valuta e salva `result.json` e gli audit `private/probe_truth.json` e `private/identification_grid.json`. La cartella è nuova e non viene sovrascritta. Una copia della verità privata non viene aggiunta al payload dei provider. I risultati possono essere consultati dall'operatore **dopo** il freeze; la CLI non gestisce la pubblicazione a terzi né un reveal competitivo.

## Interpretazione delle metriche

L'errore predittivo è RMSE, massimo e errore normalizzato su tutti i probe e separatamente per `interpolation` ed `extrapolation`. Per una legge AST, la valutazione usa 128 stati deterministici derivati da materiale privato: 64 per categoria. Riporta le stesse metriche e un indicatore di equivalenza **empirica** se ogni errore vettoriale è al massimo `0,001 + 0,001 × |accelerazione vera|` m/s². Non è una prova simbolica e può non scoprire differenze fra gli stati campionati. La griglia resta nell'audit privato; se il candidato non è definito su un suo stato, l'esito è `undefined_on_secret_grid`.

La complessità conta nodi totali, profondità massima e operazioni nell'AST. La correttezza delle dipendenze confronta sensibilità numeriche delle quattro variabili `(x, y, vx, vy)` su ancore della griglia: corrette, mancanti, spurie ed esatte. È un controllo empirico: cancellazioni locali, soglie e non linearità possono falsare l'esito. La calibrazione usa il modello gaussiano isotropo dichiarato: copertura radiale nominale al 68% e 95%, deviazione standard media e negative log likelihood media, anche per categoria. Con pochi probe, copertura e NLL sono descrittive, non una verifica statistica affidabile.

La griglia deterministica evita variazioni fra ricalcoli dello stesso trial, ma non garantisce segretezza crittografica o riproducibilità di un LLM. Un seed Forge prevedibile e il codice pubblico permettono di ricostruire il mondo: non usare questa CLI come challenge competitiva riservata. I trial reali con LLM e la capacità di identificare davvero una legge non sono ancora stati validati. I suggerimenti teorici dell'operatore possono influenzare la conclusione e vanno dichiarati.
