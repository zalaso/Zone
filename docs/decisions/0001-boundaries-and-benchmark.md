# 0001 — Confini del core e benchmark

Stato: accettata per lo sviluppo locale.

Il core fisico resta Python puro e indipendente da web/SDK. Gli adapter ricevono soltanto `ModelRequest` costruite per proiezione della storia pubblica. Le suite benchmark sono private fino a reveal autorizzato; il manifest conserva hash e ID opachi.

`active` e `passive_sequential` sono il confronto primario: stesso budget massimo e un'ipotesi dopo ogni osservazione. `passive_fixed` resta un controllo batch diagnostico. I probe di interpolazione ed estrapolazione e le metriche vengono riportati separatamente. La policy casuale e lo stimatore affine sono baseline non LLM con input pubblico; non hanno le capacità di un agente generale. Gli intervalli bootstrap descrittivi richiedono almeno otto mondi appaiati distinti; con campioni piccoli il report mostra `insufficient_sample` e non un'affermazione di superiorità.

SQLite e FastAPI sono rinviati alla prima API verticale. Il frontend potrà leggere solo DTO pubblici: mai serializzare direttamente `SimulationConfig`, suite private o oggetti `Session`.
