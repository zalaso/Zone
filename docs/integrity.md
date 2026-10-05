# Integrity v1 — fase 8

Zone separa la pratica pubblica dal test riservato con pacchetti versionati. I controlli sono locali e applicativi; non certificano assenza di contaminazione, identità dei partecipanti o capacità scientifiche di un modello. Il [threat model](threat-model.md) descrive fiducia e attacchi residui.

## Split e commitment

`integrity prepare` produce `public/train.json` e `public/development.json` con **record completi, leggi e seed inclusi**, `public/manifest.json`, `private/test.json` e `private/pack.json`. Pubblicare soltanto la cartella `public`, senza una proof finché la challenge è aperta. Il database e la cartella `private` rimangono sul server fidato; non sono risorse statiche del frontend. Le leggi pubbliche servono alla pratica e non sono ammissibili alle challenge cieche.

La versione del pacchetto è `1`. `--kind forge` riusa World Forge v1 e la sua validazione, con livelli 1–5 e fino a cinque casi per livello/split. Il budget predefinito è tre: budget piccoli possono non avere una schedule informativa e vengono rifiutati dal generatore esistente. `--kind benchmark` crea tre suite nel formato v0.3 originario, otto casi per split; `--levels` e `--per-level` riguardano solo Forge. Non introduce nuove famiglie fisiche.

Il seed radice è casuale a 128 bit per default. Seed dei casi e nonce sono derivati con SHA-256 e domini distinti; i seed train/development non permettono di ricostruire lo stato di un generatore pseudocasuale condiviso. `--seed` è utile soltanto per demo ripetibili: pubblicarlo rende ricostruibile anche il test. Non riutilizzare un pacchetto demo come valutazione cieca.

Il manifest pubblico elenca hash dei dataset pubblici e ID opachi; per il test espone ID e commitment salati, senza hash grezzi del mondo/probe, seed, livello, legge o nonce. Il commitment è SHA-256 della serializzazione canonica del dominio `zone-integrity-v1`, ID, record completo e nonce. **Conservare l'hash del manifest prima del trial**, su un canale separato dal successivo reveal: un hash senza riferimento originale non impedisce di sostituire manifest e proof insieme. Non esistono ancora firma o notarizzazione esterna.

## Percorso offline completo

Dalla radice, con ambiente virtuale ed extra backend già installati, usare percorsi nuovi:

```powershell
.\.venv\Scripts\python.exe -m hidden_lab integrity prepare --kind forge --levels 1 2 3 4 5 --budget 3 --seed 800123 --out benchmark_data/integrity-forge-demo
.\.venv\Scripts\python.exe -m hidden_lab integrity check --pack benchmark_data/integrity-forge-demo
$pinnedManifestHash = (Get-Content benchmark_data/integrity-forge-demo/public/manifest.json -Raw | ConvertFrom-Json).sha256
.\.venv\Scripts\python.exe -m hidden_lab arena demo --db benchmark_data/integrity-forge-demo/arena.sqlite3 --integrity-pack benchmark_data/integrity-forge-demo/private/pack.json --proof-out benchmark_data/integrity-forge-demo/public/demo-reveal.json
.\.venv\Scripts\python.exe -m hidden_lab integrity verify-reveal --manifest benchmark_data/integrity-forge-demo/public/manifest.json --proof benchmark_data/integrity-forge-demo/public/demo-reveal.json --expected-manifest-hash $pinnedManifestHash
```

La demo sceglie il primo caso test, usa la baseline affine pubblica e un operatore simulato esplicito, congela la submission, valuta, chiude, effettua il reveal richiesto da `--proof-out`, verifica la proof e revoca il token. Non chiama un LLM. Omettere `--proof-out` conserva il caso senza reveal; la challenge test comunque non è riapribile. Lo stato `blind_test` indica la provenienza del catalogo, non attesta una demo con seed noto come esperimento scientifico cieco.

Benchmark offline nelle quattro condizioni, con fixture oracolo chiaramente diagnostico:

```powershell
.\.venv\Scripts\python.exe -m hidden_lab integrity prepare --kind benchmark --seed 810456 --budget 1 --out benchmark_data/integrity-benchmark-demo
.\.venv\Scripts\python.exe -m hidden_lab integrity check --pack benchmark_data/integrity-benchmark-demo
$integritySuite = Get-Content benchmark_data/integrity-benchmark-demo/private/test.json -Raw | ConvertFrom-Json
foreach ($condition in @('prior_only','passive_fixed','passive_sequential','active')) {
  .\.venv\Scripts\python.exe -m hidden_lab benchmark trial --suite benchmark_data/integrity-benchmark-demo/private/test.json --integrity-pack benchmark_data/integrity-benchmark-demo/private/pack.json --world $integritySuite.worlds[0].id --condition $condition --provider simulated --yes --out "benchmark_data/integrity-benchmark-demo/runs/$condition"
  if ($LASTEXITCODE -ne 0) { throw 'Trial non completato' }
}
.\.venv\Scripts\python.exe -m hidden_lab benchmark aggregate --runs benchmark_data/integrity-benchmark-demo/runs --out benchmark_data/integrity-benchmark-demo/aggregate.json
.\.venv\Scripts\python.exe -m hidden_lab benchmark report --aggregate benchmark_data/integrity-benchmark-demo/aggregate.json --out benchmark_data/integrity-benchmark-demo/report.md
```

`--integrity-pack` verifica l'uguaglianza esatta tra suite/caso e split, e registra manifest, split e commitment nei risultati. Aggregazioni con split, manifest diversi o trial tracciati/non tracciati mescolati vengono rifiutate; restano tutti i controlli di appaiamento v0.3. I risultati precedenti continuano a essere leggibili senza il nuovo campo. La CLI benchmark è un processo fidato che possiede i file privati: il binding è provenienza locale, non un'attestazione crittografica dei risultati. La gestione di accesso, embargo, reveal e ritiro è applicata da Arena/SQLite, non da un registro globale delle esecuzioni CLI.

