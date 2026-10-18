import { useEffect, useState } from 'react'
import { request } from './api'
import type { ArenaAgent, ArenaBoard, ArenaChallenge, ArenaTrial } from './arena-api'
import { EventCard, fmt, ResultView, statusName, dimensionName } from './view'
import { ModeGuide } from './Guide'
import { Activity, NextStep, PublicExperiment, type ActivityKind } from './LabVisuals'

export function PersonalArena({ initialSession }: { initialSession: string | null }) {
  const [agents, setAgents] = useState<ArenaAgent[]>([])
  const [challenges, setChallenges] = useState<ArenaChallenge[]>([])
  const [trials, setTrials] = useState<ArenaTrial[]>([])
  const [agent, setAgent] = useState('')
  const [challenge, setChallenge] = useState('')
  const [name, setName] = useState("My agent")
  const [trial, setTrial] = useState<ArenaTrial | null>(null)
  const [busy, setBusy] = useState(false)
  const [activity, setActivity] = useState<ActivityKind>('sync')
  const [error, setError] = useState('')
  const [reason, setReason] = useState("Operational decision.")
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
    try { await work() } catch (e) { setError(e instanceof Error ? e.message : "This action could not be completed.") }
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
    <section className="panel"><h2>Your agent. A shared challenge.</h2><p>Use the connection selected in AI connections, or the offline baseline to try the workflow. The model is fixed when the trial starts.</p><p className="notice">Arena gives participants the same world, test states and experiment budget. Exploration only: no parameter changes or theoretical hints. Blind test results stay hidden until closure.</p>
      <form onSubmit={e => { e.preventDefault(); void act(async () => {
        const created = await request<{ agent_id: string }>('/my/arena/agents', 'POST', { name }); setAgent(created.agent_id); await load()
      }) }}><label>Your agent's name<input required maxLength={80} value={name} onChange={e => setName(e.target.value)} /></label><button className="button secondary" disabled={busy}>Register with the selected model</button></form>
      <form onSubmit={e => { e.preventDefault(); void act(async () => {
        const created = await write('/my/arena/trials', { agent_id: agent, challenge_id: challenge }); await load(created.session_id)
      }) }}><label>Agent<select aria-label={"Agent"} required value={agent} onChange={e => setAgent(e.target.value)}><option value="">Select an agent</option>{agents.map(a => <option key={a.agent_id} value={a.agent_id}>{a.name} · {a.model === 'offline-affine-v1' ? 'Offline baseline' : a.model}</option>)}</select></label><label>Challenge<select aria-label="Challenge" required value={challenge} onChange={e => setChallenge(e.target.value)}><option value="">Select a challenge</option>{challenges.filter(c => !c.closed).map(c => <option key={c.challenge_id} value={c.challenge_id}>{c.name} · {c.rules.experiment_budget} experiments</option>)}</select></label><button className="button primary" disabled={busy || !agent || !challenge}>Start your trial</button></form>
      {!challenges.some(c => !c.closed) && <p>No challenges are open. The operator can create one in the Arena staff console.</p>}
    </section>
    {busy && <Activity kind={activity} />}{error && <p role="alert" className="error">{error} Refresh the state before repeating an action.</p>}
    <section className="panel"><h2>Your trials</h2><button className="button secondary" disabled={busy} onClick={() => void act(() => load(trial?.session_id))}>Refresh status and history</button><div className="button-row">{trials.map(t => <button className="button secondary" disabled={busy} key={t.session_id} onClick={() => void act(() => load(t.session_id))}>{t.account.name} · {statusName(t.status)}</button>)}</div>
      {trial && <><NextStep status={trial.status} managed restricted /><PublicExperiment events={trial.events ?? []} /><h3>{trial.account.name}</h3><p>{statusName(trial.status)} · {trial.executed_experiments} experiments · {trial.observations} observations</p><details><summary>Technical identifier</summary><code>{trial.session_id}</code></details>{trial.resources?.managed_model_calls !== undefined && <p>{trial.resources.managed_model_calls}/8 calls · {trial.resources.invalid_model_responses ?? 0} invalid replies. Usage and settings are saved in the technical record. Model costs remain with your provider.</p>}
        {['discovering', 'awaiting_submission'].includes(trial.status) && <button className="button primary" disabled={busy} onClick={() => void act(() => action('step'))}>Ask for next step · one call</button>}
        {trial.status === 'awaiting_decision' && <div><label>Operational reason<input maxLength={2000} required value={reason} onChange={e => setReason(e.target.value)} /></label><div className="button-row">{['approve', 'reject'].map(decision => <button key={decision} className={`button ${decision === 'approve' ? 'primary' : 'secondary'}`} disabled={busy || !reason.trim()} onClick={() => void act(() => action('messages', { message: { type: 'operator_decision', request_id: trial.pending_request_id, action: decision, reason } }))}>{decision === 'approve' ? "Approve proposal" : "Reject proposal"}</button>)}</div></div>}
        {trial.status === 'awaiting_mode' && <button className="button primary" disabled={busy} onClick={() => void act(() => action('messages', { message: { type: 'execution_mode', request_id: trial.pending_request_id, mode: 'exploration' } }))}>Confirm Arena exploration</button>}
        {trial.status === 'ready_to_run' && <button className="button primary" disabled={busy} onClick={() => void act(() => action('run', { request_id: trial.pending_request_id }))}>Run this experiment</button>}
        {trial.status === 'scoring_pending' && <button className="button primary" disabled={busy} onClick={() => void act(() => action('score'))}>Complete evaluation</button>}
        {!terminal && <details><summary>Stop the trial</summary><button className="button danger" disabled={busy} onClick={() => void act(() => action('stop', { reason: trial.status === 'execution_started' ? 'interrupted_execution' : 'operator_stop' }))}>Confirm stop</button></details>}
        {trial.scores && <ResultView scores={trial.scores} />}
        <h3>Scientific history</h3><div className="timeline">{trial.events?.map(event => <EventCard key={event.seq} event={event} events={trial.events} />)}</div>
      </>}
    </section>
    <section className="panel"><h2>Closed challenge comparisons</h2><p>Each dimension has a separate ranking. No combined score is calculated.</p><div className="button-row">{challenges.filter(c => c.closed).map(c => <button className="button secondary" key={c.challenge_id} disabled={busy} onClick={() => void act(async () => setBoard(await request<ArenaBoard>(`/my/arena/leaderboards/${c.challenge_id}`)))}>{c.name}</button>)}</div>{board && Object.entries(board.dimensions).map(([dimension, rows]) => <div className="table-scroll" key={dimension}><table><caption>{dimensionName(dimension)} · lower values rank first</caption><thead><tr><th>Rank</th><th>Agent</th><th>Value</th></tr></thead><tbody>{rows.map(row => <tr key={row.session_id}><td>{row.rank}</td><td>{board.trials.find(t => t.session_id === row.session_id)?.account.name}</td><td>{fmt(row.value)}</td></tr>)}</tbody></table></div>)}</section>
  </div>
}
