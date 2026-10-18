# Fase 12 — pilot LLM, 8 ottobre 2026

> Historical/advanced engineering reference. For the version 1.0 supported installation start with [Getting started](getting-started.md), [AI connections](ai-connections.md) and [self-hosting](self-hosting.md). Earlier phase statuses describe that earlier revision, not missing release features or a current hosted service.


Stato: **fase 12 completata nel perimetro del primo pilot locale**. ChatGPT ha concluso un’indagine con otto chiamate valide, tre esperimenti e una verifica preregistrata; l’autore ha confermato in Usage il consumo della sola quota dell’abbonamento, senza crediti extra. Quattro generazioni Qwen locali e sei chiamate Gemini precedenti, avviate dall’autore, restano documentate sotto. Nessuna nuova inferenza avviata da Codex durante la verifica dei registri. Nessun download di modelli. Uso delle chiamate fallite ignoto.

Il percorso scelto dall’autore è **[Sign in with ChatGPT](chatgpt-plan.md)**: login OAuth ufficiale e pilot con l’abbonamento, senza API key aggiuntiva. Dopo il primo tentativo con tre risposte invalide e la correzione dello stream, la sessione `pilot12-chatgpt-f94542b8deee` ha completato richiesta, osservazioni, ipotesi, previsione e conclusione senza errori. Utilizzo totale 21393 token; tempo delle chiamate 63,351 s; RMSE della verifica 3,49 × 10^-16 m, all’ordine dell’arrotondamento numerico. Il [resoconto verificato](pilot-chatgpt-result.md) distingue risultato operativo, limiti scientifici e controllo dell’utilizzo dichiarato dall’autore. Gemini resta disponibile e i registri precedenti sono conservati.

## Avviare Gemini Free Tier

Questa procedura resta disponibile; per il nuovo pilot scelto usa [ChatGPT](chatgpt-plan.md).

Da un terminale PowerShell interattivo nella cartella `C:\path\to\Zone`. Non usare il terminale come copione con approvazioni prefissate.

