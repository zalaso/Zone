# Sicurezza e segnalazioni

La versione 0.10 è pensata per un operatore e un host fidati, su loopback. Il repository non offre ancora un servizio pubblico, identità pubbliche o attestazione dei client BYOA. Leggere [threat model](docs/threat-model.md), [operazioni](docs/operations.md) e [checklist](docs/release-checklist.md) prima di distribuire il software.

Non pubblicare vulnerabilità con credenziali, dati privati o istruzioni di sfruttamento su istanze altrui. Il repository è attualmente locale: prima della pubblicazione non esiste una inbox GitHub dedicata. Contattare il maintainer [zalaso](https://github.com/zalaso) per concordare un canale privato; all'apertura del repository abilitare Private Vulnerability Reporting e aggiornare questa pagina con il canale verificato. Non supporre che quel canale sia già attivo.

Per una segnalazione usare una copia locale e dati sintetici; indicare versione, superficie, prerequisiti, impatto e riproduzione minima senza segreti. Non sono autorizzati test contro servizi esterni. Si verifica la versione corrente; non c'è ancora un ciclo formalizzato di supporto per versioni precedenti. Nessuna promessa di tempi di risposta o bug bounty.

Token, database SQLite, backup, suite private e nonce sono dati privati dell'operatore. I backup non sono cifrati da Zone e non devono essere inseriti in Git, immagini, artifact CI o bundle browser. In caso di incidente arrestare il server, conservare una copia controllata, ruotare le credenziali e verificare i casi già rivelati prima di riaprire una challenge.
