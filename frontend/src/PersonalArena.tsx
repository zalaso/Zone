import { useEffect, useState } from 'react'
import { request } from './api'
import type { ArenaAgent, ArenaBoard, ArenaChallenge, ArenaTrial } from './arena-api'
import { EventCard, fmt, ResultView } from './view'
import { ModeGuide } from './Guide'
import { Activity, NextStep, PublicExperiment, type ActivityKind } from './LabVisuals'

export function PersonalArena({ initialSession }: { initialSession: string | null }) {
  const [agents, setAgents] = useState<ArenaAgent[]>([])
  const [challenges, setChallenges] = useState<ArenaChallenge[]>([])
  const [trials, setTrials] = useState<ArenaTrial[]>([])
  const [agent, setAgent] = useState('')
  const [challenge, setChallenge] = useState('')
  const [name, setName] = useState('Il mio agente')
  const [trial, setTrial] = useState<ArenaTrial | null>(null)
  const [busy, setBusy] = useState(false)
  const [activity, setActivity] = useState<ActivityKind>('sync')
  const [error, setError] = useState('')
  const [reason, setReason] = useState('Decisione operativa.')
  const [board, setBoard] = useState<ArenaBoard | null>(null)
  async function load(id?: string) {
    const [mine, available] = await Promise.all([
      request<{ agents: ArenaAgent[]; trials: ArenaTrial[] }>('/my/arena'),
      request<{ challenges: ArenaChallenge[] }>('/arena/challenges'),
    ])
    setAgents(mine.agents); setTrials(mine.trials); setChallenges(available.challenges)
    setAgent(current => current || mine.agents[0]?.agent_id || '')
    setChallenge(current => current || available.challenges.find(c => !c.closed)?.challenge_id || '')
    if (id) setTrial(await request<ArenaTrial>(`/my/arena/trials/${id}`))
  }
  async function act(work: () => Promise<void>) {
    setBusy(true); setError('')
    try { await work() } catch (e) { setError(e instanceof Error ? e.message : 'Operazione non riuscita.') }
    finally { setBusy(false) }
  }
  useEffect(() => { void act(() => load(initialSession ?? undefined)) }, [initialSession])
  async function write(path: string, body: unknown) {
    return request<ArenaTrial>(path, 'POST', body, undefined, { 'Idempotency-Key': crypto.randomUUID() })
  }
  async function action(kind: string, extra: Record<string, unknown> = {}) {
    setActivity(kind === 'step' ? 'model' : kind === 'run' ? 'experiment' : 'sync')
    if (!trial) return
    await write(`/my/arena/trials/${trial.session_id}/${kind}`, { expected_version: trial.version, ...extra })
    await load(trial.session_id)
  }
  const terminal = trial && ['scored', 'stopped', 'revealed'].includes(trial.status)
  return <div><ModeGuide mode="arena" />
    <section className="panel"><h2>Il tuo agente, una challenge comune</h2><p>Usa la connessione scelta in Connessioni AI oppure la baseline offline, che serve a provare il flusso. Il modello è fissato all’avvio del trial.</p><p className="notice">Arena mantiene lo stesso mondo, probe e budget per i partecipanti. Si esegue soltanto in esplorazione: niente modifiche dei parametri o suggerimenti teorici. I risultati dei test ciechi restano nascosti fino alla chiusura.</p>
      <form onSubmit={e => { e.preventDefault(); void act(async () => {
        const created = await request<{ agent_id: string }>('/my/arena/agents', 'POST', { name }); setAgent(created.agent_id); await load()
      }) }}><label>Nome del tuo agente<input required maxLength={80} value={name} onChange={e => setName(e.target.value)} /></label><button className="button secondary" disabled={busy}>Registra con il modello selezionato</button></form>
      <form onSubmit={e => { e.preventDefault(); void act(async () => {
        const created = await write('/my/arena/trials', { agent_id: agent, challenge_id: challenge }); await load(created.session_id)
      }) }}><label>Agente<select aria-label="Agente" required value={agent} onChange={e => setAgent(e.target.value)}><option value="">Seleziona un agente</option>{agents.map(a => <option key={a.agent_id} value={a.agent_id}>{a.name} · {a.model}</option>)}</select></label><label>Challenge<select aria-label="Challenge" required value={challenge} onChange={e => setChallenge(e.target.value)}><option value="">Seleziona una challenge</option>{challenges.filter(c => !c.closed).map(c => <option key={c.challenge_id} value={c.challenge_id}>{c.name} · {c.rules.experiment_budget} lanci</option>)}</select></label><button className="button primary" disabled={busy || !agent || !challenge}>Avvia trial personale</button></form>
      {!challenges.some(c => !c.closed) && <p>Non ci sono challenge aperte. Il gestore può prepararne dalla console Arena.</p>}
    </section>
    {busy && <Activity kind={activity} />}{error && <p role="alert" className="error">{error} Aggiorna lo stato prima di ripetere un’azione.</p>}
    <section className="panel"><h2>I tuoi trial</h2><button className="button secondary" disabled={busy} onClick={() => void act(() => load(trial?.session_id))}>Aggiorna stato e registro</button><div className="button-row">{trials.map(t => <button className="button secondary" disabled={busy} key={t.session_id} onClick={() => void act(() => load(t.session_id))}>{t.account.name} · {t.status}</button>)}</div>
      {trial && <><NextStep status={trial.status} managed restricted /><PublicExperiment events={trial.events ?? []} /><h3>{trial.account.name}</h3><p>{trial.status} · {trial.executed_experiments} lanci · {trial.observations} osservazioni</p><code>{trial.session_id}</code>{trial.resources?.managed_model_calls !== undefined && <p>{trial.resources.managed_model_calls}/8 chiamate · {trial.resources.invalid_model_responses ?? 0} risposte invalide. Utilizzo e impostazioni sono conservati nel registro tecnico; i costi restano quelli del provider.</p>}
        {['discovering', 'awaiting_submission'].includes(trial.status) && <button className="button primary" disabled={busy} onClick={() => void act(() => action('step'))}>Avanza agente · una chiamata</button>}
        {trial.status === 'awaiting_decision' && <div><label>Motivazione operativa<input maxLength={2000} required value={reason} onChange={e => setReason(e.target.value)} /></label><div className="button-row">{['approve', 'reject'].map(decision => <button key={decision} className={`button ${decision === 'approve' ? 'primary' : 'secondary'}`} disabled={busy || !reason.trim()} onClick={() => void act(() => action('messages', { message: { type: 'operator_decision', request_id: trial.pending_request_id, action: decision, reason } }))}>{decision === 'approve' ? 'Approva richiesta' : 'Rifiuta richiesta'}</button>)}</div></div>}
        {trial.status === 'awaiting_mode' && <button className="button primary" disabled={busy} onClick={() => void act(() => action('messages', { message: { type: 'execution_mode', request_id: trial.pending_request_id, mode: 'exploration' } }))}>Conferma esplorazione Arena</button>}
        {trial.status === 'ready_to_run' && <button className="button primary" disabled={busy} onClick={() => void act(() => action('run', { request_id: trial.pending_request_id }))}>Esegui questo esperimento</button>}
        {trial.status === 'scoring_pending' && <button className="button primary" disabled={busy} onClick={() => void act(() => action('score'))}>Completa valutazione</button>}
        {!terminal && <details><summary>Arresta il trial</summary><button className="button danger" disabled={busy} onClick={() => void act(() => action('stop', { reason: trial.status === 'execution_started' ? 'interrupted_execution' : 'operator_stop' }))}>Conferma arresto</button></details>}
        {trial.scores && <ResultView scores={trial.scores} />}
        <h3>Registro pubblico</h3><div className="timeline">{trial.events?.map(event => <EventCard key={event.seq} event={event} />)}</div>
      </>}
    </section>
    <section className="panel"><h2>Confronti delle challenge chiuse</h2><p>Ogni dimensione ha una classifica separata. Non viene calcolato un punteggio unico.</p><div className="button-row">{challenges.filter(c => c.closed).map(c => <button className="button secondary" key={c.challenge_id} disabled={busy} onClick={() => void act(async () => setBoard(await request<ArenaBoard>(`/my/arena/leaderboards/${c.challenge_id}`)))}>{c.name}</button>)}</div>{board && Object.entries(board.dimensions).map(([dimension, rows]) => <div className="table-scroll" key={dimension}><table><caption>{dimension}</caption><thead><tr><th>Rango</th><th>Agente</th><th>Valore</th></tr></thead><tbody>{rows.map(row => <tr key={row.session_id}><td>{row.rank}</td><td>{board.trials.find(t => t.session_id === row.session_id)?.account.name}</td><td>{fmt(row.value)}</td></tr>)}</tbody></table></div>)}</section>
  </div>
}
