# Prima sessione con un agente LLM

Per usare l’abbonamento ChatGPT senza una chiave API aggiuntiva, segui [la guida OAuth e pilot](chatgpt-plan.md): `python -m hidden_lab chatgpt login`, poi `python -m hidden_lab chatgpt pilot`. Provider `chatgpt` distinto da `openai`; extra `.[chatgpt]`. La preview non accetta `max_output_tokens`; il limite locale non limita i token del servizio. Accesso e indagine reali ancora da verificare, nessun fallback a pagamento. Gli altri provider descritti sotto mantengono il collegamento esistente.

Questa guida è per l'operatore e riguarda la sessione CLI con LLM. Non viene inviata al modello. `investigate` conserva simulatore, validatori, registri, grafici e demo manuale e può usare OpenAI, Anthropic, Gemini, Ollama locale o il copione simulato. Il benchmark separato è ora alla v0.3.

Puoi anche generare un mondo AST di livello 1–5 con [World Forge](world-forge.md) e passare il suo `config.json` privato a `investigate`. Il payload del modello continua a contenere solo apparato e storia pubblica. I mondi AST non fanno parte delle suite benchmark v0.3. I primi tentativi Qwen reali non hanno prodotto esperimenti: capacità di scoperta ancora da verificare. Per il pilot Gemini gratuito con chiave nascosta e mondo nuovo segui [questa guida](pilot-llm.md).

## 1. Preparazione

Da PowerShell, nella cartella Zone:

