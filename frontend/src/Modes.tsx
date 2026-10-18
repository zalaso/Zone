import { useState, type FormEvent } from 'react'
import { api } from './api'
import { ResultView } from './view'
import type { ActivityKind } from './LabVisuals'
import type { AgentInfo, Match, WorldManifest } from './types'

export const modes = [
  ['scientist', 'Scientist', 'Conduci tu l’indagine: proposte, ipotesi e previsioni, con un registro completo.'],
  ['human_vs_ai', 'Human vs AI', 'Stesso mondo, budget e probe. Consegna prima la tua risposta; poi osserva l’agente. Le storie restano separate.'],
  ['watch_agent', 'Watch an Agent', 'L’agente propone e ragiona. Tu approvi, scegli esplorazione o verifica ed esegui ogni lancio.'],
  ['world_of_day', 'World of the Day', 'Un mondo locale per giorno UTC, conservato in SQLite. Conduci l’indagine come Scientist.'],
  ['build_universe', 'Build a Universe', 'Genera un mondo o definisci un AST limitato. Il server lo valida prima di renderlo disponibile.'],
] as const

export function AgentDescription({ agent }: { agent: AgentInfo }) {
  const plan = agent.provider === 'chatgpt'
  return <p className="field-hint"><strong>{plan ? 'Modello reale · piano ChatGPT personale' : agent.real_model ? 'Provider reale' : 'Baseline numerica offline · non è un LLM'}</strong><br />{agent.provider} / {agent.model} · {agent.settings.max_calls} chiamate · {agent.settings.max_turns} turni. {plan ? 'Ogni passo usa la quota del piano, incluse le correzioni. Nessun fallback API. Riservato al proprietario; controlla Usage e disabilita i crediti extra. La preview non consente un tetto ai token generati.' : agent.real_model ? 'Ogni passo esplicito può consumare API, inclusi i tentativi di correzione.' : 'Nessuna credenziale o chiamata API.'}</p>
}

export function UniverseBuilder({ token, busy, action, ready }: { token: string; busy: boolean;
  action: (work: () => Promise<unknown>, success: string, kind?: ActivityKind) => Promise<void>; ready: (world: WorldManifest) => void }) {
  const [kind, setKind] = useState('generate')
  const [building, setBuilding] = useState(false)
  const [created, setCreated] = useState<WorldManifest | null>(null)
  const [level, setLevel] = useState(1)
  const [budget, setBudget] = useState(3)
  const [law, setLaw] = useState('{\n  "level": 1,\n  "ax": {"op": "const", "value": 1},\n  "ay": {"op": "const", "value": -4}\n}')
  function submit(event: FormEvent) {
    event.preventDefault()
    setBuilding(true); setCreated(null)
    void action(async () => {
      let result: { world: WorldManifest }
      if (kind === 'generate') result = await api.generate(level, budget, token)
      else {
        let value: unknown
        try { value = JSON.parse(law) } catch { throw new Error('AST JSON non valido. Correggi il testo prima di inviarlo.') }
        result = await api.build(value, budget, token)
      }
      ready(result.world); setCreated(result.world)
    }, 'Mondo validato e selezionato. Puoi avviare una sessione.', 'world').finally(() => setBuilding(false))
  }
  return <section className="panel"><div className="panel-heading"><span className="kicker">WORLD FORGE / LOCALE</span><h2>Costruisci un universo</h2></div><p>Il generatore crea una legge nascosta e controlla il mondo prima di registrarlo. Il livello descrive la complessità strutturale; per il primo tentativo scegli 1. Il budget indica quanti lanci avrai in una sessione.</p><div className={`forge-visual ${building ? "is-building" : ""}`} aria-hidden="true"><span /><span /><span /><i /></div>{created && <p className="world-ready" role="status">Mondo accettato: {created.world_id}. È selezionato nel modulo Nuova sessione; ora puoi creare l’indagine.</p>}<form onSubmit={submit}>
    <label>Metodo del costruttore<select value={kind} onChange={e => setKind(e.target.value)}><option value="generate">Generatore World Forge</option><option value="author">Avanzato: legge AST dell’autore</option></select></label>
    {kind === 'generate' ? <label>Livello<select value={level} onChange={e => setLevel(Number(e.target.value))}>{[1, 2, 3, 4, 5].map(n => <option key={n}>{n}</option>)}</select></label> : <label>AST del mondo<textarea required maxLength={32000} rows={7} value={law} onChange={e => setLaw(e.target.value)} spellCheck={false} /></label>}
    <p className="field-hint">Livelli 1–5: struttura progressivamente più articolata, non una garanzia di difficoltà. Se scegli l’AST, usa solo nodi ammessi: non incollare codice Python o formule LaTeX.</p><details className="technical-notes"><summary>Come scrivere l’AST (avanzato)</summary><p>Ogni legge ha level, ax e ay. Un nodo const contiene op e value (numero tra −100 e 100); un nodo var contiene op e name (x, y, vx o vy). add, sub e mul usano due nodi nell’elenco args. Il livello 1 ammette solo costanti: modifica i numeri dell’esempio per partire.</p><p>Le operazioni avanzate comprendono div protetta, abs, sin, cos, tanh, norm, normalize e pow con exponent intero da 0 a 3. Il server controlla arità, livello, massimo 64 nodi e profondità 12: l’editor non sostituisce la validazione. Usa il generatore se vuoi indagare senza conoscere già la legge.</p></details><label>Budget del mondo<select value={budget} onChange={e => setBudget(Number(e.target.value))}>{[1, 2, 3, 4].map(n => <option key={n}>{n}</option>)}</select></label>
    <button className="button secondary" disabled={busy || !token}>Valida e registra mondo</button></form><p className="field-hint">Controlli numerici euristici, senza codice arbitrario. Se definisci la legge, conosci già la risposta: il mondo è escluso da Human vs AI. Il generatore usa un seed privato casuale.</p></section>
}

