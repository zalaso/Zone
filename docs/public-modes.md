# Modalità del laboratorio locale — fase 6

> Historical/advanced engineering reference. For the version 1.0 supported installation start with [Getting started](getting-started.md), [AI connections](ai-connections.md) and [self-hosting](self-hosting.md). Earlier phase statuses describe that earlier revision, not missing release features or a current hosted service.


Le cinque modalità usano lo stesso simulatore, protocollo, registro SQLite, freeze della submission e valutatore scientifico. Non modificano suite, trial o aggregazione del benchmark v0.3. Il server predefinito usa **una baseline numerica offline, non un LLM**: propone lanci con una policy pubblica e stima accelerazioni dalle sole posizioni osservate. Non legge legge, seed, schedule privata o verità dei probe. È una verifica del software, non una dimostrazione di scoperta scientifica.

| Percorso | Comportamento |
| --- | --- |
| Scientist | La persona formula richieste, ipotesi, previsioni e conclusione; l'operatore autorizza ed esegue. Mantiene il ciclo manuale della fase 5. |
| Watch an Agent | `Avanza agente` chiede un solo messaggio al client del server. La persona approva, modifica o rifiuta; sceglie esplorazione/verifica ed esegue. Il passo agente non può lanciare esperimenti. |
| Human vs AI | Due sessioni sullo stesso mondo: indagine umana prima, risposta congelata, poi indagine agente con storia separata. Punteggi dopo entrambe le submission; nessun punteggio combinato o vincitore sintetico. |
| World of the Day | Un mondo per giorno UTC e database locale, con livello ciclico 1–5 e budget 3. Il seed è casuale privato, non ricavato dalla data. La scelta resta stabile al riavvio con lo stesso SQLite. Si indaga come Scientist. |
| Build a Universe | Generatore Forge 1 per livelli 1–5, oppure AST scritto dall'autore. Registrazione soltanto dopo validazione. Il manifesto restituito esclude AST, seed e configurazione. |

## Prima prova senza API

In PowerShell dalla radice, con extra backend e dipendenze frontend già installati:

```powershell
.\.venv\Scripts\python.exe -m hidden_lab forge generate --level 1 --seed 123456 --budget 3 --private benchmark_data/modes-demo/world.json --manifest benchmark_data/modes-demo/manifest.json
$env:ZONE_OPERATOR_TOKEN = [Convert]::ToHexString([Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
Set-Clipboard $env:ZONE_OPERATOR_TOKEN
.\.venv\Scripts\python.exe -m hidden_lab serve --db benchmark_data/modes-demo/zone.sqlite3 --world benchmark_data/modes-demo/world.json --port 8765
```

In un secondo terminale:

```powershell
cd frontend
pnpm dev
```

Apri `http://127.0.0.1:5173/`, scegli **Watch an Agent**, incolla il token operatore e crea la sessione. Premi `Avanza agente` per l'ipotesi iniziale e ancora per una proposta. Leggi lo scopo nel replay, registra una decisione, scegli la modalità e premi `Esegui esperimento`. L'agente non interpreta il silenzio come autorizzazione. Dopo la misura, un altro passo aggiorna l'ipotesi. Alla conclusione il server pubblica sei stati probe; un ultimo passo congela le previsioni numeriche e produce il risultato. Il reveal richiede una conferma separata.

Se scegli verifica, l'agente riceve **i parametri modificati approvati e i relativi tempi** prima della previsione. La baseline usa un'approssimazione a accelerazione iniziale costante per queste posizioni, anche quando il fit dell'accelerazione dipende dallo stato: può sbagliare. Le previsioni sono numeri validati, non formule o codice eseguibile.

Per riprendere, apri l'ID sessione o l'ID confronto. Scientist richiede il token agente originale oltre a quello operatore; nelle sessioni gestite non viene rilasciato un token agente al browser. I token restano nella sola memoria della pagina. Gli agenti gestiti riprendono dal registro e dai contatori persistiti, con la stessa configurazione del server; se provider, modello o impostazioni cambiano, il server rifiuta nuovi passi su quelle sessioni.

## Condizioni di Human vs AI

