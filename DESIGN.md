# Zone — sistema di interfaccia

## Theme

Laboratorio scientifico chiaro. Persone che leggono misure e compilano esperimenti su un laptop in luce ambiente: superfici chiare, contrasto netto e pochi accenti.

## Colors

Neutri freddi, superficie bianca, testo inchiostro, blu come accento operativo. Token CSS in `frontend/src/workspace.css`; stati errore e successo hanno colore e testo, mai solo colore.

## Typography

Stack sans di sistema, 16px di base; scala fissa per il prodotto. Monospace solo per identificativi e dati numerici. Testi di spiegazione massimo 70ch.

## Layout

Barra superiore compatta, navigazione laterale sul desktop, navigazione a scorrimento sul telefono. Pagine: laboratorio, connessioni AI, sessioni, account e amministrazione. Nel laboratorio azioni e registro su due colonne, impilate sul mobile.

## Components

Bottoni 8px, pannelli 12px, campi 8px; bordi sottili, ombre solo quando servono. Etichette sopra i campi. Stati default, hover, focus, disabled, loading ed errore. Segreti mascherati e cancellati dal form dopo l'invio, mai conservati nello storage del browser.

## Motion

Transizioni di stato 160ms, nessuna coreografia d'ingresso. Le attese di generazione, chiamata AI e lancio hanno animazioni distinte, prive di percentuali inventate; il tempo mostrato è quello trascorso. Il replay si avvia e si arresta su comando e usa soltanto campioni pubblici. `prefers-reduced-motion` azzera transizioni e animazioni continue; i controlli manuali restano disponibili.

## Spiegazioni e visualizzazioni

Guida introduttiva, schede per tutte le modalità, glossario ricercabile e dettagli tecnici separati. Il laboratorio mostra il prossimo passo, nasconde i moduli secondari in sezioni espandibili e distingue una nuova configurazione dall’indagine attiva. Il profilo espone quote e risorse distinte, connessione selezionata, recupero e limiti delle funzioni disponibili.

La vista dell’esperimento usa esclusivamente gli eventi pubblici fino al cursore del replay, rispetta modifiche approvate, distingue osservazioni e previsioni ed esplicita che le linee collegano i campioni. Prima del lancio mostra solo posizione e direzione della velocità iniziali. Nessuna legge o misura viene ricostruita dal browser. Gli assi hanno scale indipendenti dichiarate.

Le formule delimitate in LaTeX vengono impaginate con KaTeX in MathML nativo (browser moderni), senza HTML non fidato, risorse esterne o indebolimento della CSP. Comandi non supportati restano testo; macro e dimensioni sono limitate.

L'interfaccia usa l'inglese. Le note dell'utente e i messaggi scientifici dei modelli
mantengono la propria lingua. Esperimenti, ipotesi e stati di verifica hanno
riferimenti leggibili; gli identificativi opachi restano nei dettagli tecnici.
Nessuna numerazione decorativa nelle modalità. Ordine degli eventi, budget,
misure e unità restano visibili perché hanno un significato operativo.
I numeri mostrati usano il punto decimale e precisione limitata, con notazione
scientifica per valori molto piccoli o grandi. I registri conservano la precisione
originale e la baseline non stampa sequenze di coefficienti nella spiegazione.