export function MatchView({ match, current, busy, change }: { match: Match; current: string; busy: boolean;
  change: (id: string) => Promise<void> }) {
  const humanFrozen = ['scoring_pending', 'scored', 'revealed'].includes(match.human.status)
  const humanStopped = match.human.status === 'stopped'
  return <section className="panel match-panel" aria-label="Confronto umano e agente"><span className="kicker">HUMAN VS AI / STORIE SEPARATE</span><h2>Confronto sullo stesso mondo</h2>
    <p className="session-id">ID confronto: {match.match_id}</p><p>{match.rules.experiment_budget} lanci ciascuno · massimo {match.rules.max_points} misure per lancio · {match.rules.max_turns} messaggi ciascuno. Solo esplorazione, senza modifiche o assistenza teorica.</p>
    <div className="button-row"><button className="button secondary" disabled={busy || current === match.human_session_id} onClick={() => void change(match.human_session_id)}>Indagine umana</button><button className="button secondary" disabled={busy || (!humanFrozen && !humanStopped) || current === match.agent_session_id} onClick={() => void change(match.agent_session_id)}>Indagine agente</button></div>
    <p className="field-hint">{match.complete ? 'Confronto completato: entrambe le risposte sono congelate. Le metriche restano separate.' : humanStopped ? 'Indagine umana arrestata. Apri l’indagine agente per arrestare anche quella; il reveal richiede la chiusura di entrambe.' : humanFrozen ? 'Risposta umana congelata. Puoi proseguire con l’agente; i punteggi arrivano dopo entrambe le consegne.' : 'Conduci e consegna prima l’indagine umana. L’agente non riceverà i tuoi messaggi o la tua risposta.'}</p>
    {match.complete && <div className="comparison-grid">{(['human', 'agent'] as const).map(side => <div key={side}><h3>{side === 'human' ? 'Umano' : 'Agente'}</h3><p>{match[side].observations} osservazioni · {match[side].messages} messaggi{side === 'agent' ? ` · ${match.agent.agent?.calls ?? 0} chiamate · ${match.agent.agent?.invalid_responses ?? 0} risposte invalide` : ''}</p>{match[side].scores && <ResultView scores={match[side].scores} />}</div>)}</div>}
  </section>
}
