# World Forge v1 — fase 2

World Forge genera mondi privati con leggi AST validate, livelli 1–5 e seed riproducibile. Il simulatore RK4 usa la stessa interfaccia `simulate` per famiglie storiche e leggi AST. Le suite benchmark v0.1–v0.3 **rimangono nel vecchio formato**: World Forge non modifica né rigenera i loro mondi. Un benchmark con mondi AST richiederà una versione di suite successiva e una validazione metodologica separata.

## Generazione offline

Da PowerShell, in una cartella di output nuova:

```powershell
.\.venv\Scripts\python.exe -m hidden_lab forge levels
.\.venv\Scripts\python.exe -m hidden_lab forge generate --level 3 --private benchmark_data/forge-demo/world.json --manifest benchmark_data/forge-demo/manifest.json --config-out benchmark_data/forge-demo/config.json
.\.venv\Scripts\python.exe -m hidden_lab forge check --private benchmark_data/forge-demo/world.json --manifest benchmark_data/forge-demo/manifest.json
.\.venv\Scripts\python.exe -m hidden_lab shell --config benchmark_data/forge-demo/config.json --session sessions/forge-demo
```

Senza `--seed`, `generate` crea un seed privato casuale di 128 bit. Per una demo ripetibile si può aggiungere `--seed 123456789`; **non** usare un seed prevedibile per una challenge riservata, perché l'hash pubblico non impedisce un attacco per enumerazione. La cartella `benchmark_data/` e `sessions/` sono ignorate da Git. Conserva `world.json` e `config.json` fuori dal repository. Il comando rifiuta percorsi già esistenti e non contatta provider.

Il record privato contiene versione del generatore, seed, livello, tentativo, configurazione AST, schedule, probe e hash SHA-256 del JSON canonico senza il campo `sha256`. `forge check` rigenera esattamente il candidato dal seed e ripete i controlli. Il manifest pubblico contiene solo versione, ID opaco, hash, livello, budget e numero di probe per categoria; non contiene legge, coefficienti, seed, schedule, stati dei probe o verità delle accelerazioni. L'ID e l'hash servono a verificare un eventuale reveal deliberato, che questa CLI non automatizza.

Schedule e stati dei probe sono per ora **template fissi nel codice sorgente**: l'assenza dal manifest non li rende segreti in un progetto open source. Servono a filtrare mondi locali e a provare il software, non a una suite privata competitiva. Prima di usare mondi AST in un benchmark riservato occorrono probe generati sul server da seed privati e un nuovo protocollo versionato.

## Leggi e livelli

Ogni legge è un oggetto JSON con `level`, `ax`, `ay`. Esempio di livello 2:

```json
{
  "level": 2,
  "ax": {"op": "const", "value": 0},
  "ay": {"op": "add", "args": [
    {"op": "const", "value": -9.8},
    {"op": "mul", "args": [
      {"op": "const", "value": -0.2},
      {"op": "var", "name": "y"}
    ]}
  ]}
}
```

`parse_law` restituisce un oggetto immutabile; `canonical_json()` produce JSON ordinato; `evaluate_law(law, (x, y, vx, vy))` calcola le accelerazioni. I nodi ammessi sono `const`, `var`, `add`, `sub`, `mul`, `div` protetta, `abs`, `pow` con esponente intero 0–3, `sin`, `cos`, `tanh`, `norm` e `normalize` protetta. `time` è disponibile solo nel parser di espressioni quando abilitata esplicitamente; le leggi generabili dei livelli 1–5 sono stazionarie. Nessuna stringa viene valutata come codice. Massimo 64 nodi, profondità 12, costanti entro ±100 e valori numerici finiti entro ±1.000.000.

| Livello | Classe generata | Segnale controllato |
| --- | --- | --- |
| 1 | Accelerazione costante | Accelerazione non nulla |
| 2 | Una variabile, qui la quota `y` | Variazione con la quota |
| 3 | Termini additivi, qui velocità per asse | Sensibilità su entrambi gli assi |
| 4 | Accoppiamento fra assi | Sensibilità incrociata |
| 5 | Non linearità, qui modulo della velocità × componente | Curvatura rispetto alla velocità |

I livelli 6–9 sono **interfacce dichiarate ma non generabili**: regioni con controlli di frontiera; latenti con identifiabilità; memoria con replay dello stato; non stazionarietà con tempo e replay. `forge levels` li mostra esplicitamente. Il livello dichiara una classe strutturale, non una misura assoluta della difficoltà.

## Pipeline di accettazione

Per ogni candidato deterministico il generatore verifica schema e limiti dell'AST, riproducibilità dal seed, finitezza dell'accelerazione, schedule e probe validi. Esegue ogni lancio con RK4, controlla il dominio fisico e un margine di sicurezza, poi ripete il lancio con passo dimezzato e rifiuta differenze oltre 0,002 m. Richiede un segnale specifico del livello, distanza sui probe sia da una legge più semplice sia da una variante parametrica plausibile, e almeno un esperimento la cui traiettoria distingua entrambe le alternative. I probe di interpolazione sono stati nuovi entro il dominio iniziale ±20; quelli di estrapolazione sono esterni a quel dominio ma entro i limiti fisici. Un candidato fallito viene scartato; sono ammessi al massimo 16 tentativi deterministici per seed e livello.

`validate_generated_world` restituisce dimensioni separate della **difficoltà euristica**: nodi/profondità, segnale del livello, differenza nelle osservazioni, distanza dalle alternative sui probe, primo esperimento informativo e separazione in interpolazione/estrapolazione. Queste quantità non sono un punteggio unico né una garanzia di identificabilità. Le alternative usate sono due controlli costruiti, non l'insieme di tutte le leggi possibili; il controllo numerico a passo dimezzato non certifica la stabilità matematica globale. Le traiettorie osservabili sono quelle della schedule testata, non ogni esperimento che una persona potrebbe scegliere.

La sessione pubblica usa solo `apparatus`, richieste e osservazioni. Legge, seed e configurazione completa restano nei registri privati. Il modello remoto continua a ricevere payload costruiti dalla sola storia pubblica, senza accesso al simulatore, a file o alla `Session`.