Mondo e hash, apparato, probe, budget degli esperimenti, numero massimo di misure per lancio e messaggi scientifici coincidono. Per default: budget del mondo, massimo 9 punti, massimo 15 messaggi per partecipante, inclusa la submission. Il report conserva osservazioni, messaggi, chiamate e risposte invalide, mostrando le metriche scientifiche separate. Il confronto è rifiutato se record, apparato, hash dei probe o limiti non coincidono.

In questa modalità sono ammesse solo approvazioni e lanci esplorativi; modifiche, rifiuti e dialogo teorico sono rifiutati per **entrambi** i partecipanti. La motivazione dell'approvazione è normalizzata dal server a una nota operativa, così non trasmette suggerimenti all'agente. Richieste e ipotesi restano a scelta del partecipante. Si può sempre arrestare un'indagine, senza inventare una submission.

La risposta umana deve essere congelata prima di attivare l'agente. L'agente non riceve storia umana, submission umana, punteggi, README, codice, copioni o configurazioni private. Nessuno dei due riceve risultati di scoring prima che entrambi abbiano consegnato. Il reveal è bloccato finché entrambe le sessioni hanno un punteggio o sono arrestate. Anche una submission già congelata in attesa del secondo partecipante può essere arrestata: rimane nel registro, ma non riapre l'indagine né viene valutata. I mondi AST scritti dall'autore sono esclusi dal confronto, perché l'autore conosce la risposta.

Sono condizioni applicative locali, non una gara protetta contro chi controlla la macchina. Tempo di ragionamento umano, esperienza, consultazioni esterne e contaminazione non sono equiparati o controllati. Riutilizzare un mondo già rivelato invalida una lettura cieca del confronto; il server locale non impedisce reveal di altre sessioni sullo stesso mondo. Non usare questi risultati come prova causale di superiorità umano/LLM. L'integrità competitiva e le identità pubbliche appartengono alle fasi 7–8. In Scientist e Watch an Agent, suggerimenti teorici dell'operatore possono influenzare i risultati e vanno riconosciuti nella conclusione.

## Costruttore e validazione

`Build a Universe` consente un generatore con livello 1–5 e budget 1–4, oppure il JSON di una legge AST con gli operatori già ammessi da [World Forge](world-forge.md). Il JSON è riservato all'autore: non viene allegato ai payload degli agenti. Schema distinto `builder_version=1`, hash canonico e seed registrato privatamente; Forge 1 e benchmark v0.3 mantengono i propri formati.

Il costruttore riusa parser AST, limiti di profondità/nodi, simulatore e dominio. Confronta la schedule con un'integrazione a passo dimezzato (differenza massima 0,002 m), controlla traiettorie entro 80 m per asse e accelerazioni finite su sei probe e 36 stati di controllo, rifiutando leggi con segnale inferiore a 0,25 m/s². Sono controlli numerici **euristici**, non una prova di stabilità o identificabilità in tutti gli stati. Il generatore mantiene la pipeline Forge esistente. Nessun `eval`, codice arbitrario, famiglia fisica nuova o modello scaricato.

## Budget, errori e audit

Ogni passo richiede token operatore e versione degli eventi. Una chiamata viene prenotata persistentemente prima di contattare il client. Budget chiamate (default 20), turni (15), correzioni per passo (2), timeout (30 s), output (2500 token) e punti (9) sono separati dal budget esperimenti. Sono disponibili `--agent-max-calls`, `--agent-max-turns`, `--agent-max-corrections` e `--agent-timeout`.

Se i budget si esauriscono dopo la conclusione o una submission rimane pendente, l'operatore può arrestare la sessione. In Human vs AI può passare all'altro partecipante per arrestare anche quello; il reveal resta bloccato fino alla chiusura di entrambi. Le risposte invalide consumano chiamate e possono ricevere al massimo il numero configurato di correzioni, senza concatenare nel prompt il corpo invalido. Gli errori di rete non vengono ritentati automaticamente. Un timeout non registra la risposta tardiva; finché il worker è attivo un secondo passo sulla stessa sessione è bloccato. Due clic concorrenti nello stesso processo non avviano due passi. Una scrittura concorrente rende obsoleta la risposta, che non viene applicata. Questi meccanismi non implementano ancora coordinamento di chiamate fra più processi server.

