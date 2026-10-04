# Laboratorio di fisica nascosta

Una base funzionante per studiare la progettazione degli esperimenti: un partecipante propone lanci di una particella, l'operatore approva o modifica le richieste, il simulatore restituisce posizioni e una previsione preregistrata viene confrontata con misure successive.

**Zone locale: fasi 0–7 della roadmap, con benchmark sulla piattaforma multi-provider.** Il comando `investigate` continua a collegare OpenAI, Anthropic, Gemini, Ollama locale oppure un client chiaramente simulato. Il modello conduce l'indagine con messaggi strutturati; la persona decide e autorizza ogni lancio con un menu testuale. Le modalità originali `shell` e `demo` restano manuali e compatibili.

**Zone Benchmark v0.3** usa suite private versionate e quattro condizioni (`prior_only`, `passive_fixed`, `passive_sequential`, `active`) per valutare previsioni di accelerazione su stati nascosti. `passive_fixed` consegna le misure in blocco come diagnosi; `passive_sequential` usa gli stessi lanci ma una misura e una chiamata di ragionamento per volta, per il confronto principale con `active`. Due baseline offline, una policy casuale riproducibile e uno stimatore affine senza LLM, rendono verificabile il flusso. **World Forge v1** genera e valida mondi AST dei livelli 1–5, utilizzabili nelle sessioni locali, mantenendo le suite benchmark v0.3 nel formato storico. La **fase 3** aggiunge una proposta di legge AST facoltativa e incertezza numerica: accuratezza dei probe, equivalenza funzionale empirica, complessità, dipendenze e calibrazione rimangono metriche separate. La **fase 4** aggiunge un backend FastAPI locale con SQLite, replay e reveal esplicito. La **fase 5** aggiunge un laboratorio web React/TypeScript/Vite sul backend locale. La **fase 6** aggiunge Scientist, Human vs AI con sessioni separate e freeze umano iniziale, Watch an Agent con baseline numerica offline o provider esplicito, World of the Day persistito e Build a Universe validato. La **fase 7** aggiunge Zone Arena BYOA v1: challenge locali, token revocabili con scadenza, quote persistenti, idempotenza, audit e leaderboard per dimensione, con decisioni ed esecuzione riservate all’operatore. Vedi [Zone Arena](docs/arena.md), [stato e lavoro restante](docs/status.md), [modalità locali](docs/public-modes.md), [guida benchmark](docs/benchmark.md), [World Forge](docs/world-forge.md), [identificazione](docs/identification.md), [backend](docs/backend.md), [laboratorio web](docs/frontend.md) e [roadmap](ROADMAP.md).

Per il prossimo passo leggi **[Prima sessione con un agente LLM](docs/first-llm-session.md)**: installazione dell'extra desiderato, credenziale da ambiente per i provider remoti, scelta del modello, conferme, limiti e verifica offline. Nessuna chiamata reale a un modello è stata effettuata durante lo sviluppo.

## Installazione e avvio rapido

Richiede Python 3.11 o successivo. La dipendenza base è Matplotlib per i grafici; gli extra `.[openai]`, `.[anthropic]`, `.[gemini]`, `.[ollama]` e `.[all-llm]` aggiungono soltanto i client necessari. `.[llm]` resta alias di `.[openai]`. L'extra `.[backend]` installa FastAPI, Uvicorn e HTTPX per il server locale e i test in processo. Simulatore e protocollo restano indipendenti dagli SDK e dal web. Per eseguire tutta la suite dei test dei provider installa `.[all-llm]`.

