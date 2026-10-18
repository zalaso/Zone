# Contribuire a Zone

Zone è un laboratorio locale di ricerca, con licenza [MIT](LICENSE). Prima di cambiare il protocollo leggere [architettura](docs/architecture.md), [ROADMAP](ROADMAP.md) e [threat model](docs/threat-model.md). Proporre cambiamenti piccoli con criteri verificabili e documentazione coerente.

## Checkout e sviluppo

Python 3.11 o successivo, Node 22 e pnpm 10.28.0. Da PowerShell nella radice:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -c constraints-ci.txt -e '.[workspace,all-llm,dev]'
$env:MPLBACKEND = 'Agg'
$env:MPLCONFIGDIR = Join-Path (Get-Location) 'benchmark_data/mpl-cache'
.\.venv\Scripts\python.exe -m ruff check hidden_lab tests tools
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
.\.venv\Scripts\python.exe -m hidden_lab ops demo --out benchmark_data/contributor-demo
cd frontend
pnpm install --frozen-lockfile
pnpm audit --audit-level moderate
pnpm typecheck
pnpm lint
pnpm test:quality
pnpm test
pnpm build
pnpm check:bundle
cd ..
.\.venv\Scripts\python.exe tools/build_release.py --out dist
.\.venv\Scripts\python.exe tools/check_release.py --archives dist
git diff --check
```

Su Linux usare `.venv/bin/python`. La demo richiede una cartella nuova. Gli SDK sono facoltativi per l'uso normale: la CI li installa per verificare adapter con trasporti fittizi, senza credenziali. `constraints-ci.txt` fissa le dipendenze dirette provate; non è un lock transitivo. Il frontend conserva il lock pnpm.

Per lavorare sull'interfaccia avvia `python -m hidden_lab workspace --data ./zone-data --web-dir frontend/dist` dopo il build: il percorso esplicito evita di mostrare un precedente bundle generato da un build della release nello stesso checkout.

Ruff controlla errori di sintassi, nomi e import inutilizzati; TypeScript usa controlli strict. Il lint AST frontend vieta esecuzione dinamica, HTML raw e storage persistente: non è un formatter né un analizzatore generale di sicurezza. Le scansioni di bundle sono euristiche. Aggiungere test di comportamento per nuove transizioni, autorizzazioni o confini, senza duplicare l'implementazione.

## Confini da conservare

- Il provider riceve solo payload costruiti esplicitamente da storia e contratto pubblici. Mai codice, README, seed, configurazioni, nonce test, verità o accesso a strumenti.
- Approvazione, scelta esplorazione/verifica e autorizzazione di esecuzione restano azioni distinte. Il silenzio non autorizza esperimenti.
- Risultati grezzi e metriche rimangono separati; `active` si confronta principalmente con `passive_sequential`. Non indebolire l'appaiamento delle configurazioni.
- Conservare eventi, revoche, quote, receipt idempotenti, embargo, flag e ritiro dopo reveal; non inserire purge automatici.
- Non effettuare chiamate reali, scaricare modelli, pubblicare artefatti o distribuire il servizio nei test. Un pilot reale richiede autorizzazione separata.

Prima di una PR eseguire i controlli pertinenti e indicare test passati, eventuali skip e limiti. Non allegare database, token, pacchetti test privati, screenshot con segreti o log completi dei provider. Una segnalazione di sicurezza segue [SECURITY.md](SECURITY.md).

## Release process

The supported release is built with `python tools/build_release.py --out dist` after installing the frontend lockfile. It includes audited static assets in both wheel and source archive, preserves dependency notices and writes SHA256SUMS. Run `python tools/check_publication.py --history --archives dist` before publishing. The ordinary base-package build remains possible for CLI-only development; public application releases must include the UI. Never upload local databases or private test material. See [release gates](docs/release-checklist.md).
