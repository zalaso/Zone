# Laboratorio web locale — fasi 5–7

> Historical/advanced engineering reference. For the version 1.0 supported installation start with [Getting started](getting-started.md), [AI connections](ai-connections.md) and [self-hosting](self-hosting.md). Earlier phase statuses describe that earlier revision, not missing release features or a current hosted service.


La UI in `frontend/` è un client React/TypeScript/Vite della [API locale](backend.md). Usa solo `/v1` sullo stesso origin; Vite inoltra queste richieste al backend su `127.0.0.1:8765`. Non contiene un modello LLM, non esegue formule o codice inviati come testo e non legge direttamente SQLite o i file del mondo. Per questa fase una persona può compilare i messaggi del ruolo agente e quelli dell'operatore nella stessa pagina. La separazione dei ruoli è applicata dal backend tramite token diversi. La fase 6 aggiunge [cinque modalità locali](public-modes.md): un agente gestito sul server può usare la baseline offline predefinita oppure un provider configurato esplicitamente. Il browser non chiama provider esterni.

## Prima sessione locale

Servono Python con l'extra `backend`, Node.js 22.12 o superiore e pnpm. Da PowerShell, nella radice del repository:

```powershell
.\.venv\Scripts\python.exe -m pip install -e '.[backend]'
.\.venv\Scripts\python.exe -m hidden_lab forge generate --level 1 --seed 123456 --budget 3 --private benchmark_data/web-demo/world.json --manifest benchmark_data/web-demo/manifest.json
$env:ZONE_OPERATOR_TOKEN = [Convert]::ToHexString([Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
Set-Clipboard $env:ZONE_OPERATOR_TOKEN
.\.venv\Scripts\python.exe -m hidden_lab serve --db benchmark_data/web-demo/zone.sqlite3 --world benchmark_data/web-demo/world.json --port 8765
```

Lascia il backend acceso. In un **secondo terminale**, dalla stessa radice:

```powershell
cd frontend
pnpm install --frozen-lockfile
pnpm dev
```

Apri `http://127.0.0.1:5173/`. Incolla nella UI il token operatore copiato negli appunti dal primo terminale e scegli il mondo pubblico. Alla creazione, il backend restituisce il token agente una sola volta. La pagina lo mantiene soltanto in memoria; copialo in un luogo privato prima di chiudere la scheda se vuoi riprendere la sessione. Per una sessione già creata, usa l'ID per il replay pubblico e reinserisci entrambi i token per continuare.

Il percorso è: richiesta con scopo e parametri → approvazione, modifica o rifiuto → scelta esplicita fra esplorazione e verifica → eventuale ipotesi e previsione preregistrata sui tempi dei parametri **approvati** → pulsante di esecuzione dell'operatore → misure nel registro → conclusione con evidenze, limiti e alternative → challenge con probe pubblici → previsioni numeriche di accelerazione → punteggi separati e replay. Domande dell'agente interrompono il flusso finché l'operatore risponde. Si può concludere senza una legge finale se le evidenze sono insufficienti. Il reveal è separato, solo per l'operatore, dopo risultato o arresto, con una conferma esplicita; mostra dati privati sulla pagina.

Nessun silenzio dell'operatore attiva una decisione. Il pulsante `Esegui esperimento` non viene premuto dal client. Un errore di rete **non** ritenta automaticamente una mutazione: aggiorna lo stato prima di decidere se intervenire. In particolare, non ripetere manualmente un lancio il cui stato è `execution_started`; il backend ha già consumato il budget. Le versioni degli eventi prevengono scritture su uno stato vecchio. Il replay carica tutte le pagine da 100 eventi e consente di avanzare evento per evento; il cursore non modifica la sessione.

## Confine e limiti

Le credenziali vengono inviate soltanto nell'header `X-Zone-Token` delle azioni autorizzate, mai in URL, cookie o storage del browser. Il bundle non contiene token, mondo privato, seed, coefficienti, griglia di verità o endpoint esterni. I contenuti pubblici arrivano dalle proiezioni del backend; la UI usa React per il rendering testuale, senza HTML arbitrario. Il token operatore inserito nella pagina dà accesso a reveal e arresto: usa la UI solo sulla macchina locale fidata. Il server e Vite sono vincolati a loopback. Non è una UI pubblica multiutente né una sandbox contro estensioni del browser o chi controlla la macchina.

Le previsioni della verifica usano tutti i tempi previsti dal protocollo. Per esperimenti lunghi con molti campioni, la compilazione manuale può risultare laboriosa. La legge AST è facoltativa e deve rispettare il formato della [identificazione](identification.md); il backend la valida e la valuta in un interprete sicuro. La UI non calcola punteggi né verità privata. La ripresa di un lancio fisicamente interrotto resta futura. La scheda [Zone Arena](arena.md) della fase 7 aggiunge gestione delle credenziali revocabili, challenge, trial esterni, decisioni e leaderboard per dimensione; i token storici del laboratorio conservano il comportamento originario. Non è stato effettuato un trial con LLM reale né alcuna chiamata API a pagamento nello sviluppo della UI.

## Verifiche locali

```powershell
cd frontend
pnpm test
pnpm build
cd ..
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

I test frontend usano API simulate: verificano la sequenza decisione/modalità/lancio, rifiuto, modifica, challenge e risultato, oltre a header, paginazione e mancato retry del lancio. I test Python verificano il backend reale e il confine pubblico/privato senza rete. La build Vite produce `frontend/dist/`, ignorata da Git: ispezionarla per confermare l'assenza di credenziali prima di un'eventuale distribuzione. La distribuzione non è prevista nelle fasi 5–6. Le prove browser reali sono documentate in [verifiche locali](verification.md).
