# Workspace pubblico · versione da provare

> Historical/advanced engineering reference. For the version 1.0 supported installation start with [Getting started](getting-started.md), [AI connections](ai-connections.md) and [self-hosting](self-hosting.md). Earlier phase statuses describe that earlier revision, not missing release features or a current hosted service.


Questa versione è preparata **in locale**. Non sostituisce la beta sul VPS e non apre le registrazioni del sito esistente. Prima vengono le prove dell’autore con i propri modelli, poi una distribuzione controllata, infine l’apertura generale.

## Cosa offre

Un account con nome utente e password, cookie HttpOnly, protezione CSRF, codice di recupero monouso e quote personali. Non occorrono chiavi AI per registrarsi. Il recupero cambia password, revoca i cookie e disconnette tutte le AI precedenti; il codice vecchio non è riutilizzabile. Non è previsto recupero via email: conserva il codice in un password manager. Gli account su invito precedenti continuano a usare la chiave di accesso.

Le connessioni supportate sono:

| Collegamento | Dove resta la credenziale | Avvio |
| --- | --- | --- |
| OpenAI API, Anthropic API, Gemini API | Archivio cifrato sul server, oppure solo sul PC con connettore | Connessioni AI → provider → ID modello → salva |
| Piano ChatGPT | Archivio OAuth locale già usato dal client Zone | Connessioni AI → ChatGPT → prepara → connettore con `--login` |
| Ollama | Modello già installato sul PC; nessuna porta esposta al sito | Connessioni AI → Ollama → connettore |

Nessuna inferenza parte da registrazione, salvataggio, selezione, polling senza lavori o avvio di una sessione. **Avanza agente** autorizza una chiamata, con al massimo una correzione esplicitamente compresa nei limiti delle sessioni Watch/Human vs AI. Arena personale non riprova risposte invalide. Una chiamata API può consumare credito personale: Zone non imposta tetti monetari presso il provider.

La connessione è fissata per ogni nuova sessione; cambiarla vale per le successive. Revocarla ferma anche le vecchie sessioni associate, senza passare automaticamente a un’altra AI. Le sessioni storiche offline restano offline.

Scientist, Watch an Agent, Human vs AI, World of the Day, Build a Universe e Arena sono raggiungibili dall’area iniziale. Il benchmark a quattro condizioni resta uno strumento CLI per la ricerca; non è trasformato in un lancio web automatico. L’AST resta un linguaggio validato, mai codice eseguibile.

Arena personale riusa challenge, macchina a stati, ricevute idempotenti, scoring ed embargo esistenti. Il gestore crea e chiude le challenge dalla console staff. Ogni utente registra il proprio agente e opera soltanto sui propri trial. Le classifiche delle challenge chiuse sono consultabili per dimensione; nessun punteggio complessivo. Il modello dichiarato non è un’attestazione del modello realmente eseguito.

## Precisazione su Sign in with ChatGPT

Il connettore usa il percorso locale/open source di Zone, con consenso nel browser del computer dell’utente. Il server riceve soltanto risposte a lavori contenenti istruzioni, contratto e storia pubblici; non riceve access/refresh token ChatGPT.