L'audit privato `GET /v1/sessions/{id}/agent/audit`, con `X-Zone-Token` operatore, conserva provider, modello richiesto/restituito, SDK, impostazioni, fingerprint del contratto, utilizzo nativo restituito e stato (`accepted`, `invalid`, `error`, `stale`, `interrupted`, o prenotazione `started` dopo un crash). Nessuna chiave, header SDK, prompt integrale o corpo invalido viene salvato. I conteggi mancanti restano indisponibili; il costo monetario di un provider reale richiede prezzi/fatturazione e non viene inventato. Non si promette riproducibilità esatta delle risposte LLM. Un errore dell'agente non ripete un esperimento: solo `/run` può invocare il simulatore e il registro impedisce un secondo lancio già iniziato.

## Piano ChatGPT personale nel web

`serve --agent-provider chatgpt` riusa il provider CLI. Con account richiede `--agent-owner`, riserva il piano a quell’identità e alle sue sessioni, e mantiene offline gli altri invitati. Modello e consenso sono espliciti; nessun fallback API. [Preparazione VM, trasferimento autorizzato e limiti](web-llm-pilot.md). Nessuna inferenza web reale è stata eseguita nello sviluppo.

## Pilot API reale successivo — non eseguito nello sviluppo

Riusa gli adapter esistenti, senza modello predefinito costoso. Prepara tu `OPENAI_API_KEY` nell'ambiente del terminale e scegli un ID modello in `OPENAI_MODEL`. Per un solo mondo, in un database nuovo:

```powershell
.\.venv\Scripts\python.exe -m pip install -e '.[backend,openai]'
# OPENAI_API_KEY e OPENAI_MODEL devono essere già impostati; non scriverli in file del repository.
if (-not $env:OPENAI_API_KEY -or -not $env:OPENAI_MODEL) { throw 'Imposta credenziale e modello nell’ambiente.' }
$env:ZONE_OPERATOR_TOKEN = [Convert]::ToHexString([Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
Set-Clipboard $env:ZONE_OPERATOR_TOKEN
.\.venv\Scripts\python.exe -m hidden_lab serve --db benchmark_data/real-pilot/zone.sqlite3 --world benchmark_data/modes-demo/world.json --agent-provider openai --agent-model $env:OPENAI_MODEL --allow-real-agent --agent-max-calls 12 --agent-max-turns 10 --agent-max-corrections 1 --agent-timeout 30
```

Avvia Vite nel secondo terminale, scegli Watch an Agent e verifica che la UI mostri **Provider reale**. La creazione del client non chiama il modello; ogni `Avanza agente` autorizza il passo e le eventuali correzioni entro il budget. Installazione e chiamate del pilot non sono state effettuate per questa fase. Scegli un mondo nuovo se il precedente è stato rivelato: la prova software con il mondo demo non è un'indagine cieca.

## Route aggiunte

| Route | Accesso |
| --- | --- |
| `GET /v1/modes` | Pubblico: modalità e client configurato, senza credenziali. |
| `GET /v1/worlds/daily` | Pubblico: data UTC e solo manifesto. |
| `POST /v1/worlds/generate` | Operatore: `level`, `budget`, `seed` facoltativo privato. |
| `POST /v1/worlds/build` | Operatore: `law`, `budget`, `seed` facoltativo privato. |
| `POST /v1/matches` | Operatore: `world_id`, due sessioni create atomicamente; token umano una volta. |
| `GET /v1/matches/{id}` | Pubblico: condizioni, stati, risorse e risultati dopo entrambi i freeze. |
| `POST /v1/sessions/{id}/agent/step` | Operatore: `expected_version`; un messaggio, nessun lancio. |
| `GET /v1/sessions/{id}/agent/audit` | Operatore: metadati delle chiamate senza segreti. |

`POST /v1/sessions` accetta inoltre `mode`: `scientist` (default compatibile), `watch_agent`, `world_of_day`. Per quest'ultimo il backend verifica il mondo UTC corrente. I database della fase 4–5 vengono estesi con tabelle additive, senza riscrivere gli eventi esistenti.