Da PowerShell, nella cartella del progetto:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m hidden_lab demo --config examples/operator-world.json --script examples/manual-session.txt --session sessions/demo
```

Su Linux/macOS gli stessi comandi usano `.venv/bin/python` al posto di `.\.venv\Scripts\python.exe`. È disponibile anche il comando installato `physics-lab`. Non è necessario attivare l'ambiente virtuale.

La cartella della sessione **deve essere nuova**. Per ripetere la demo usa ad esempio `sessions/demo-2`: il programma rifiuta di sovrascrivere un registro esistente.

Il risultato della demo comprende:

- due esperimenti eseguiti, con cinque misure ciascuno;
- un'ipotesi e una previsione registrata prima del secondo lancio;
- una modifica approvata e un successivo rifiuto che non consuma budget;
- errore predittivo prossimo alla precisione numerica nel mondo di esempio;
- `sessions/demo/public/trajectory_check-1.png`, grafico delle posizioni osservate e previste;
- registri pubblici e valutazioni private separati.

Il copione è pensato per la configurazione di esempio senza rumore. Cambiando mondo, le sue previsioni rimangono quelle scritte manualmente: il punteggio può quindi peggiorare. Non viene adattato leggendo la legge vera.

## Terminale manuale

```powershell
.\.venv\Scripts\python.exe -m hidden_lab shell --config examples/operator-world.json --session sessions/indagine-1
```

Al prompt `lab>`:

```text
agent @examples/request.json
operator {"type":"operator_decision","request_id":"probe-1","action":"approve","reason":"Procediamo con la misura esplorativa."}
run probe-1
plot probe-1
status
quit
```

`agent` e `operator` accettano un oggetto JSON su una riga oppure `@percorso.json`. I percorsi relativi sono risolti rispetto alla cartella da cui avvii il programma. `help` mostra i comandi. Il terminale è dell'operatore: entrambi i prefissi sono disponibili alla persona, non costituiscono autenticazione.

Per ipotesi, modifica, previsione e rifiuto puoi seguire [il copione completo](examples/manual-session.txt). È possibile generare nuovamente un grafico anche dopo la chiusura:

```powershell
.\.venv\Scripts\python.exe -m hidden_lab plot --public sessions/demo/public --request check-1
```

Questo comando richiede esclusivamente il registro pubblico. Il grafico riporta la traiettoria nel piano e la quota nel tempo; le linee congiungono i campioni e non rappresentano misure aggiuntive.

## Apparato e leggi — documentazione dell'operatore

Questo README e il codice del simulatore sono materiale di sviluppo e dell'operatore. **Non vanno forniti all'agente valutato.** L'adattatore API consegna al modello la descrizione `apparatus` nel registro pubblico, che non contiene la famiglia attiva o i coefficienti.

Lo stato è `(x, y, vx, vy)`. `x` cresce verso destra, `y` verso l'alto; il tempo parte da zero a ogni lancio. Posizioni in metri, tempo in secondi, velocità in m/s, accelerazioni in m/s². L'origine è fissa. Le coordinate negative sono ammesse: **non esiste un pavimento**, né ci sono urti, rimbalzi o attriti di contatto. La particella è puntiforme; la massa è assorbita nei coefficienti di accelerazione, non è un comando disponibile.

Tutti i mondi soddisfano `dx/dt = vx`, `dy/dt = vy`, `dvx/dt = ax`, `dvy/dt = ay`. Nei mondi storici il parametro `gravity = g` è non negativo e l'accelerazione gravitazionale è diretta verso il basso. Le quattro famiglie storiche sono:

| `family` | Accelerazione orizzontale | Accelerazione verticale | Significato di `coefficient` |
| --- | --- | --- | --- |
| `constant` | `ax = 0` | `ay = -g` | Deve essere zero |
| `height` | `ax = 0` | `ay = -g - k*y` | `k`, in s⁻² |
| `linear_drag` | `ax = -γ*vx` | `ay = -g - γ*vy` | `γ`, in s⁻¹ |
| `quadratic_drag` | `ax = -β*sqrt(vx²+vy²)*vx` | `ay = -g - β*sqrt(vx²+vy²)*vy` | `β`, in m⁻¹ |

Nella famiglia `height`, sotto `y = -g/k` l'accelerazione può puntare verso l'alto: è una scelta intenzionale di questo mondo, non la gravità terrestre. Nel caso quadratico si usa il **modulo dell'intero vettore velocità**, non il quadrato separato delle componenti. Le famiglie storiche non combinano dipendenza dalla quota e resistenza nello stesso mondo. World Forge aggiunge una famiglia privata `ast`, descritta nella [guida dedicata](docs/world-forge.md), con leggi validate e senza esecuzione di formule testuali.

Per le famiglie storiche i valori privati ammessi sono: `g` fra 0 e 30 m/s², `coefficient` fra 0 e 2 nella rispettiva unità, seed fisico intero fra 0 e 2³²−1, budget intero fra 1 e 100. Il valore zero rende alcune famiglie indistinguibili. Il generatore AST filtra candidati con due alternative costruite e una schedule informativa, senza promettere identificabilità generale.

L'operatore può scegliere un mondo storico modificando una copia di [operator-world.json](examples/operator-world.json), oppure generare un mondo AST con `forge generate` e usare il `config.json` privato esportato. I campi sono obbligatori e gli extra vengono rifiutati. La configurazione effettiva viene copiata nel registro privato, così modifiche successive al file sorgente non alterano la riproducibilità della sessione.

### Dominio valido e integrazione

| Quantità | Limite |
| --- | --- |
| Posizione iniziale, per asse | da −20 a +20 m |
| Velocità iniziale, per asse | da −20 a +20 m/s |
| Durata richiesta | da 0,1 a 5 s |
| Intervallo fra osservazioni | da 0,05 a 1 s |
| Posizione durante l'integrazione, per asse | da −100 a +100 m |
| Modulo della velocità durante l'integrazione | massimo 200 m/s |
| Passo massimo privato di integrazione | da 0,0001 a 0,01 s |

La durata deve essere un multiplo dell'intervallo di osservazione (tolleranza assoluta 10⁻⁹ s). La griglia contiene `t=0`, tutti i campioni intermedi e l'istante finale: massimo 101 punti. Posizione e velocità iniziali sono fissate esattamente dall'operatore.

L'integrazione usa Runge–Kutta del quarto ordine, RK4. Per ogni intervallo di osservazione `Δt` vengono eseguiti `ceil(Δt / integration_step)` sottopassi uguali. Il passo effettivo raggiunge esattamente gli istanti richiesti ed è indipendente dalla frequenza di osservazione. Il costo è limitato a circa 50.100 passi per lancio con i limiti ammessi.

Il programma controlla finitezza, posizione e velocità negli stati intermedi di RK4 e dopo ogni passo. Quando fallisce un controllo, interrompe il lancio: restituisce `TRAJECTORY_INVALID` e **nessuna misura parziale**. Non comunica il tempo interno del fallimento o dettagli della legge. Il controllo è numerico: non localizza esattamente l'attraversamento continuo di un confine e può essere conservativo sugli stati intermedi. Non è un integratore adattivo né una certificazione dell'errore numerico.

### Misure e rumore riproducibile

La configurazione fornita usa `noise_std = 0`: si osservano solo tempo e posizione, mai velocità o accelerazione. Il rumore non è necessario per completare il ciclo, ma è già disponibile come opzione privata semplice: con `noise_std > 0` si aggiunge rumore gaussiano indipendente a `x` e `y`, anche a `t=0`, con deviazione standard in metri fra 0 e 1. Il tempo resta esatto. Il rumore si applica alle misure, non alla dinamica; una misura rumorosa può superare il confine pur con uno stato fisico valido.

Ogni esecuzione usa un generatore locale `random.Random(seed + experiment_index)`, con indice che parte da 1 e comprende i lanci falliti. Nessuna dipendenza dal generatore casuale globale. Configurazione, ordine dei lanci, codice e versione di Python uguali riproducono le stesse misure; non promettiamo identità bit per bit fra piattaforme o versioni diverse. La versione Python e la versione del pacchetto sono salvate in `private/reproducibility.json`; conserva anche la stessa revisione del codice per riprodurre uno studio.

## Messaggi e ordine delle operazioni

Il contratto eseguibile è [protocol.py](hidden_lab/protocol.py); non richiede Pydantic o un servizio esterno. Il parser rifiuta chiavi duplicate, campi sconosciuti, valori non finiti, booleani al posto di numeri e messaggi JSON oltre 64.000 byte. Gli identificatori iniziano con una lettera e contengono al massimo 48 caratteri tra lettere ASCII, cifre, trattini e underscore. Testi non vuoti, massimo 2.000 caratteri; liste di incertezze ed evidenze massimo 100 elementi.

| Messaggio | Mittente | Campi oltre a `type` |
| --- | --- | --- |
| `experiment_request` | Agente manuale | `request_id`, `purpose`, `experiment` |
| `operator_decision` | Operatore | `request_id`, `action`, `reason`; `modified_experiment` solo per `modify` |
| `hypothesis` | Agente manuale | `hypothesis_id`, `statement`, `uncertainties`, `evidence` |
| `prediction` | Agente manuale | `prediction_id`, `hypothesis_id`, `request_id`, `points` |
| `operator_question` | Agente manuale o LLM | `question_id`, `question`, `purpose` |
| `operator_answer` | Operatore | `question_id`, `answer` |
| `execution_mode` | Operatore | `request_id`, `mode` (`exploration` o `verification`) |
| `conclusion` | Agente manuale o LLM | `final_hypothesis_id` (anche `null`), `summary`, `evidence`, `limits`, `alternatives` |
| `observation` | Apparato | `request_id`, `experiment_index`, `status`, `points`, `error`, `executed_count`, `remaining_budget` |

`experiment` contiene esattamente `initial_position: {x,y}`, `initial_velocity: {x,y}`, `duration`, `observation_interval`. Una modifica sostituisce **tutta** questa configurazione. `points` contiene oggetti `{t,x,y}`. `evidence` contiene ID di richieste già eseguite con successo; può essere vuota per un'ipotesi iniziale.

È ammessa una sola richiesta aperta alla volta. Una decisione è definitiva: `approve` conserva la richiesta, `modify` la sostituisce con parametri validati, `reject` la chiude. Il lancio si esegue soltanto con `run`, una volta sola. Un'ipotesi può essere registrata prima dell'esplorazione oppure dopo averne ricevuto le osservazioni. Per la verifica:

1. Registra l'ipotesi, con le evidenze disponibili e le incertezze.
2. Proponi un nuovo esperimento e attendi la decisione dell'operatore.
3. Registra una sola previsione per quella richiesta, usando **tutti** i tempi dell'esperimento approvato, in ordine.
4. Esegui il lancio: arrivano le osservazioni e quindi la metrica di verifica.

La previsione è vincolata alla configurazione approvata e non è sostituibile. Non è accettata dopo l'esecuzione. Per correggere o revisionare un'ipotesi occorre un nuovo ID: la storia precedente rimane nel registro. Le coordinate previste devono essere finite e comprese fra −10⁶ e +10⁶ m; possono superare il dominio dell'apparato per consentire ipotesi sbagliate.

Le risposte di osservazione sono validate anche prima della scrittura. Per `status="ok"`, i punti sono completi ed `error=null`; per `status="error"`, `points=[]` ed `error` contiene `code` e `message`. Completano il protocollo i messaggi automatici `apparatus`, `execution_started`, `verification` e `protocol_error`. Ogni evento pubblico è avvolto in `{seq, actor, message}`. Il campo `seq`, crescente da 1, è l'ordine canonico degli eventi.

Le formule delle ipotesi restano testo: non si usa `eval`, `exec` o esecuzione di codice ricevuto. Le previsioni quantitative sono esclusivamente punti numerici.

Il protocollo è ora alla versione 2. Richieste, ipotesi e previsioni sono gli stessi messaggi per persona e LLM. Il client API avvolge ogni messaggio in `{"message": ...}` per il formato strutturato del provider; il registro conserva il messaggio canonico. `investigate` rende obbligatoria una scelta esplicita della modalità dopo la decisione. La modalità di verifica blocca `run` fino alla registrazione della previsione. Le vecchie sessioni manuali possono continuare a usare `run` senza `execution_mode`.

Una domanda rimane in attesa fino alla risposta della persona; la conclusione richiede almeno un limite dichiarato, evidenze già disponibili e un'ipotesi registrata oppure `null`. Concludere chiude l'indagine e annulla l'eventuale lancio non eseguito. Un arresto per budget, rete o scelta umana genera invece `investigation_stopped`: non viene inventata una conclusione del modello.

## Registri, budget e valutazione

```text
session/
  public/
    events.jsonl                  # Apparato, messaggi, esecuzioni, misure, punteggi
    trajectory_check-1.png        # Generato su richiesta
  private/
    reproducibility.json         # Legge, coefficienti, seed, rumore, integrazione, versioni
    evaluations.jsonl            # Verità privata accanto a ipotesi e metriche
    agent_settings.jsonl         # Solo investigate: provider, modello, impostazioni e versione del client
    model_calls.jsonl            # Solo investigate: tentativi, esiti e utilizzo restituito