```powershell
.\.venv\Scripts\python.exe -m pip install -e '.[all-llm]'
$env:PYTHONUTF8 = '1'
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Se non hai ancora l'ambiente virtuale, prima esegui `python -m venv .venv`. `all-llm` serve per l'intera suite offline; per una sola sessione basta uno fra `.[openai]`, `.[anthropic]`, `.[gemini]` e `.[ollama]`. L'extra storico `.[llm]` equivale a `.[openai]`. Ollama usa HTTPX, senza SDK specifico. Su Linux/macOS usa `.venv/bin/python` e la sintassi della tua shell per le variabili d'ambiente.

Lo sviluppo è stato verificato con Python 3.14.4, OpenAI SDK 2.54.0, Anthropic SDK 1.8.0, Google Gen AI SDK 2.25.0 e HTTPX 0.28.1. I test non richiedono credenziali reali: i trasporti o i client sono simulati e usano chiavi fittizie. Installare le dipendenze non effettua chiamate ai modelli. Senza un extra, i suoi test di adapter vengono saltati esplicitamente; per verificare tutti e quattro i provider installa `.[all-llm]`.

## 2. Provare il terminale senza rete

```powershell
.\.venv\Scripts\python.exe -m hidden_lab investigate --provider simulated --config examples/operator-world.json --session sessions/prova-simulata
```

Il terminale mostra **CLIENT SIMULATO**. È un copione prefissato, non un modello e non un algoritmo di scoperta. Per completarlo:

1. Digita `avvia` e rispondi alla domanda con testo libero.
2. Alla prima richiesta digita `a`, scrivi la motivazione, scegli `e` e infine `esegui`.
3. Leggi misure e ipotesi. Alla seconda richiesta digita `a`, scrivi la motivazione, scegli `v`.
4. Leggi la previsione preregistrata e digita `esegui`. Seguiranno metrica e conclusione del copione.

La demo produce 6 chiamate simulate, 6 turni validi e 2 esperimenti. `examples/simulated-operator-input.txt` contiene gli input umani equivalenti usati dal test CLI. Il client simulato incorporato non si adatta a scelte diverse; modifiche, rifiuti ed errori sono verificati nei test con copioni specifici. Un'interruzione in quel caso non implica un problema del simulatore fisico.

Per visualizzare il secondo esperimento:

```powershell
.\.venv\Scripts\python.exe -m hidden_lab plot --public sessions/prova-simulata/public --request check-1
```

Ogni avvio richiede una cartella nuova: usa nomi diversi per prove successive.

## 3. Avviare un modello reale

**Non c'è un modello reale predefinito**, né un passaggio automatico a un altro modello. Scegli un ID compatibile con l'API e il formato JSON Schema del provider. Indicalo con `--model` oppure con la variabile `<PROVIDER>_MODEL`; il flag ha precedenza. Per i provider remoti consulta cataloghi, abilitazioni e prezzi prima di avviare la sessione. Ogni esempio usa una cartella nuova e i limiti standard; puoi aggiungere `--max-calls`, `--max-turns`, `--timeout` e le altre opzioni della sezione 5.

**OpenAI.** Installa `.[openai]`, scegli un modello abilitato a Responses API e Structured Outputs ([modelli](https://developers.openai.com/api/docs/models), [prezzi](https://developers.openai.com/api/docs/pricing)).

```powershell
.\.venv\Scripts\python.exe -m pip install -e '.[openai]'
$zoneApiKey = Read-Host 'OpenAI API key' -AsSecureString
$env:OPENAI_API_KEY = [System.Net.NetworkCredential]::new('', $zoneApiKey).Password
Remove-Variable zoneApiKey
$env:OPENAI_MODEL = Read-Host 'ID del modello OpenAI'
.\.venv\Scripts\python.exe -m hidden_lab investigate --provider openai --config examples/operator-world.json --session sessions/prima-openai
Remove-Item Env:OPENAI_API_KEY
```

**Anthropic.** Installa `.[anthropic]` e scegli un modello Claude compatibile con [Structured Outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs). Il client usa Messages API e `output_config.format`.

```powershell
.\.venv\Scripts\python.exe -m pip install -e '.[anthropic]'
$zoneApiKey = Read-Host 'Anthropic API key' -AsSecureString
$env:ANTHROPIC_API_KEY = [System.Net.NetworkCredential]::new('', $zoneApiKey).Password
Remove-Variable zoneApiKey
$env:ANTHROPIC_MODEL = Read-Host 'ID del modello Anthropic'
.\.venv\Scripts\python.exe -m hidden_lab investigate --provider anthropic --config examples/operator-world.json --session sessions/prima-anthropic
Remove-Item Env:ANTHROPIC_API_KEY
```

**Gemini.** Installa `.[gemini]` e scegli un modello supportato dal [Google Gen AI SDK e dallo structured output](https://ai.google.dev/gemini-api/docs/generate-content/structured-output). La credenziale usa `GEMINI_API_KEY`; il client usa Gemini Developer API, non Vertex AI.

Il default usa schema vincolato. `--gemini-output-mode json` sceglie esplicitamente JSON con il medesimo contratto pubblico nel prompt, conservando la validazione locale e le conferme: può aiutare con incompatibilità del percorso schema, ma non c'è fallback automatico. Modalità registrata fra le impostazioni di generazione; le sessioni dei due modi non sono scientificamente equivalenti. Dettagli ed evidenze del pilot in [pilot LLM](pilot-llm.md).

```powershell
.\.venv\Scripts\python.exe -m pip install -e '.[gemini]'
$zoneApiKey = Read-Host 'Gemini API key' -AsSecureString
$env:GEMINI_API_KEY = [System.Net.NetworkCredential]::new('', $zoneApiKey).Password
Remove-Variable zoneApiKey
$env:GEMINI_MODEL = Read-Host 'ID del modello Gemini'
.\.venv\Scripts\python.exe -m hidden_lab investigate --provider gemini --config examples/operator-world.json --session sessions/prima-gemini
Remove-Item Env:GEMINI_API_KEY
```

**Ollama locale.** Installa `.[ollama]`. Installa e avvia Ollama separatamente, e assicurati che un modello capace di seguire un JSON Schema sia **già presente** sul computer: `ollama list` mostra gli ID locali. Il programma interroga soltanto `http://127.0.0.1:11434`, controlla `/api/tags`, rifiuta gli ID `:cloud` e non scarica modelli. Non serve alcuna chiave API. La qualità dipende dal modello locale e dalle risorse del computer.

```powershell
.\.venv\Scripts\python.exe -m pip install -e '.[ollama]'
ollama list
$env:OLLAMA_MODEL = Read-Host 'ID esatto del modello già installato'
.\.venv\Scripts\python.exe -m hidden_lab investigate --provider ollama --config examples/operator-world.json --session sessions/prima-ollama
```

Il programma mostra chiaramente il provider e il modello. **La prima generazione parte solo dopo `avvia`.** La preparazione del client e della sessione non invia richieste al modello; per Ollama, dopo `avvia` avviene prima un controllo locale della disponibilità. Una riga vuota non vale come conferma. `esci`, EOF o Ctrl+C interrompono la sessione. Le chiavi sono lette solo dalle rispettive variabili d'ambiente, non da argomenti CLI o file del progetto; non entrano nei registri. Gli esempi `Remove-Item` le rimuovono dalla shell corrente al termine del comando, ma un'interruzione della shell può lasciare la variabile impostata fino alla chiusura della shell.