## Arena con test privato

Preparazione per un futuro pilot, **non eseguito con modelli reali durante lo sviluppo**:

```powershell
# Omettere --seed e usare una cartella nuova. Un caso per split, livello 1.
.\.venv\Scripts\python.exe -m hidden_lab integrity prepare --kind forge --levels 1 --budget 3 --out benchmark_data/integrity-pilot
.\.venv\Scripts\python.exe -m hidden_lab integrity check --pack benchmark_data/integrity-pilot
$pinnedManifestHash = (Get-Content benchmark_data/integrity-pilot/public/manifest.json -Raw | ConvertFrom-Json).sha256
# ZONE_OPERATOR_TOKEN: impostato separatamente nel proprio ambiente, mai in prompt o registri.
.\.venv\Scripts\python.exe -m hidden_lab serve --db benchmark_data/integrity-pilot/zone.sqlite3 --integrity-pack benchmark_data/integrity-pilot/private/pack.json --port 8766
```

In un secondo terminale `cd frontend`, impostare `$env:ZONE_BACKEND_URL = 'http://127.0.0.1:8766'`, poi `pnpm dev --host 127.0.0.1`. Aprire la UI, connettere Arena, selezionare l'ID test dal manifest (solo i mondi `blind_test` sono candidati ciechi), creare **una challenge sul solo caso test**, registrare un account agente e passare al proprio runner soltanto token agente e challenge ID. Il runner BYOA reale resta da validare: esempi di client e costruzione del payload in [Arena](arena.md), nessun comando qui avvia automaticamente un provider. La registrazione del nome modello non fa chiamate. Le credenziali provider rimangono nell'ambiente del runner, esterno al server.

Le route pubbliche `GET /v1/integrity/manifests` e `GET /v1/integrity/packs/{pack_id}/train|development` espongono solo manifest e split pubblici; `/test` restituisce `404`. Questi dataset non sono allegati automaticamente a un payload provider. Il payload contiene solo istruzioni, contratto e storia pubblica positiva; eventuale uso volontario dei dati train da parte di un client va dichiarato nel protocollo di valutazione.

Il server riserva i mondi test ad Arena, impedisce sessioni Scientist/match/daily sul test e registrazioni di alias fisici. Un test ammette una sola challenge nel catalogo. I punteggi del proprietario, inclusi replay e receipt di submission, rimangono `null` fino alla chiusura; l'operatore può ispezionarli per gestire il laboratorio. La leaderboard richiede tutti i trial terminati prima di essere visibile agli agenti. Il reveal richiede conferma, challenge chiusa e nessuna indagine aperta sulla stessa legge; controllo e ritiro avvengono nella stessa transazione di scrittura. Reimportare un pacchetto non azzera ritiro o flag.

Il reveal Arena restituisce una `integrity_proof` con **soltanto quel caso** e il nonce. Il record è una stringa JSON canonica in `record_json`: conservarla come testo evita che JavaScript cambi la rappresentazione numerica del commitment (`0.0`/`0`). La risposta contiene anche il record leggibile in `world`. Salvare la proof in un nuovo file e verificare con `integrity verify-reveal` e l'hash conservato prima della sessione. Un reveal ritira il caso: non può creare nuovi trial o challenge cieche. I risultati storici precedenti al reveal mantengono la provenienza del trial; il ritiro non riscrive la storia.

## Contaminazione, duplicati e abuso

L'operatore può inviare `POST /v1/arena/sessions/{id}/integrity` con `expected_version` e `reason`: `operator_hint`, `known_law`, `external_disclosure`, `protocol_violation`. La UI offre lo stesso controllo. Sono flag append-only, registrati negli eventi e persistenti; i risultati e le risorse restano disponibili ma il trial non riceve ranghi. Suggerimenti teorici dell'operatore possono influenzare i risultati e richiedono un flag anche quando vengono comunicati fuori dal sistema. Non esiste un rilevatore automatico di conoscenze private del partecipante.

Il catalogo rifiuta duplicati strutturali (AST normalizzato per ordine commutativo) o leggi con RMSE ≤ `1e-6` su una griglia privata fissa di 16 stati. Vale tra split, pacchetti importati e mondi già esposti/builder. Importazioni test con alias o indagini preesistenti sono rifiutate atomicamente. La griglia è una **euristica finita e conservativa**, non una dimostrazione di equivalenza o un controllo su tutte le distribuzioni: può avere falsi positivi/negativi.

Oltre alle quote account di sessioni/richieste/esperimenti e al limite IP esistente, Arena persiste per account 120 letture e 30 scritture in una finestra di 60 secondi. Anche lookup errati e receipt ripetuti consumano la finestra. Rotazione dei token e riavvio non azzerano questi limiti. Dopo 20 mutazioni invalide vengono bloccate nuove chiavi di scrittura, lasciando all'operatore arresto e revoca. Le risposte idempotenti già salvate restano consultabili entro il limite di frequenza. Nessun errore di rete riesegue automaticamente un esperimento. Queste quote non misurano chiamate LLM, token o costi esterni.

I mondi storici senza split conservano il comportamento compatibile, ma i report Arena sono marcati `diagnostic_untracked`; non sono test ciechi certificati. Un database nuovo che importa nuovamente un pacchetto già divulgato non può sapere della divulgazione avvenuta altrove: il gestore deve usare casi nuovi e segnalare contaminazioni esterne. File privati e proof di demo restano nella cartella ignorata `benchmark_data`; Git ignore non sostituisce permessi del filesystem o un controllo dei file pubblicati.
