# Primo pilot ChatGPT completato — 8 ottobre 2026

Sessione dell’autore: `sessions/pilot12-chatgpt-f94542b8deee`, modello richiesto e restituito `gpt-5.6-sol`, provider `chatgpt` con OAuth del piano, SDK OpenAI 2.54.0. L’autore ha eseguito il pilot; l’agente di sviluppo ha verificato soltanto registri e resoconto, senza nuove inferenze, credenziali reali o lettura della verità fisica privata.

**Il ciclo dell’indagine è completato:** richiesta, decisione umana, esecuzione, osservazione, ipotesi, previsione preregistrata, verifica e conclusione con evidenze, limiti e alternative. La conclusione è il messaggio 22, nell’ottava chiamata; nessun arresto per errore o superamento dei limiti.

## Risultati operativi

| Misura | Risultato |
| --- | --- |
| Chiamate / turni validi | 8 / 8, entro i tetti configurati |
| Risposte invalide / correzioni / errori provider | 0 / 0 / 0 |
| Esperimenti | 3 autorizzati, nessun rilancio, budget residuo 0 |
| Modalità | 2 esplorazioni, 1 verifica preregistrata |
| Osservazioni | 3 punti per esperimento, 9 campioni complessivi |
| Ipotesi / previsioni / conclusioni | 3 / 1 / 1 |
| Input / output / totale token | 19219 / 2174 / 21393 |
| Ragionamento / cache | 551 token già inclusi nell’output / 0 |
| Tempo totale delle chiamate | 63,351 s; escluso il tempo dell’operatore |
| Durata delle singole chiamate | 5,748–10,290 s |
| RMSE della verifica | 3,4851396216797643 × 10^-16 m |
| Errore massimo della verifica | 5,79553433516819 × 10^-16 m |
| Consumo del piano / crediti extra | L’autore conferma il controllo in ChatGPT Usage: sola quota dell’abbonamento, nessun credito extra |

Le impostazioni restano quelle del launcher: massimo 8 chiamate, 8 turni, 2 correzioni per passo, timeout remoto 120 s, 3 esperimenti e 3 punti per esperimento. `max_output_tokens` non è supportato da questa route: `generation_settings` lo registra come null, con limite locale di testo 64 KiB. La quota del piano resta distinta dai due budget del laboratorio. I token non costituiscono una misura monetaria: il mancato consumo di crediti extra è confermato dall’autore nelle impostazioni Usage, non certificato automaticamente dai registri. Questa conferma riguarda il pilot e non garantisce costi di sessioni future.

Con questa conferma, **fase 12 completata nel perimetro del primo pilot locale**. Identità multiutente, beta ospitata e apertura pubblica restano le fasi 13–15.

## Svolgimento e interpretazione

1. `exp_quiete_01`: origine, velocità nulla, durata 0,2 s, campioni a 0 / 0,1 / 0,2 s; esplorazione autorizzata. Il modello formula un andamento quadratico compatibile con le posizioni pubbliche.
2. `exp_velocita_02`: stessa posizione e griglia temporale, velocità iniziale (2, 3) m/s; verifica scelta dall’operatore. La previsione è nel messaggio 11, prima dell’avvio al messaggio 12 e delle misure al messaggio 13. L’errore è dell’ordine dell’arrotondamento floating point del simulatore. La verifica riguarda le posizioni, con `law_identification=not_assessed`.
3. `exp_posizione_03`: posizione iniziale (5, -4) m, velocità nulla, stessa griglia; esplorazione autorizzata. Il modello confronta gli spostamenti con il primo esperimento e aggiorna l’ipotesi. Questo confronto è a posteriori: non è una seconda verifica preregistrata.

L’ipotesi finale del modello è compatibile con `x(t) = x0 + vx0·t + 0,25·t²` e `y(t) = y0 + vy0·t − 4,68705·t²` nei casi osservati. È ricavata dalle sole misure pubbliche, non confrontata con i coefficienti privati. Il modello conclude correttamente che i punti non identificano una legge unica e conserva alternative plausibili.

Il risultato valida un primo percorso operativo con un LLM reale. Non valida il benchmark active/passive, Arena BYOA, l’equivalenza delle leggi o la capacità di scoperta su più mondi. Tutti i lanci coprono soltanto 0–0,2 s; i campioni t=0 sono gli stati iniziali già impostati, quindi i nove punti non sono nove misure dinamiche indipendenti. Velocità x/y nel secondo lancio e posizione x/y nel terzo cambiano insieme: restano possibili accoppiamenti non discriminati. Non ci sono repliche, probe successivi al freeze o valutazioni fuori dominio.

Nessuna domanda all’operatore, modifica o rifiuto è stata richiesta in questo pilot reale; questi rami restano coperti dai test simulati. Le motivazioni umane sono `prova`, senza suggerimenti teorici registrati. In generale suggerimenti dell’operatore possono influenzare l’indagine. Nessuna promessa di riproducibilità esatta del modello.

## Controlli sui registri

Controllo offline: 22 eventi con sequenza continua; 16 record di audit, otto `started` seguiti da otto `accepted`; tutte le risposte `completed`, nessuna correzione, tutti i testi classificati JSON valido e ricavati dallo stream. Tre approvazioni e modalità precedono tre avvii distinti; nessun request_id viene eseguito due volte. Previsione prima dell’avvio, budget residuo finale zero e conclusione finale verificati.

`text_extraction_version=2` conferma che il pilot usa la correzione del lettore. Questa sessione conferma il funzionamento del percorso corretto sul servizio reale; non ricostruisce la causa dei tre invalidi della precedente sessione `98d67609c131`, il cui testo non è conservato.

Impronte SHA-256 dei file originali, conservati localmente e ignorati da Git:

| File relativo alla sessione | SHA-256 |
| --- | --- |
| `public/events.jsonl` | `d3c0cc21bd8fe8142be48bc43cf0bd9bc124e991aa6b72ab26de4e6aa5891e25` |
| `private/model_calls.jsonl` | `c819fb0f7aa174f711451160f70da32655c3aa3f0a23a6466569d9577d7a7142` |

I test della correzione restano quelli documentati in [verifiche](verification.md): 246 test Python, regressioni dello stream e ciclo simulato. Questa revisione aggiunge l’evidenza reale e aggiorna solo documentazione; non cambia codice, budget, modelli o protocollo e non pubblica i registri privati.
