# Zone con il piano ChatGPT — preview, 8 ottobre 2026

> Historical/advanced engineering reference. For the version 1.0 supported installation start with [Getting started](getting-started.md), [AI connections](ai-connections.md) and [self-hosting](self-hosting.md). Earlier phase statuses describe that earlier revision, not missing release features or a current hosted service.


Il provider **`chatgpt`** usa il collegamento ufficiale Sign in with ChatGPT per app locali, con OAuth e Responses API in streaming. È distinto da **`openai`**, che continua a richiedere `OPENAI_API_KEY` ed essere fatturato come API. Nessun fallback tra i due, nessun recupero delle credenziali di Codex o delle conversazioni dell’account. Il modello riceve solo il contratto e la storia pubblica di Zone, senza strumenti, filesystem, Session o configurazioni private.

Fonti ufficiali controllate l’8 ottobre: [registrazione e consenso](https://developers.openai.com/siwc/token-sharing-open-source/sign-in), [modelli e inferenza](https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference), [account, rinnovo e utilizzo](https://developers.openai.com/siwc/token-sharing-open-source/profiles-and-sessions), [limiti della preview](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations), [errori e recupero](https://developers.openai.com/siwc/token-sharing-open-source/errors-and-recovery). L’accesso effettivo dipende dall’account/workspace, dal modello e dalla disponibilità della preview; il login o il catalogo da soli non provano che un’inferenza sarà accettata.

## Primo accesso su questo PC

Apri **PowerShell**, nella cartella `C:\path\to\Zone`:

```powershell
Set-Location C:\path\to\Zone
$env:PYTHONUTF8 = '1'
.\.venv\Scripts\python.exe -m hidden_lab chatgpt login
```

Si apre il browser di sistema con **Continue with ChatGPT**. Scegli il tuo account/workspace e autorizza **Zone** a usare il piano. Torna al terminale: deve risultare `Login verificato. Uso del piano: autorizzato.` La finestra browser conferma solo ricezione del callback; la verifica effettiva è nel terminale. Non copiare URL del callback, codici o token in chat. Il login ha 180 s di attesa, si annulla con Ctrl+C e non effettua inferenze.

Su questo PC OpenAI SDK e PyJWT sono installati nella `.venv`. In un altro checkout, prepara l’extra gratuito prima del login:

```powershell
.\.venv\Scripts\python.exe -m pip install -e '.[chatgpt]'
```

## Primo pilot

Prima controlla in **ChatGPT Settings → Usage** il permesso dell’app Zone, la quota e i limiti assegnati; disabilita eventuali crediti extra/acquisti automatici per questa prova. Il programma non attesta queste impostazioni né un costo monetario. Le quote del piano possono essere condivise con altre app; non sono inferenze illimitate.

```powershell
.\.venv\Scripts\python.exe -m hidden_lab chatgpt pilot
```

1. Digita `piano` dopo il controllo delle impostazioni. Invio annulla, senza inferenza.
2. Scegli un modello con il numero mostrato dal catalogo attuale dell’account. Nessun modello costoso o predefinito è fissato nel codice; un input vuoto non seleziona nulla.
3. Zone genera e valida un mondo Forge livello 1 nuovo, seed casuale privato, tre esperimenti; mostra la cartella `sessions/pilot12-chatgpt-<id>`.
4. Digita `avvia` per consentire la prima generazione. Poi `a/m/r`, motivazione pubblica, `e/v` e `esegui` per ogni lancio. In verifica, il modello vede le modifiche definitive prima di preregistrare i punti. Nessun silenzio equivale a consenso.

Puoi scegliere un modello esplicito del catalogo con `chatgpt pilot --model SLUG`. Questo pilot è una nuova indagine, separata dai tentativi Gemini: non importa né ripete il vecchio esperimento. La ripresa delle sessioni interrotte non è implementata. Suggerimenti teorici dell’operatore possono influenzare i risultati: usa risposte operative quando vuoi misurare le capacità del modello.

Limiti: **8 chiamate**, **8 turni validi**, **2 correzioni per passo** entro il tetto totale, **3 esperimenti**, **3 punti per esperimento**. Timeout HTTP 120 s per operazione di rete, controllo del tempo trascorso agli eventi dello stream. Un’interruzione conta come chiamata; non causa retry, fallback o rilancio di un esperimento. Se il provider smette di inviare eventi, interviene il timeout di lettura; non è un termine assoluto preciso al millisecondo dell’intera chiamata.

**La preview rifiuta `max_output_tokens`**: questo provider lo omette insieme a `truncation` e agli altri campi non supportati. Il campo storico nelle `AgentSettings` non limita la generazione ChatGPT. `generation_settings` registra esplicitamente `max_output_tokens: null` e `max_output_tokens_supported: false`. Il limite locale di testo è **64 KiB**; lo stream viene fermato anche oltre 2 MB di eventi. Questi controlli non limitano i token già generati dal servizio né certificano la spesa. Budget delle chiamate, quota del piano e budget fisico restano distinti.

Il client raccoglie gli eventi `response.output_text.delta` e `response.output_text.done`, ordinando le parti per indice senza duplicare il riepilogo finale. Il testo è disponibile solo dopo `response.completed`; EOF, errore, rifiuto o risposta incompleta non vengono trattati come successo. Due rappresentazioni del testo discordanti sono rifiutate. Il JSON ricevuto passa dalla validazione locale esistente, inclusi ordine dei messaggi e vincoli fisici: non vengono rimossi blocchi Markdown né riparati JSON malformati. Niente codice o formule del modello vengono eseguiti. I registri restano quelli di `investigate`, con provider `chatgpt`, impostazioni, modello richiesto/restituito e utilizzo nativo quando disponibile; uso ignoto non significa zero. Errori conservano solo codici consentiti e status HTTP, senza corpi, header o credenziali. Le risposte non sono esattamente riproducibili.

Se una risposta è invalida, la diagnostica strutturale distingue testo vuoto, blocco Markdown, JSON invalido e JSON valido che viola il contratto. `provider_details` conserva soltanto `json_syntax`, `response_text_bytes`, `text_delta_events` e `text_source`; `generation_settings.text_extraction_version=2` identifica il lettore corretto. Output grezzo e frammenti degli errori JSON non vengono registrati né aggiunti al prompt.

## Gestire l’account

```powershell
.\.venv\Scripts\python.exe -m hidden_lab chatgpt status
.\.venv\Scripts\python.exe -m hidden_lab chatgpt models
.\.venv\Scripts\python.exe -m hidden_lab chatgpt login --new-account
.\.venv\Scripts\python.exe -m hidden_lab chatgpt select 1
.\.venv\Scripts\python.exe -m hidden_lab chatgpt logout
```

`status` è offline e mostra account, selezione e permesso, senza token. `models` interroga il catalogo e può rinnovare OAuth, ma non genera risposte. Le registrazioni di account/workspace diversi restano separate, anche con la stessa email. Un normale `login` riusa il client dell’account selezionato; `--new-account` aggiunge una registrazione.

`logout` tenta la revoca remota e rimuove sempre i token locali dell’account selezionato, conservando host e associazione account/client per un nuovo login. Se la revoca remota non è confermata, il terminale lo segnala: disconnetti Zone dalle impostazioni ChatGPT. Gli altri account salvati restano intatti.

## Protezione locale

Credenziali fuori dal repository e dai registri: su Windows `%LOCALAPPDATA%\Zone\chatgpt\credentials.dpapi`, cifrate con **DPAPI dell’utente corrente**; su Unix `~/.config/zone/chatgpt/credentials.json`, cartella 0700 e file 0600. Non copiare questi file per condividere una sessione. Non è un sandbox contro programmi eseguiti dallo stesso utente.

Host UUID persistito prima del consenso; PKCE S256, state e nonce nuovi per tentativo; callback esclusivamente `127.0.0.1`, porta assegnata dal sistema; query non registrata. Le firme ID token sono verificate con PyJWT e JWKS ufficiali, **RS256**, issuer, audience, scadenza e nonce; una diversa identità non può sostituire l’account selezionato. Algoritmi diversi sono rifiutati. Token scambiati solo con gli endpoint OpenAI fissi, TLS, senza proxy da ambiente né redirect automatici.

Un lock impedisce processi concorrenti sullo stesso archivio e serializza i rinnovi. Dopo un refresh riuscito, access/refresh/ID token e scadenza vengono sostituiti atomicamente. Un errore temporaneo conserva le credenziali; una revoca confermata al refresh elimina i token inutilizzabili e richiede un nuovo login esplicito. Nessun login automatico dopo un errore del modello. Se il processo viene terminato brutalmente può restare `session.lock`: rimuovilo manualmente **solo dopo aver verificato che nessun processo Zone usa l’account**.

## Verificato e ancora da verificare

Verificato offline: firma e claims con JWT sintetici; browser/callback e HTTP simulati; cifratura DPAPI reale su dati sintetici; rinnovo, revoca e isolamento account; SDK OpenAI reale su trasporto HTTP fittizio; ciclo completo, modifica, rifiuto, correzione, errori dopo le misure, payload pubblici e metadati ridotti. Queste prove non attestano accesso al tuo account o capacità di ricerca del modello.

L’autore ha eseguito il primo tentativo reale `sessions/pilot12-chatgpt-98d67609c131`: tre risposte `completed` da `gpt-5.6-sol`, tutte rifiutate come JSON invalido, zero turni validi e zero esperimenti. È stato riprodotto e corretto offline un difetto del lettore che ignorava i delta quando il riepilogo finale non conteneva testo. I vecchi registri non conservano il testo né la forma dello stream: non dimostrano che questo difetto fosse la causa di quel tentativo.

La successiva sessione `sessions/pilot12-chatgpt-f94542b8deee` ha confermato il percorso corretto sul modello reale: otto risposte valide, tre esperimenti autorizzati, ipotesi aggiornate, una previsione preregistrata e conclusione, senza errori o correzioni. Utilizzo nativo 21393 token, tempo delle chiamate 63,351 s. L’autore ha confermato in Usage sola quota dell’abbonamento, nessun credito extra. **Fase 12 completata nel perimetro del primo pilot locale**; [risultati e limiti](pilot-chatgpt-result.md). Non costituisce validazione del benchmark o identificazione univoca della legge. Nessuna chiamata reale è stata effettuata dall’agente di sviluppo durante la verifica dei registri. Il backend e il frontend supportano ora anche il pilot personale `chatgpt`, con archivio dedicato, proprietario esplicito e invitati offline: [pilot web](web-llm-pilot.md). Dopo autorizzazione, la registrazione selezionata è stata trasferita al VPS e i token locali rimossi; `gpt-5.6-sol` è attivo soltanto per `guido`. Nessuna inferenza web avviata durante l’attivazione: primo pilot e controllo Usage restano da verificare dall’autore. Benchmark v0.3 e Arena non acquisiscono un provider aggiuntivo. Il benchmark e i relativi formati restano invariati.