```

Ogni JSONL è leggibile una riga alla volta. Il budget conta le **esecuzioni avviate**, comprese quelle con traiettoria invalida. Richieste, modifiche, rifiuti, grafici ed errori di validazione non consumano esperimenti. `execution_started` viene scritto e sincronizzato su disco prima di avviare la simulazione. Anche gli altri eventi vengono sincronizzati; un arresto improvviso può comunque lasciare un'esecuzione senza osservazioni o un registro privato incompleto. I due file non sono una transazione atomica.

Questa base usa un solo processo per sessione, non ha ripresa interattiva o recupero automatico dopo un crash. Le sessioni chiuse restano consultabili e rappresentabili in grafico. Non modificare manualmente i registri se vuoi conservarne il valore sperimentale: non sono firmati, autenticati o protetti da manomissioni dell'operatore.

La verifica confronta una previsione con le misure dell'esperimento successivo a cui si riferisce. Per ogni punto:

```text
error_i = sqrt((x_pred_i - x_obs_i)^2 + (y_pred_i - y_obs_i)^2)
position_rmse = sqrt(mean(error_i^2))
max_position_error = max(error_i)
```

Entrambe le metriche sono in metri; includono `t=0`. Non c'è una soglia arbitraria di promozione. Con rumore si valuta rispetto alle misure rumorose. Se il lancio fallisce, `verification.status="unavailable"` e `metrics=null`: non si assegna un errore zero.

Il punteggio predittivo delle traiettorie è pubblico perché deriva solo da previsioni e misure pubbliche. La valutazione privata della singola sessione affianca a queste metriche la legge vera e l'ipotesi, così l'operatore può esaminarle; **non decide se le formule sono equivalenti**. `law_identification="not_assessed"` si riferisce a questo confronto di traiettorie. La successiva valutazione di fase 3 verifica invece un AST candidato su una griglia privata e riporta soltanto equivalenza empirica, senza prova simbolica generale.

## Confine delle informazioni

| Informazione | Destinatari |
| --- | --- |
| Legge e configurazione vera | Operatore, simulatore, valutazione privata |
| Coordinate, unità, comandi, limiti e budget | Agente e operatore |
| Misure ed errori generici | Agente e operatore |
| Richieste, ipotesi e previsioni | Registro pubblico |
| Configurazione di riproducibilità e confronto con la verità | Solo registro privato |

Il programma costruisce i messaggi pubblici mediante campi espliciti: non serializza la configurazione, il nome della famiglia, coefficienti, seed o tracce di eccezioni del simulatore. Non pubblica nomi di file privati o nomi rivelatori delle configurazioni. Il grafico legge solo dati pubblici. Le differenze nelle traiettorie e il fatto che un lancio sia invalido sono invece evidenze sperimentali intenzionali.

**È separazione applicativa, non una sandbox.** Codex sviluppa e verifica l'intero progetto, con un ruolo diverso dall'agente sperimentale. Il modello remoto riceve solo il payload costruito da `agent_contract.py`, senza strumenti, file o riferimento a `Session`. L'orchestratore Python locale è fidato e conserva accesso al simulatore. Lo stdout completo resta dell'operatore: può contenere percorsi o errori locali e non viene allegato al modello. Dare in futuro a un agente locale accesso alla cartella, al simulatore, a questo README o ai copioni comprometterebbe la valutazione e richiederebbe un isolamento reale aggiuntivo.

Il software non può impedire che una persona copi volontariamente segreti in `reason`, o che un'ipotesi contenga il valore corretto di un coefficiente inferito. Le garanzie testate riguardano la mancata divulgazione automatica di metadati privati, non la censura dei testi liberi o la prevenzione dell'inferenza scientifica.

## Architettura e test

| File | Responsabilità |
| --- | --- |
| `hidden_lab/protocol.py` | Messaggi pubblici, controlli di forma, limiti e griglia |
| `hidden_lab/simulator.py` | Configurazione privata, dinamica, RK4 e rumore |
| `hidden_lab/session.py` | Ordine delle operazioni, ruoli applicativi, budget e registri |
| `hidden_lab/evaluation.py` | Errore fra posizioni; non conosce la legge vera |
| `hidden_lab/plotting.py` | Grafico da registro pubblico |
| `hidden_lab/cli.py` | Terminale e lettura del copione manuale |
| `hidden_lab/agent_contract.py` | Richiesta canonica, istruzioni pubbliche, schema e lista positiva dei campi inviabili |
| `hidden_lab/provider_base.py` | Contratto minimo dei client, impostazioni e metadati di audit |
| `hidden_lab/llm.py` | Adapter OpenAI Responses API |
| `hidden_lab/anthropic_client.py` | Adapter Anthropic Messages API |
| `hidden_lab/gemini_client.py` | Adapter Google Gen AI |
| `hidden_lab/ollama_client.py` | Adapter HTTP Ollama locale, senza download automatici |
| `hidden_lab/investigation.py` | Ciclo LLM/operatore, budget di chiamate, correzioni e audit |
| `hidden_lab/terminal.py` | Menu e misure leggibili, conferme esplicite |
| `hidden_lab/fake_client.py` | Copione simulato offline, separato dal client reale |
| `hidden_lab/benchmark_suite.py` | Suite privata, validazione della schedule, hash e manifest pubblico |
| `hidden_lab/benchmark_contract.py` | Payload pubblico e schema delle due fasi del benchmark |
| `hidden_lab/benchmark_trial.py` | Trial singolo, operatore neutrale, freeze e audit |
| `hidden_lab/benchmark_metrics.py` | Errore di accelerazione ricalcolabile dai file salvati |
| `hidden_lab/benchmark_report.py` | Aggregazione e report descrittivo senza simulazioni |
| `hidden_lab/benchmark_cli.py` | Comandi `benchmark prepare/check/trial/aggregate/report` |
| `hidden_lab/benchmark_baselines.py` | Policy casuale e stimatore numerico da sola storia pubblica |
| `hidden_lab/world_ast.py` | Parser e interprete sicuro delle leggi AST |
| `hidden_lab/world_forge.py` | Generatore versionato, filtro dei mondi e difficoltà euristica |
| `hidden_lab/world_forge_cli.py` | Comandi `forge generate/check/levels` offline |
| `hidden_lab/identification.py` | Submission scientifica comune, griglia privata e metriche separate |
| `hidden_lab/identify_cli.py` | Challenge e valutazione locale dopo la conclusione |
| `hidden_lab/backend_state.py` | Stato ricostruito dagli eventi e regole HTTP dell'indagine |
| `hidden_lab/backend_store.py` | Contratto di persistenza e repository SQLite append-only |
| `hidden_lab/backend.py` | Route FastAPI, proiezione pubblica, token, limiti e reveal |
| `hidden_lab/server_cli.py` | Avvio del server su loopback |
| `frontend/` | Interfaccia React/TypeScript/Vite per sessioni, challenge, risultato e replay |
| `examples/` | Configurazione privata, richiesta pubblica e copione dimostrativo |
| `tests/test_lab.py` | Dinamica, protocollo, separazione, riproducibilità e CLI completa |
| `tests/test_agent.py` | Ciclo simulato, payload, conferme, limiti e SDK con HTTP simulato |
| `tests/test_providers.py` | Traduzione del contratto comune, trasporti fittizi, errori e confine informativo |
| `tests/test_benchmark.py` | Suite, quattro condizioni, probe, metriche, compatibilità v0.1 e CLI offline |
| `tests/test_world_ast.py` | Validazione, limiti e valutazione deterministica dell'AST |
| `tests/test_world_forge.py` | Generazione, simulazione AST, privacy e CLI offline |
| `tests/test_identification.py` | Equivalenza funzionale, calibrazione, freeze, audit e integrazione benchmark |
| `tests/test_backend.py` | Ciclo HTTP offline, replay, ruoli, crash, rate e confine privato |

Il backend locale opzionale usa SQLite e FastAPI senza framework di agenti. Per studiare il ciclo CLI parti dal protocollo, poi segui `Session.submit()` e `Session.run()`; per l'API parti da `backend_state.py` e `backend_store.py`. Il simulatore può essere letto separatamente.

I test confrontano tutte e quattro le famiglie con soluzioni analitiche note (nel caso quadratico, moto unidimensionale senza gravità), verificano la convergenza del caso quadratico con gravità, griglie di campionamento e integrazione diverse, rumore riproducibile, limiti, budget, ruoli, riferimenti, immutabilità delle previsioni e rifiuto di metadati inattesi. Un test esegue la demo tramite un vero processo CLI e rigenera il grafico da una cartella contenente solo il registro pubblico.

## Stato del collegamento LLM e prossimi passi

I quattro adapter, il ciclo guidato e i controlli sono implementati. Le prove di sviluppo usano risposte simulate, inclusi SDK con trasporti fittizi: verificano il software, non la qualità scientifica dei modelli. La prima chiamata reale, la compatibilità del modello scelto e l'indagine effettiva rimangono da verificare con autorizzazione dell'operatore. [Istruzioni complete per ciascun provider](docs/first-llm-session.md).

Le risposte LLM non sono esattamente riproducibili: modello, impostazioni e utilizzo sono registrati per tracciabilità, non come promessa di determinismo. I suggerimenti teorici dell'operatore possono influenzare il risultato e vanno considerati nella valutazione.

Ripresa delle sessioni CLI, integrazione adattiva e analisi statistica del rumore rimangono possibili estensioni. Il frontend locale è implementato; non sono inclusi un verificatore generale di equivalenza delle equazioni o confronti multi-modello validati. I mondi AST sono integrati nel simulatore e nelle sessioni locali; non sono ancora ammessi nelle suite benchmark v0.3. I trial del benchmark e la submission di legge sono stati verificati soltanto con fixture e baseline offline: nessun trial con un LLM reale è stato validato durante lo sviluppo.