Un pulsante OAuth direttamente sul sito, senza connettore, non è abilitato per tutti. La documentazione OpenAI distingue l’identità sul sito dall’uso del piano per inferenza e richiede un percorso di adesione per applicazioni ospitate. Non si riutilizza il client OAuth locale come se autorizzasse un servizio hosted multiutente. Riferimenti: [token sharing per app open source e locali](https://developers.openai.com/siwc/token-sharing-open-source), [Sign in with ChatGPT per siti](https://developers.openai.com/siwc/website).

## Prima prova, senza AI reale

Dal PowerShell nella cartella `C:\path\to\Zone`, con le dipendenze già installate:

```powershell
Set-Location C:\path\to\Zone
Push-Location frontend
pnpm run build
Pop-Location
.\.venv\Scripts\python.exe -m tools.preview_workspace --out benchmark_data\workspace-preview --port 8767
```

Apri `http://127.0.0.1:8767`. Crea un account, conserva il recupero e prova le sei modalità. La preview prepara un mondo e una challenge offline; non legge credenziali provider e non abilita l’archivio API sul server. Usa una password di prova diversa da quella degli altri servizi. Il processo resta nel terminale; `Ctrl+C` lo arresta, senza eliminare le sessioni. Il bootstrap tecnico della preview viene disabilitato dopo la preparazione della challenge e non viene consegnato come account amministratore.

Per ripetere lo smoke con Edge già installato, in un secondo terminale:

```powershell
Set-Location C:\path\to\Zone\frontend
node scripts/smoke-workspace.mjs
```

Questo test crea un account sintetico, prepara un connettore senza avviarlo, torna alla baseline, conduce Arena fino allo scoring con due lanci autorizzati, riapre la sessione ed esce. Le schermate sono in `benchmark_data\workspace-browser`; non vengono fotografati password, recupero o chiavi visibili.

## Le tue prove reali con ChatGPT e Ollama

La preview può usare un connettore personale. Prima prepara la connessione sul sito e scegli un ID modello disponibile nel tuo account o già installato in Ollama. Zone non scarica modelli e rifiuta il suffisso Ollama `:cloud`. Installa eventualmente l’extra appropriato; questi comandi installano software, non eseguono inferenze:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[workspace,chatgpt,ollama]"
```

In un secondo terminale, dalla cartella del progetto, sostituisci il segnaposto con lo stesso ID inserito sul sito:

```powershell
.\.venv\Scripts\python.exe -m hidden_lab connector --origin http://127.0.0.1:8767 --local-http --provider chatgpt --model IL_TUO_MODELLO --login --allow-inference --max-jobs 8
```

Per Ollama, già avviato sul computer:

```powershell
.\.venv\Scripts\python.exe -m hidden_lab connector --origin http://127.0.0.1:8767 --local-http --provider ollama --model IL_TUO_MODELLO --allow-inference --max-jobs 8
```

La chiave `zc_…` mostrata una sola volta sul sito viene chiesta con input nascosto; non passarla negli argomenti o in chat. Il connettore la mantiene in memoria, vale 30 giorni e può essere revocata dal sito. Il login ChatGPT conserva il proprio archivio OAuth locale con le protezioni già previste da Zone. Controlla quota e crediti extra del piano prima del primo clic. HTTP è ammesso soltanto su `127.0.0.1`, con consenso esplicito `--local-http`; per un sito remoto occorre HTTPS.

Il connettore fa solo richieste in uscita, non riceve un Session, non legge il progetto per comporre i prompt e non esegue esperimenti. Ogni lavoro può essere preso una volta sola. In caso di rete interrotta si arresta senza ripetere l’inferenza. Se il passo scade, una risposta tardiva non entra nella sessione. I budget del sito e `--max-jobs` sono distinti; anche le chiamate fallite contano.

## API personali salvate sul server

Per una prova separata puoi installare `.[workspace,openai,anthropic,gemini]` e avviare il server con una chiave di cifratura. **Non viene fatto automaticamente dalla preview.** Usa la preview in una cartella distinta: prepara un database e una challenge di prova, senza riutilizzare la produzione.

```powershell
$env:ZONE_CONNECTION_KEY = (.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(32))")
.\.venv\Scripts\python.exe -m tools.preview_workspace --out benchmark_data\workspace-api --port 8768 --enable-personal-api
```

Generare questa variabile non legge né invia credenziali provider. Apri `http://127.0.0.1:8768`, crea un account e salva la tua connessione API. L’ID modello è obbligatorio; non viene scelto un modello costoso in codice. API key e password non compaiono negli URL, nei prompt, nei registri o nello storage persistente del browser. Non impostare una chiave provider globale per servire utenti pubblici: ogni connessione usa esplicitamente quella del suo proprietario.

Sul server la chiave master deve restare stabile, in un secret protetto fuori da Git, database e log. Il valore di esempio precedente vive soltanto nel processo PowerShell: **non rigenerarlo a ogni riavvio di un ambiente persistente**. Senza la stessa chiave le API salvate non sono recuperabili e gli utenti devono riconnetterle. Cifratura AES-256-GCM con nonce casuale e associazione ad account, connessione, provider e modello; i token dei connettori sono conservati soltanto come hash.

Un database e i suoi backup restano dati privati: comprendono registri, hash di password e codici, API cifrate e, durante una chiamata, lavori pubblici temporanei. La cancellazione logica di un collegamento non elimina retroattivamente i backup. Conserva la master key separatamente e verifica il ripristino prima di distribuirlo. Non copiare il backup del VPS sul PC: resta valida la scelta dell’autore di mantenerlo sul VPS.

## Distribuzione successiva alle prove

La migrazione additiva 4 mantiene i checksum 1–3. Esegui backup prima dell’aggiornamento; un rollback del codice che conosce solo schema 3 richiede il ripristino della copia precedente in un nuovo file. Registrazione aperta solo con entrambi `--public-workspace --open-registration`, autenticazione accounts e origine esatta HTTPS. La modalità su invito continua a essere il default. `--max-accounts` limita la capacità iniziale (default 1000, inclusi account disabilitati).

L’immagine di default continua a essere offline. Una candidata con SDK per API personali può essere costruita, senza avviarla né distribuirla:

```powershell
docker build --build-arg ZONE_EXTRAS=workspace,openai,anthropic,gemini -t zone:workspace-candidate .
```

Non occorrono SDK ChatGPT/Ollama nel server quando si usa il connettore. Sul VPS mantenere HTTPS, cookie Secure, porta privata, log di accesso disabilitati, limiti CPU/RAM e backup. La configurazione dei flag e dei secret della candidata resta un passaggio successivo alle prove dell’autore.

## Limiti e criteri prima di aprire

- Test automatici con client simulati/baseline e browser locale; **nessuna nuova inferenza reale di questa versione verificata durante lo sviluppo**. Il pilot ChatGPT precedente non valida questo nuovo percorso multiutente.
- Limiti iniziali: 8 chiamate/8 turni per una AI personale, 3 punti per lancio, timeout 110 s, massimo 10 connessioni attive, 20 mondi per account e 5 agenti Arena. Quote account, esperimenti e chiamate restano distinti. Arena riusa anche le quote per agente.
- La demo offline non valida scoperta scientifica né robustezza di modelli reali. Nessuna riproducibilità esatta delle risposte LLM. Suggerimenti teorici dell’operatore possono influenzare il risultato; Arena li esclude dal protocollo comparabile.
- Prima dell’apertura: prove dell’autore con ogni collegamento offerto, prova di capacità sul VPS, distribuzione candidata con restore, revisione delle informazioni su dati/conservazione/supporto e percorso Hosted ChatGPT se desideri eliminare il connettore. Non sono inclusi invio email, recupero senza codice o cancellazione autonoma dell’account: le richieste di cancellazione richiedono il gestore.
- Il limite IP di login/registrazione è prudente. Dietro il proxy attuale più visitatori possono condividere quel limite; prima di una platea ampia occorre configurare una fonte IP fidata e verificarne il comportamento senza accettare header arbitrari dal client.
