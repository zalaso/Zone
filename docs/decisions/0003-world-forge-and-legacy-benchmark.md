# 0003 — World Forge privato, benchmark v0.3 invariato

Stato: accettata per la fase 2.

`World(family="ast")` usa lo stesso integratore RK4 delle quattro famiglie storiche. `parse_config` conserva esattamente lo schema dei mondi storici e accetta un secondo schema privato con `law` AST. La serializzazione esplicita ricostruisce il JSON dell'AST e mantiene i vecchi file di configurazione leggibili.

World Forge v1 produce candidati deterministici da versione, seed, livello e tentativo; li verifica contro una legge più semplice e una variante parametrica, con simulazioni, probe e controllo a passo dimezzato. Il manifest espone solo ID, hash, livello e limiti pubblicabili. Le misure di difficoltà restano vettoriali ed euristiche, senza un punteggio unico.

Le suite benchmark v0.3 non accettano mondi AST. Cambiarne schema o famiglie senza una nuova versione renderebbe non confrontabili risultati già salvati. Un'estensione del benchmark ai mondi AST richiede una versione successiva, probe e schedule verificati e una nuova analisi del disegno sperimentale. I livelli 6–9 espongono solo contratti descrittivi e sono rifiutati dal generatore fino a un'implementazione completa.