1. Apri [API Keys in Google AI Studio](https://aistudio.google.com/api-keys), accedi e crea/seleziona un progetto dedicato a Zone. Un account nuovo può avere già progetto e chiave predefiniti; verifica comunque il progetto nella sezione Projects. Vedi la [guida ufficiale alle chiavi](https://ai.google.dev/gemini-api/docs/api-key).
2. Verifica che quel progetto risulti **Free Tier**, senza fatturazione attiva. Non scegliere Set up billing, crediti o upgrade per questa prova. Le chiavi ereditano il piano del progetto: il budget GitHub Actions zero non si applica a Google. [Billing ufficiale](https://ai.google.dev/gemini-api/docs/billing).
3. Controlla modello e quota gratuita in AI Studio. Al controllo dell'8 ottobre 2026, `gemini-3.8-flash` è stabile, supporta structured output e ha input/output gratuiti nel piano Free Tier standard. È un candidato esplicito nel comando, senza default nel codice. Se non disponibile nel progetto, fermati; niente cambio automatico di modello/piano. Fonti: [scheda modello](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash), [prezzi](https://ai.google.dev/gemini-api/docs/pricing), [quote](https://ai.google.dev/gemini-api/docs/rate-limits).
4. Crea la chiave in quel progetto. Non incollarla in chat, file, argomenti CLI, risposte all'agente o registri. Il comando seguente la chiede con input nascosto.

```powershell
Set-Location C:\path\to\Zone
$env:PYTHONUTF8 = '1'
.\.venv\Scripts\python.exe -m tools.free_gemini_pilot --model gemini-3.8-flash --gemini-output-mode json
```

Gli SDK sono già presenti nell'ambiente di questo PC. In un altro checkout serve prima installare `.[gemini]`; il launcher non installa né scarica nulla. Lo script è incluso nei sorgenti, non nella wheel del pacchetto. Il comando sopra sceglie esplicitamente la modalità JSON alternativa dopo i fallimenti dello schema vincolato: ha prodotto una richiesta e un esperimento reali, ma l’indagine si è interrotta alla chiamata successiva. Senza il flag resta il default `schema`.

Il launcher chiede di digitare `free` **dopo il controllo umano del piano e della quota**, genera e valida un mondo Forge livello 1 con seed casuale non pubblicato, budget tre esperimenti e percorsi nuovi sotto `benchmark_data/pilot12-gemini-<id>`. Chiede la chiave nascosta e avvia `investigate` con la cartella nuova `sessions/pilot12-gemini-<id>` mostrata sul terminale. La credenziale passa all'adapter soltanto tramite `GEMINI_API_KEY` nel processo; al termine, anche per errore/interruzione, il precedente ambiente del processo viene ripristinato. Non viene modificata la shell chiamante. Se l'input non è interattivo o non può essere nascosto, l'avvio si ferma. La chiave resta in memoria durante l'indagine; non è una sandbox del processo.

**Il programma non può attestare il piano dell'account:** `free` conferma un controllo umano, non verifica Google e non garantisce un tetto di spesa. La gratuità dipende dal progetto e dal modello controllati prima della chiamata. La CLI conserva impostazioni/utilizzo ma non calcola un costo monetario certificato. La storia pubblica viene trasmessa a Google; questa guida e la configurazione privata non vengono inviate. Per il trattamento dei dati del Free Tier consulta [i termini del provider](https://ai.google.dev/gemini-api/terms).

Limiti espliciti: **8 chiamate totali**, **8 messaggi validi**, fino a **2 correzioni** per passo entro il tetto totale, **120 s** di timeout rete, **2500 token output** per chiamata compresi eventuali token di ragionamento, **3 punti** per esperimento e **3 esperimenti**. Il budget modello è distinto da quello fisico. Nessun retry di rete o rilancio automatico; con `rate_limit`, `request_rejected` o timeout la sessione resta conservata e si arresta. Non attivare fatturazione per superare una quota.

## Operare la sessione

- Digita `avvia` per consentire la prima generazione. Input vuoto e silenzio non autorizzano nulla.
- Rispondi alle domande dell'agente con testo libero; le risposte sono pubbliche. Suggerimenti teorici possono influenzare l'indagine e vanno dichiarati nella valutazione.
- Leggi richiesta, scopo, parametri e tempi. Scegli `a` per approvare, `m` per modificare, `r` per rifiutare; scrivi una motivazione non vuota.
- Dopo approvazione/modifica scegli `e` (esplorazione) o `v` (verifica). In verifica, il modello vede prima i parametri definitivi e deve preregistrare tutti i punti previsti. Il lancio parte solo digitando `esegui`.
- `esci`, EOF o Ctrl+C interrompono. Non c'è ripresa automatica: conserva i registri e usa percorsi nuovi per un'altra prova.

Richieste, decisioni, osservazioni, ipotesi, previsioni e conclusione sono in `public/events.jsonl`. Modello, limiti, versione SDK, esiti, latenza e conteggi nativi restituiti da Gemini sono in `private/agent_settings.jsonl` e `private/model_calls.jsonl`. Nei conteggi considera soltanto righe finali: `started` non è una chiamata aggiuntiva. Uso ignoto non significa zero; niente promessa di risposte esattamente riproducibili. L'agente non riceve Session, strumenti, file, roadmap, livello/seed, elenco delle leggi o verità privata. Formule restano testo; previsioni esclusivamente numeriche.

## Primo tentativo Gemini e diagnosi

L'autore ha avviato `sessions/pilot12-gemini-fc1ebde5f608` con `gemini-3.8-flash`, SDK 2.25.0, timeout 120 s e le impostazioni del launcher. Una sola chiamata iniziale, terminata in **120,843 s**: `outcome=provider_error`, **`error_code=server_error`**, utilizzo ignoto. Nessun messaggio valido, esperimento o retry. La sessione resta conservata. `server_error` deriva da un errore API con codice almeno 500; non è il codice locale `timeout`, né dimostra che la chiave sia invalida. Il corpo e il codice HTTP specifico non sono conservati, quindi non possiamo attribuire una causa precisa.

Per separare disponibilità del servizio/accesso al modello da un problema con la richiesta completa, il launcher offre una diagnostica esplicita. Cambia soltanto il contenuto della richiesta: stesso modello, adapter, timeout e limite output, schema JSON minimo. Non genera un mondo, non crea Session, non legge configurazioni private e non avvia il pilot dopo la diagnostica.

```powershell
.\.venv\Scripts\python.exe -m tools.free_gemini_pilot --model gemini-3.8-flash --diagnostic
```

Controllo umano Free Tier e chiave nascosta restano obbligatori. **Una chiamata aggiuntiva** con schema `{ok: boolean}`, nessun retry, zero esperimenti. L'esito ridotto, impostazioni e metadati nativi sono salvati in un nuovo `benchmark_data/pilot12-gemini-<id>/private/connectivity-result.json`; output grezzo e segreti non vengono salvati. `JSON valido` dimostra soltanto accesso e risposta minima in quel momento. Un altro `server_error` non consente di dare la colpa al protocollo fisico. Nessuna modifica speculativa a temperature, thinking, modelli o retry del pilot. Vedi [diagnosi ufficiale Google](https://ai.google.dev/gemini-api/docs/troubleshooting).

Diagnostica reale eseguita dall'autore e riscontrata nel registro `benchmark_data/pilot12-gemini-887d2321bcc7/private/connectivity-result.json`: **JSON valido in 4,251 s**, una chiamata, zero esperimenti, modello restituito `gemini-3.8-flash`. Conteggi nativi: `prompt_token_count=34`, `candidates_token_count=5`, `thoughts_token_count=107`, `total_token_count=146`; cache non restituita. Dimostra accesso a quel modello tramite l'adapter e risposta al JSON minimo, non accettazione del contratto completo, qualità scientifica o gratuità del progetto. Il prossimo passo è un tentativo completo avviato esplicitamente dall'operatore con il comando iniziale senza `--diagnostic`, cartelle nuove e le stesse impostazioni. La sessione precedente resta chiusa; nessuna ripresa o ritrasmissione automatica.

Ulteriori tentativi completi dell'autore: `sessions/pilot12-gemini-78027aca516a`, una chiamata `server_error` in **4,627 s**; `sessions/pilot12-gemini-3115735d1e38`, una chiamata `server_error` in **6,109 s**. Zero turni validi ed esperimenti in entrambi. Il fallimento rapido ripetuto della richiesta completa, mentre il JSON minimo riesce, rende il percorso dello schema un sospetto più forte; non prova una causa precisa. Non vengono richieste ripetizioni identiche indefinite.

### Modalità Gemini JSON alternativa

`--gemini-output-mode json` è disponibile nella CLI `investigate` e nel launcher; il default rimane `schema`. In `json` l'adapter chiede `application/json` ma non passa `response_json_schema`: allega invece il medesimo schema pubblico sotto `message_contract` insieme alla storia e a `next_action`. Il modello mantiene la scelta fra richieste, ipotesi, domande e conclusione, oppure previsione nella fase appropriata. Non vengono aggiunte informazioni private o strumenti. Chiamate automatiche di funzioni dell'SDK disabilitate esplicitamente anche in `schema`.

La validazione locale è identica: contenitore, chiavi, numeri, limiti fisici, pochi punti, tipi consentiti nella fase, riferimenti, modifica prima della previsione e conferme umane. Il provider garantisce soltanto JSON: possono aumentare le risposte invalide, con lo stesso limite di correzioni e chiamate. Nessun fallback dopo un errore, nessun retry di rete, nessun cambio modello/timeout/temperatura/thinking. La modalità è salvata in `generation_settings.output_mode`, insieme al flag `response_json_schema`; i conteggi restano nativi. Questa scelta non cambia il formato dei registri o il benchmark v0.3 e non rende confrontabili trial con diverse impostazioni di generazione. La CLI benchmark mantiene il percorso schema preesistente.

È un percorso di compatibilità esplicito per il prossimo tentativo, **non una riparazione del servizio Gemini attestata**. Test offline con SDK reale e HTTP fittizio verificano l'assenza del parametro schema sulla richiesta serializzata e la presenza del contratto pubblico nel prompt; un ciclo con SDK simulato copre domanda, approvazione, misura, ipotesi, modifica, previsione e conclusione, oltre al rifiuto applicativo di richieste fuori dominio. Riferimenti: [output strutturati e limiti](https://ai.google.dev/gemini-api/docs/structured-output), [API generateContent](https://ai.google.dev/api/generate-content).

## Primo esperimento Gemini reale

Nella sessione `sessions/pilot12-gemini-c2c3a8c7fbc9`, modalità JSON, l’autore ha ricevuto `exp_probe_rest` in **7,319 s**, approvato con motivazione `prova`, scelto esplorazione e autorizzato il lancio con `esegui`. Tre posizioni sono state registrate; un esperimento consumato, due rimasti. La chiamata 2 si è fermata con `server_error` in **5,377 s**. Nessun rilancio, ipotesi, previsione o conclusione. Utilizzo della chiamata accettata: prompt 1428, risposta 118, ragionamento 492, totale 2038; quello della chiamata fallita è ignoto. Il codice HTTP esatto di questo errore non era ancora registrato. La prima richiesta valida non dimostra che il problema del servizio sia risolto.

## Evidenze Qwen conservate

Host Windows con circa 6,9 GiB RAM, Radeon Vega 3. Ollama **0.35.0** riporta `qwen2.5:3b-instruct`, ID `357c53fb659c`, 2,2 GB, **100% CPU**, contesto 4096. Modello già installato; nessun download. Mondo Forge nuovo, validato, seed non pubblicato, budget tre lanci. Nessuna legge privata consultata per guidare l'agente.

| Prova | Risultato reale | Esperimenti |
| --- | --- | --- |
| `sessions/phase12-qwen-01` | Prima chiamata: timeout in 120,128 s, output limitato a 768 token; utilizzo ignoto | 0 |
| Diagnostica JSON minima separata | Schema `{ok: boolean}` senza apparato: valido in 9,268 s; 41 token prompt, 7 generati. Caricamento 0,089 s, prompt 5,363 s, generazione 1,992 s | 0 |
| `sessions/phase12-qwen-02`, chiamata 1 | JSON completo in 25,970 s, rifiutato dal validatore perché richiedeva troppi punti; prompt 799, cache 775, generati 93 (conteggi nativi) | 0 |
| Stessa sessione, correzione | Timeout in 120,042 s; utilizzo ignoto; arresto `provider_error` | 0 |

Quattro generazioni reali complessive. Il JSON minimo dimostra collegamento e formato semplice; il secondo tentativo dimostra che un JSON completo può violare un vincolo applicativo. Nessuna richiesta valida o conclusione scientifica. L'output grezzo invalido non è conservato né inoltrato al modello; nessuna approvazione umana inventata.

I log tecnici mostrano circa 50 s per elaborare 512 token del primo prompt e circa 0,5 GB RAM fisica libera. Caricamento, memoria e generazione restano fattori da distinguere. Il secondo tentativo cambia anche output massimo (512 token) e usa un modello già caricato/cache: non è un confronto controllato né una diagnosi conclusiva della latenza. Nessuna ulteriore generazione Ollama dopo la scelta Gemini.

Correzioni locali: vincolo pubblico esplicito `1 + duration / observation_interval`, con rapporto massimo derivato da `max_points`; timeout Ollama configurabile fino a 600 s, default 30 s invariato e tetto remoto ancora 120 s. Quest'ultimo cambiamento è testato offline, **non** verificato con una nuova generazione Qwen.

## Verifiche e criteri pendenti

I test del launcher usano una chiave sentinella e un client **chiaramente simulato**. Esercitano Forge reale offline e ciclo completo con domanda, decisione umana simulata, osservazione, ipotesi, previsione, verifica e conclusione; annullamento, input non interattivo, ripristino dell'ambiente su successo/errore e blocco del fallback che mostrerebbe la chiave. Le regressioni del pilot locale verificano timeout e confine pubblico/privato. I test preesistenti mantengono modifica, rifiuto, invalidi, rete e assenza di doppie esecuzioni.

La diagnostica verifica accesso al modello e schema minimo tramite `generate_content`. Restano da verificare realmente con Gemini: disponibilità della quota per l'indagine, accettazione del contratto completo, richiesta semanticamente valida, decisione umana, osservazione, aggiornamento di ipotesi, previsione preregistrata, verifica e conclusione o arresto motivato. Un singolo pilot non valida il benchmark v0.3, confronti tra modelli o Arena BYOA.

Riferimenti Ollama: [chat](https://docs.ollama.com/api/chat), [output strutturati](https://docs.ollama.com/capabilities/structured-outputs). I validatori applicativi restano autoritativi anche quando il JSON è conforme allo schema.
