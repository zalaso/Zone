# ADR 0008 — Split impegnati e catalogo di integrità locale

Stato: accettata, fase 8.

Arena necessita distinguere prove su leggi già divulgate dai test riservati senza modificare lo schema benchmark v0.3. Un hash grezzo di leggi con pochi parametri può rivelare informazioni, e un reveal anticipato altera le condizioni degli altri trial.

Introduciamo un pacchetto Integrity v1 esterno agli schemi fisici: train/development completi pubblici, test privato, ID disgiunti, commitment salati e seed derivati con domini separati. Un catalogo SQLite riusa mondi, eventi e transazioni esistenti; ammissione, flag e ritiro sono persistenti. Il test entra solo in Arena, con una challenge per caso, score nascosto all'agente fino alla chiusura e reveal che verifica atomicamente tutte le indagini sulla stessa legge. La proof va verificata contro il manifest conservato prima del trial.

Manteniamo i mondi legacy come confronti diagnostici e le suite v0.3 immutate. La CLI benchmark può registrare provenienza e rifiuta aggregazioni miste; il processo locale che possiede la suite privata rimane fidato. Non aggiungiamo un registro globale delle esecuzioni né rendiamo la CLI un confine di sicurezza contro il suo proprietario.

Duplicati fisici vengono rilevati per struttura normalizzata e firma numerica su 16 stati: euristica, non equivalenza generale. Flag operatore append-only escludono dai ranghi conservando grezzi. Rate account persistenti integrano quote e limite IP, senza fingere di misurare spese LLM esterne. La provenienza storica non viene riscritta dopo il reveal; una reimportazione nel medesimo DB non ripristina ammissibilità.

Conseguenze: gestore e host sono fidati, il manifest necessita un riferimento originale esterno, la contaminazione fuori dal catalogo va dichiarata e i test reali richiedono casi nuovi. Sicurezza pubblica, identità, attestazioni, migrazioni e deployment rimangono fuori da questa fase. Vedi [threat model](../threat-model.md).