## 4. Dialogare con l'agente

L'agente riceve l'apparato pubblico e propone un messaggio alla volta. Le richieste mostrano scopo, posizione e velocità iniziali, durata, intervallo e tempi di misura. I comandi dell'operatore sono:

| Prompt | Risposte |
| --- | --- |
| Decisione sull'esperimento | `a` approva; `m` modifica; `r` rifiuta; `esci` termina |
| Parametri di una modifica | Numeri; Invio conserva quel singolo valore; `conferma` accetta l'insieme |
| Motivazione | Testo pubblico non vuoto |
| Modalità dopo approvazione/modifica | `e` esplorazione; `v` verifica con previsione; `esci` termina |
| Conferma finale del lancio | Solo `esegui` autorizza; `esci` termina |
| Domanda dell'agente | Risposta testuale pubblica non vuota, oppure `esci` |

L'approvazione accetta i parametri ma non lancia ancora la particella. In modalità esplorativa arriva la conferma finale senza ulteriore chiamata al modello. In modalità verifica l'agente riceve prima la decisione, i parametri eventualmente modificati e la griglia esatta dei tempi. Può registrare un'ipotesi mancante, fare una domanda oppure dichiarare di non poter proseguire. Solo una previsione valida e preregistrata porta al prompt `esegui`.

Ogni esecuzione produce una tabella di tempo e posizione; la verifica aggiunge l'errore RMSE. Le misure vengono registrate **prima** della successiva richiesta API. Il modello vede osservazioni e punteggio attraverso la storia pubblica e può aggiornare le ipotesi con nuovi ID, proporre altro o concludere. Le formule scritte dal modello rimangono testo e non vengono valutate come codice.

In questa prima esperienza sono consentiti al massimo 9 punti di osservazione (si può abbassare con `--max-points`, minimo 2). Il motore manuale conserva il limite precedente di 101 punti. Il rumore rimane disattivato nella configurazione di esempio.

La conclusione contiene `final_hypothesis_id`, `summary`, `evidence`, `limits`, `alternatives`. L'ipotesi finale deve esistere oppure essere `null`, per informazioni insufficienti. Le evidenze devono riferirsi a misure riuscite già ricevute; deve essere dichiarato almeno un limite. Una conclusione annulla un eventuale lancio in attesa e chiude l'indagine.

**Le risposte e le motivazioni dell'operatore sono dati pubblici.** Suggerimenti teorici possono orientare il modello: annotali nella valutazione e non confonderli con scoperte autonome. Il software non può impedire a una persona di rivelare deliberatamente la legge in un testo libero.

## 5. Budget, errori e timeout

| Opzione | Default | Effetto |
| --- | --- | --- |
| `--max-calls` | 20 | Tentativi API totali, incluse correzioni, timeout ed errori |
| `--max-turns` | 15 | Messaggi validi accettati dal modello, incluse domande e ipotesi |
| `--max-corrections` | 2 | Chiamate aggiuntive dopo una risposta non valida per lo stesso passo |
| `--timeout` | 30 s | Timeout SDK/HTTPX: 1–120 s remoto, fino a 600 s con Ollama locale; default invariato |
| `--max-output-tokens` | 2500 | Limite di generazione per chiamata, compresi gli eventuali token di ragionamento |
| `--max-input-bytes` | 200000 | Dimensione massima locale del payload JSON prima dell'invio |
| `--max-points` | 9 | Campioni massimi per esperimento in `investigate` |

Il budget degli esperimenti è quello della configurazione dell'operatore; conta ogni lancio avviato anche quando invalido. È indipendente dalle chiamate al modello. `max_calls` è un limite di tentativi, **non un tetto di spesa in euro**: il costo dipende da modello e token. Un timeout può avvenire dopo che il provider ha iniziato a elaborare; l'utilizzo può quindi essere sconosciuto e non implica costo zero.

Il timeout di rete non è una scadenza totale dell'indagine né un limite sul tempo di risposta umano. Non sono implementati streaming o attese con approvazione automatica. Le operazioni di connessione, lettura, scrittura e pool hanno il timeout impostato; il tempo totale della chiamata può essere superiore al singolo timeout.

Una risposta JSON malformata, incompleta, rifiutata dal provider o non valida per lo stato corrente non modifica l'esperimento: registra un `protocol_error` generico e consente correzioni entro entrambi i limiti. L'output grezzo non valido non viene aggiunto ai registri o al contesto successivo. Esaurite le correzioni, l'indagine termina senza inventare una conclusione.

