# Esperienza guidata del laboratorio

> Historical/advanced engineering reference. For the version 1.0 supported installation start with [Getting started](getting-started.md), [AI connections](ai-connections.md) and [self-hosting](self-hosting.md). Earlier phase statuses describe that earlier revision, not missing release features or a current hosted service.


Questa versione è un’anteprima locale per le prove dell’autore. Non aggiorna automaticamente il VPS e non esegue inferenze reali durante lo sviluppo.

## Provala

Nella cartella del progetto, con le dipendenze frontend già installate:

```powershell
Push-Location frontend
pnpm install --frozen-lockfile
pnpm run build
Pop-Location
.\.venv\Scripts\python.exe -m tools.preview_workspace --out benchmark_data\workspace-preview --port 8767
```

Apri http://127.0.0.1:8767. Se l’anteprima è già in esecuzione basta aggiornare la pagina dopo la compilazione; non avviare un secondo server sulla stessa porta. Crea un account locale e conserva il codice di recupero, oppure accedi con la password dell’account creato nell’anteprima. L’account online è separato.

1. Leggi **La tua prima indagine** e scegli **Inizia senza AI**. Ogni modalità ha una spiegazione di scopo, impostazioni, passaggi e risultato.
2. Crea una sessione. Il riquadro successivo indica l’azione disponibile. Imposta scopo, posizione, velocità, durata e intervallo di misura.
3. Approva o modifica, poi scegli esplorazione o verifica. In verifica registra prima ipotesi e posizioni numeriche previste. Il lancio richiede sempre un altro clic esplicito; nessun silenzio viene interpretato come autorizzazione.
4. Dopo **Esegui esperimento** segui i campioni con **Riproduci misure** o con il cursore. La previsione preregistrata è tratteggiata e può essere nascosta. I dati restano disponibili anche nella tabella del registro.
5. Apri **Registra un’ipotesi o una domanda**, oppure **Concludi e passa alla prova finale**. La conclusione ammette informazioni insufficienti. I probe finali chiedono accelerazioni, mentre le previsioni degli esperimenti chiedono posizioni.
6. Consulta **Guida a Zone** per confrontare i sei percorsi, cercare termini e aprire i dettagli tecnici. In **Account** trovi utilizzo, quote residue e modello delle nuove indagini; il nome in alto apre il profilo.

**Build a Universe** mostra l’attesa della validazione e comunica il mondo accettato soltanto dopo la conferma del server. **Watch an Agent** e **Zone Arena** distinguono l’attesa di una risposta dal lancio fisico: un passo AI non esegue un esperimento. Senza connessione personale viene usata la baseline numerica, esplicitamente identificata come algoritmo e non LLM. Per modelli reali seguire [la guida alle connessioni](public-workspace.md).

## Formule

Nei testi di ipotesi, scopo, domanda, risposta e conclusione sono supportati `$...$`, `$$...$$`, `\(...\)` e `\[...\]`. Per esempio:

```text
Ipotesi provvisoria: $a_y=-\gamma v_y$.
```

L’anteprima dell’ipotesi mostra la formula prima della registrazione. La stringa originale viene conservata nel registro; cambia soltanto la presentazione. KaTeX 0.19.0 produce MathML nativo per browser moderni; `trust=false`, macro isolate, massimo 100 espansioni e dimensione limitata. Errori o comandi non ammessi restano testo. Non si eseguono formule, non si caricano immagini o font esterni e non si allenta la Content Security Policy. Riferimenti: [opzioni ufficiali](https://katex.org/docs/options), [sicurezza](https://katex.org/docs/security).

## Fedeltà scientifica e movimento

Il grafico principale riceve solo gli eventi pubblici fino al cursore del replay. Una nuova proposta non eredita le misure del lancio precedente. Le modifiche approvate precedono la previsione; i fallimenti non generano una traiettoria fittizia. Il modello riceve numeri e storia pubblica, non l’immagine del grafico. La visualizzazione non è una lettura del ragionamento interno del modello.

I punti sono campioni misurati, le linee li collegano senza aggiungere dati. Le scale degli assi sono indipendenti; il replay non è un’integrazione fisica continua né un video a velocità reale. Prima del lancio si mostrano posizione e direzione della velocità, senza prevedere la traiettoria. L’esempio senza account è etichettato come dimostrativo e non proviene da un mondo privato.

Le animazioni d’attesa non mostrano percentuali o fasi interne inventate. Non ci sono attese artificiali nell’applicazione. La preferenza di sistema **riduci movimento** disattiva i cicli e le transizioni; il replay resta manuale e controllabile. I grafici non sostituiscono le tabelle accessibili. Non sono stati aggiunti video esterni o generazione di contenuti con un’AI.

## Verifiche ripetibili, senza credenziali

Con l’anteprima locale avviata e il frontend compilato:

```powershell
Push-Location frontend
pnpm test --maxWorkers=2
pnpm run lint
pnpm run check:bundle
pnpm run test:quality
pnpm run test:browser:experience
Start-Sleep -Seconds 60 # limite comune per IP del server locale
pnpm run test:browser:workspace
Pop-Location
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
```

I due test browser usano Edge già installato, solo loopback e account sintetici. Nessuna chiamata ai provider. Il test dell’esperienza ritarda soltanto la consegna di alcune risposte locali per fotografare gli stati d’attesa: il prodotto non introduce quel ritardo. Artefatti in `benchmark_data/experience-browser/`, esclusi da Git. La verifica con modelli personali reali e la pubblicazione restano successive alle prove dell’autore.

Il collaudo dell’esperienza blocca anche le richieste verso host esterni. Un eventuale script di Kaspersky iniettato dal sistema è identificato separatamente e bloccato nel solo contesto di test, senza cambiare antivirus o impostazioni del PC. Qualunque altra richiesta esterna del prodotto fa fallire il controllo.
