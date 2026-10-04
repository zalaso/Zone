# 0006 — Modalità locali su sessioni separate

Stato: accettata, fase 6.

Riutilizzare backend, CAS, simulatori e scorer. Un agente web riceve soltanto `ModelRequest` costruiti tramite proiezione esplicita della propria storia pubblica; i probe entrano solo dopo la conclusione. La baseline numerica predefinita è offline e senza oracolo; i provider reali già esistenti richiedono tre opzioni esplicite al server e un passo autorizzato dalla persona. L'operatore esegue ogni esperimento.

Human vs AI crea atomicamente due sessioni con lo stesso record e limiti. Prima si congela la risposta umana, poi si attiva l'agente; scoring differito fino a entrambe le submission. Questo evita che la persona copi le risposte dell'agente e che risultati intermedi guidino il secondo partecipante. Dialogo teorico e modifiche sono disabilitati per entrambi; le motivazioni operative vengono normalizzate. L'operatore può arrestare anche una sessione dopo la conclusione o il freeze: la submission rimane registrata, senza scoring o riapertura. Il reveal richiede la chiusura di entrambe le indagini. Le dimensioni scientifiche restano separate, senza leaderboard o punteggio combinato.

World of the Day conserva un seed privato casuale per data UTC nel database, invece di derivare il seed dalla data pubblica. Il costruttore AST usa un formato distinto da Forge 1, per preservare la riproduzione e la compatibilità del benchmark v0.3. I mondi scritti dall'autore non sono challenge cieche e sono esclusi da Human vs AI.

Restano fuori: identità pubbliche, coordinamento multi-processo, controllo di consultazioni esterne, contaminazione e reveal fra sessioni dello stesso mondo. I controlli del costruttore sono numerici ed euristici. Una sessione locale umana e una baseline non stabiliscono capacità scientifiche di un LLM; il pilot reale è ancora da eseguire.