Gli errori HTTP/rete fermano invece la sessione subito. OpenAI e Anthropic usano `max_retries=0`; Gemini configura un unico tentativo; il client Ollama non ripete le richieste. Un errore dopo una misura **non rilancia l'esperimento**. Gli errori del provider sono riportati con codici locali, senza corpi HTTP, header o credenziali. `authentication` indica un problema di credenziale/permesso, `rate_limit` un limite del provider, `request_rejected` anche eventuale incompatibilità del modello o formato; per Ollama locale compaiono anche `service_unavailable` e `model_unavailable`. Correggi la configurazione e avvia una nuova sessione: non c'è ancora ripresa automatica.

Codici di uscita CLI: `0` conclusione registrata; `2` indagine interrotta senza conclusione (anche stop dell'operatore); `1` errore locale di configurazione o I/O. Un limite raggiunto viene registrato come `investigation_stopped`, distinto dalla conclusione del modello. I registri non sono transazionali tra loro: un arresto improvviso può lasciare una chiamata o un lancio soltanto avviato.

## 6. Cosa viene inviato e registrato

`agent_contract.build_request()` accetta eventi pubblici, impostazioni del modello e contatori pubblici; non accetta un oggetto `Session`, una configurazione fisica o un percorso. Costruisce una richiesta canonica con:

- istruzioni pubbliche statiche, senza elenco delle famiglie fisiche;
- schema dei messaggi ammessi nella fase corrente;
- storia pubblica, proiettata mediante liste positive di campi anche negli oggetti annidati;
- fase, budget residui, limite di campioni e, per una verifica, parametri approvati e tempi.

Non legge README, codice, configurazione privata o copioni. Gli adapter traducono solo la richiesta canonica nei rispettivi formati: non allegano file né espongono strumenti di filesystem, terminale, interprete o ricerca. Nessuno riceve `Session`; ogni richiesta è ricostruita dalla storia pubblica. OpenAI imposta `store=False` e `truncation="disabled"`; `store=False` non è una promessa generale di conservazione zero del provider. Gli endpoint remoti sono quelli ufficiali, senza proxy o URL alternativi letti dall'ambiente; Ollama usa solo l'indirizzo di loopback fisso. I provider possono trattare diversamente lo stesso JSON Schema e lo stesso limite di output: la validazione applicativa di Zone resta identica, ma ciò **non rende le sessioni un benchmark comparabile**.

Il codice locale e l'SDK sono componenti fidati. È un confine applicativo di trasmissione al modello remoto, non una sandbox del processo Python. Un futuro agente con accesso locale a file o terminale richiederebbe ulteriori restrizioni.

I nuovi registri sono in `private/`, accanto alla configurazione di riproducibilità già esistente:

| File | Contenuto |
| --- | --- |
| `agent_settings.jsonl` | Provider reale/simulato, modello richiesto, versione SDK o trasporto, versione adapter, limiti e impostazioni di generazione |
| `model_calls.jsonl` | Riga `started` prima della chiamata e riga finale con indice, fase, fingerprint delle istruzioni e dello schema, riferimento pubblico, esito, modello restituito, ID risposta se disponibile, utilizzo e durata |

L'audit mantiene i contatori **nativi**. OpenAI riporta `input_tokens`, `output_tokens` e `total_tokens` (con eventuali dettagli cache/ragionamento). Anthropic riporta `input_tokens`, `output_tokens` e, se presenti, conteggi cache separati; `total_tokens` rimane `null` perché non viene inventato. Gemini conserva `prompt_token_count`, `candidates_token_count`, `total_token_count`, `thoughts_token_count` e cache in `provider_details`; Ollama conserva `prompt_eval_count`, `prompt_eval_cached_count` ed `eval_count` nello stesso campo. Per Gemini, Ollama e client simulato il campo comune `usage` è `null`: non significa zero token. In caso di errore di rete l'utilizzo è ignoto. Per analizzare i conteggi considera solo le righe finali, non le righe `started`, e non sommare ciecamente unità o categorie diverse. Il modello effettivo restituito può essere più specifico dell'alias richiesto.

Non vengono registrati chiave API, ambiente, header, oggetti SDK completi o corpi degli errori. Il protocollo pubblico conserva domande, risposte, decisioni, modalità, previsioni, misure e conclusioni. Modello, impostazioni e utilizzo forniscono tracciabilità; **non garantiscono la riproducibilità esatta delle risposte LLM**, anche usando gli stessi dati.

## 7. Confrontare sessioni singole

Una sessione resta legata a un solo provider e un solo modello dall'inizio alla fine. Per un confronto futuro avvia cartelle **nuove e separate**, con la stessa configurazione fisica nascosta oppure configurazioni generate con la stessa procedura e seed. Imposta gli stessi budget di esperimenti, chiamate e turni, gli stessi limiti di campioni e output, e una storia iniziale equivalente. Mantieni coerente il comportamento dell'operatore, in particolare non dare suggerimenti teorici diversi ai vari agenti. Non riutilizzare per un modello una sessione che già contiene richieste, decisioni o osservazioni nate dall'indagine di un altro.

Lo stesso limite numerico di token non significa identica quantità di calcolo: provider diversi usano tokenizzazioni, vincoli dello schema, impostazioni predefinite e modalità di ragionamento differenti. Anche la conformità effettiva allo schema può differire; Zone applica comunque la medesima validazione finale. I registri permettono di descrivere tali differenze, non di dichiarare le sessioni scientificamente equivalenti. [Zone Benchmark v0.3](benchmark.md) è implementato con quattro condizioni: `passive_fixed` riceve la schedule completa in batch come diagnosi; `passive_sequential` riceve la stessa schedule un esperimento alla volta e ha un'occasione di ragionamento dopo ogni osservazione, per il confronto principale con `active`. Include due baseline offline limitate; non sono ancora stati validati trial con modelli reali né confronti multi-modello.

Dopo una conclusione, la [fase di identificazione](identification.md) permette una submission AST e incertezze numeriche facoltative. Nei trial benchmark v0.3 il modello può inviarle nel messaggio finale; nelle sessioni interattive un operatore può rilasciare il challenge e presentare lo stesso sottoinsieme scientifico da file. Il percorso è stato verificato offline, non con un modello reale.

## 8. Verifiche eseguite e ancora necessarie

Sono verificati offline il ciclo completo attraverso la CLI, la domanda e risposta umana, l'esplorazione, le ipotesi, una verifica preregistrata e la conclusione. Copioni specifici coprono rifiuto, modifica prima della previsione, risposta malformata e correzione, esaurimento dei budget, input vuoto, EOF, errori di rete e assenza di doppie esecuzioni. Sono conservati i test precedenti di dinamica e registrazione.

OpenAI e Anthropic sono esercitati con gli SDK reali e trasporti HTTP fittizi; Gemini con un doppio dell'SDK che restituisce oggetti di risposta del suo pacchetto; Ollama con HTTPX `MockTransport`. Senza chiamate a modelli controlliamo payload, timeout, assenza di retry, metadati, contatori nativi, HTTP 400/401/429/500, risposte incomplete e confine informativo. Test con valori sentinella verificano che segreti e informazioni private non entrino nei payload o nei registri dell'agente.

**La fase 12 ha completato il primo pilot locale reale.** Dopo i tentativi Qwen/Gemini e la correzione del lettore streaming, [ChatGPT con OAuth ufficiale](chatgpt-plan.md) ha concluso otto turni validi e tre esperimenti autorizzati, con ipotesi, una previsione preregistrata e conclusione. L’autore conferma in Usage sola quota dell’abbonamento e nessun credito extra. Il [resoconto verificato](pilot-chatgpt-result.md) riporta utilizzo, latenza e RMSE, distinguendo successo operativo e limiti scientifici: un mondo e tempi fino a 0,2 s non validano il benchmark, Arena o una legge unica. Modifica, rifiuto, domanda/risposta e varianti d’errore restano verificati con client simulato. I tentativi precedenti sono conservati in [pilot LLM](pilot-llm.md).

## Riferimenti ufficiali consultati

Consultati il 23 settembre 2026: [OpenAI Responses API](https://developers.openai.com/api/reference/python/resources/responses/methods/create) e [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs); [Anthropic Messages API](https://platform.claude.com/docs/en/api/python/messages/create) e [Structured Outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs); [Google Gemini structured output](https://ai.google.dev/gemini-api/docs/generate-content/structured-output) e [Google Gen AI SDK](https://googleapis.github.io/python-genai/); [Ollama structured output](https://docs.ollama.com/capabilities/structured-outputs), [chat](https://docs.ollama.com/api/chat) e [modelli locali](https://docs.ollama.com/api/tags). Lo schema non sostituisce i validatori applicativi: limiti fisici, riferimenti e ordine temporale restano verificati da Zone.
