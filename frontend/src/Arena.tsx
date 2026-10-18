import { useState, type FormEvent } from 'react'
import { arenaApi, type ArenaAgent, type ArenaBoard, type ArenaChallenge, type ArenaTrial } from './arena-api'
import { EventCard, fmt, ResultView, statusName, integrityName, dimensionName } from './view'
import type { WorldManifest } from './types'
import { useIdentity } from './Identity'

export function Arena({ worlds }: { worlds: WorldManifest[] }) {
  const identity = useIdentity()
  const staff = !identity || identity.role !== 'member'
  const admin = !identity || identity.role === 'admin'
  const availableWorlds = worlds.filter(w => !w.builder_version && (!w.integrity || ['blind_test', 'untracked'].includes(w.integrity.state)))
  const [token, setToken] = useState(identity ? 'account' : '')
  const [challenges, setChallenges] = useState<ArenaChallenge[]>([])
  const [cid, setCid] = useState('')
  const [worldId, setWorldId] = useState(availableWorlds[0]?.world_id ?? '')
  const [name, setName] = useState("First Arena challenge")
  const [agentName, setAgentName] = useState('')
  const [model, setModel] = useState('')
  const [agents, setAgents] = useState<ArenaAgent[]>([])
  const [issued, setIssued] = useState<{ token: string | null; token_id: string; agent_id: string } | null>(null)
  const [showToken, setShowToken] = useState(false)
  const [trials, setTrials] = useState<ArenaTrial[]>([])
  const [trial, setTrial] = useState<ArenaTrial | null>(null)
  const [board, setBoard] = useState<ArenaBoard | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [revealChecked, setRevealChecked] = useState(false)
  const [reveal, setReveal] = useState<unknown>(null)
  const [audit, setAudit] = useState<unknown>(null)
  const [flagReason, setFlagReason] = useState('known_law')
  const selected = challenges.find(c => c.challenge_id === cid)
  const selectedWorld = availableWorlds.some(w => w.world_id === worldId) ? worldId : availableWorlds[0]?.world_id ?? ''

  async function act(work: () => Promise<void>) {
    setBusy(true); setError('')
    try { await work() } catch (e) { setError(e instanceof Error ? e.message : "This action could not be completed.") }
    finally { setBusy(false) }
  }
  async function refresh(selectedId = cid) {
    const listing = await arenaApi.read<{ challenges: ArenaChallenge[] }>('challenges', token)
    setChallenges(listing.challenges)
    const actual = selectedId || listing.challenges[0]?.challenge_id || ''
    setCid(actual)
    const registered = await arenaApi.read<{ agents: ArenaAgent[] }>('agents', token)
    setAgents(registered.agents)
    if (actual) {
      setTrials((await arenaApi.read<{ trials: ArenaTrial[] }>(`challenges/${actual}/trials`, token)).trials)
      setBoard(await arenaApi.read<ArenaBoard>(`challenges/${actual}/leaderboard`, token))
    }
    if (trial && trial.challenge_id === actual) setTrial(await arenaApi.read<ArenaTrial>(`sessions/${trial.session_id}`, token))
    else setTrial(null)
  }
  async function trialAction(kind: string, extra: Record<string, unknown>) {
    if (!trial) return
    await arenaApi.write(`sessions/${trial.session_id}/${kind}`, { expected_version: trial.version, ...extra }, token)
    setTrial(await arenaApi.read<ArenaTrial>(`sessions/${trial.session_id}`, token))
    await refresh()
  }
  function submit(e: FormEvent, work: () => Promise<void>) { e.preventDefault(); void act(work) }

  if (!staff) return <section className="panel"><h2>Your agent in Arena</h2><p>Use the bring-your-own-agent client with your account key and the agent token linked by your administrator. Staff authorize and run each experiment. The Arena console is for operators.</p></section>

  return <div className="arena">
    <section className="panel"><span className="kicker">Arena · Integrity v1</span><h2>Zone Arena</h2>
      <p>Connect your agent to the laboratory. The agent proposes and submits; the operator approves and runs every experiment. This staff console does not call a model.</p>
      <p className="notice">Comparable challenges use the same world, test states, budgets and limits. Exploration only, with no parameter changes or theoretical hints. One trial per agent in each challenge.</p>
      <p>Private test cases are reserved for Arena. Agent scores stay hidden until closure; revealing a world retires the case. Worlds without a dataset split are diagnostic comparisons.</p>
      <form onSubmit={e => submit(e, () => refresh())}>{!identity && <label>Arena operator token<input type="password" autoComplete="off" required value={token} onChange={e => { setToken(e.target.value); setIssued(null); setShowToken(false) }} /></label>}
        <button className="button primary" disabled={busy}>Connect to Arena</button></form>
      <p className="field-hint">Tokens stay in page memory and are forgotten on reload. See docs/arena.md for the client protocol.</p>
    </section>
    {error && <p role="alert" className="error">{error} Refresh the state before repeating an action.</p>}
    <div className="setup-grid">
      <section className="panel"><h2>Challenge</h2><form onSubmit={e => submit(e, async () => {
        const created = await arenaApi.write<ArenaChallenge>('challenges', { world_id: selectedWorld, name }, token)
        await refresh(created.challenge_id)
      })}><label>Challenge name<input required maxLength={80} value={name} onChange={e => setName(e.target.value)} /></label>
        <label>Arena Forge world<select required value={selectedWorld} onChange={e => setWorldId(e.target.value)}>{availableWorlds.map((w, i) => <option key={w.world_id} value={w.world_id}>World {i + 1} · {w.experiment_budget} experiments · {integrityName(w.integrity?.state)}</option>)}</select></label>
        <button className="button secondary" disabled={busy || !token || !selectedWorld}>Create challenge</button></form>
        <label>Selected challenge<select value={cid} onChange={e => { setTrial(null); setReveal(null); setRevealChecked(false); void act(() => refresh(e.target.value)) }}><option value="">Select</option>{challenges.map(c => <option key={c.challenge_id} value={c.challenge_id}>{c.name} · {c.closed ? 'closed' : 'open'}</option>)}</select></label>
        {selected && <><details><summary>Challenge identifier</summary><code>{cid}</code></details><p>{selected.rules.experiment_budget} experiments · {selected.rules.max_messages} agent messages · up to {selected.rules.max_points} samples per experiment.</p>
          <p>Integrity: {integrityName(selected.integrity?.state)}</p>{selected.integrity?.manifest_hash && <details><summary>Technical commitments</summary><p className="session-id">Manifest to preserve before the trial: {selected.integrity.manifest_hash}<br />World commitment: {selected.integrity.commitment}</p></details>}
          <button className="button secondary" disabled={busy || selected.closed || trials.some(t => !['scored', 'stopped', 'revealed'].includes(t.status))} onClick={() => void act(async () => { await arenaApi.write(`challenges/${cid}/close`, {}, token); await refresh() })}>Close challenge</button></>}
      </section>
      <section className="panel"><h2>Agent credentials</h2><form onSubmit={e => submit(e, async () => {
        setIssued(await arenaApi.write('agents', { name: agentName, model }, token)); setShowToken(false); await refresh()
      })}><label>Agent name<input required maxLength={80} value={agentName} onChange={e => setAgentName(e.target.value)} /></label><label>Declared model<input required maxLength={80} value={model} onChange={e => setModel(e.target.value)} /></label><button className="button secondary" disabled={busy || !token}>Register agent</button></form>
        {issued && <div className="notice"><p>This credential is issued only once. Give it to your local client; never enter it in prompts or scientific messages.</p><p>Agent identifier: <code>{issued.agent_id}</code></p><label>Arena agent token<input readOnly type={showToken ? 'text' : 'password'} autoComplete="off" value={issued.token ?? ''} /></label><button className="button tiny" onClick={() => setShowToken(!showToken)}>{showToken ? "Hide token" : "Show token"}</button><button className="button tiny" onClick={() => setIssued(null)}>Forget token</button></div>}
        {agents.map(agent => <div className="arena-agent" key={agent.agent_id}><h3>{agent.name}</h3><p>{agent.model} · identity not independently verified</p><p>Account quotas: trials {agent.usage.sessions}/{agent.quotas.sessions}, requests {agent.usage.requests}/{agent.quotas.requests}, experiments {agent.usage.experiments}/{agent.quotas.experiments}; invalid {agent.usage.invalid}.</p>
          <button className="button tiny" disabled={busy} onClick={() => void act(async () => { setIssued(await arenaApi.write(`agents/${agent.agent_id}/tokens`, {}, token)); setShowToken(false); await refresh() })}>Issue a new token for {agent.name}</button>
          {agent.tokens.map((t, i) => <p key={t.token_id}>Token {i + 1} · {t.revoked ? 'revoked' : `expires ${new Date(t.expires_at * 1000).toLocaleString('en-US')}`} {!t.revoked && <button className="button tiny danger" disabled={busy} onClick={() => void act(async () => { await arenaApi.write(`tokens/${t.token_id}/revoke`, {}, token); if (issued?.token_id === t.token_id) setIssued(null); await refresh() })}>Revoke token {i + 1}</button>}</p>)}</div>)}
      </section>
    </div>
    {selected && <section className="panel"><h2>Trials and operator controls</h2><div className="button-row"><button className="button secondary" disabled={busy || !token} onClick={() => void act(() => refresh())}>Refresh Arena</button><button className="button secondary" disabled={busy || !token} onClick={() => void act(async () => setAudit(await arenaApi.read('audit', token)))}>Show audit</button></div>
      <p>Start a trial from your bring-your-own-agent client using the challenge identifier and agent token. This staff page does not send messages on the agent's behalf.</p>
      {trials.map(t => <button className="button secondary" key={t.session_id} disabled={busy} onClick={() => void act(async () => { setTrial(await arenaApi.read(`sessions/${t.session_id}`, token)); setReveal(null); setRevealChecked(false) })}>{t.account.name} · {statusName(t.status)}</button>)}
      {trial && <div><h3>{trial.account.name} · {statusName(trial.status)}</h3><details><summary>Technical identifier</summary><code>{trial.session_id}</code></details><p>{trial.executed_experiments} experiments · {trial.observations} observations · {trial.messages} messages</p>
        <p>Trial integrity: {integrityName(trial.integrity?.state)} · {trial.integrity?.eligible ? "eligible blind test" : "diagnostic or excluded"}. Flags: {trial.integrity?.flags?.map(integrityName).join(', ') || 'none'}.</p>
        <label>Contamination reason<select value={flagReason} onChange={e => setFlagReason(e.target.value)}><option value="known_law">Law already known</option><option value="operator_hint">Theoretical hint from the operator</option><option value="external_disclosure">External disclosure</option><option value="protocol_violation">Protocol violation</option></select></label><button className="button danger" disabled={busy || trial.integrity?.flags?.includes(flagReason)} onClick={() => void act(() => trialAction('integrity', { reason: flagReason }))}>Mark as contaminated · irreversible</button>
        {trial.status === 'awaiting_decision' && <div className="button-row">{(['approve', 'reject'] as const).map(action => <button className={`button ${action === 'approve' ? 'primary' : 'secondary'}`} key={action} disabled={busy} onClick={() => void act(() => trialAction('messages', { message: { type: 'operator_decision', request_id: trial.pending_request_id, action, reason: "Operational Arena decision." } }))}>{action === 'approve' ? "Approve Arena proposal" : "Reject Arena proposal"}</button>)}</div>}
        {trial.status === 'awaiting_mode' && <button className="button primary" disabled={busy} onClick={() => void act(() => trialAction('messages', { message: { type: 'execution_mode', request_id: trial.pending_request_id, mode: 'exploration' } }))}>Confirm Arena exploration</button>}
        {trial.status === 'ready_to_run' && <button className="button primary" disabled={busy} onClick={() => void act(() => trialAction('run', { request_id: trial.pending_request_id }))}>Run Arena experiment</button>}
        {trial.status === 'scoring_pending' && <button className="button primary" disabled={busy} onClick={() => void act(() => trialAction('score', {}))}>Complete Arena evaluation</button>}
        {!['scored', 'stopped', 'revealed'].includes(trial.status) && <details><summary>Stop this trial</summary><button className="button danger" disabled={busy} onClick={() => void act(() => trialAction('stop', { reason: trial.status === 'execution_started' ? 'interrupted_execution' : 'operator_stop' }))}>Confirm Arena stop</button></details>}
        {admin && selected.closed && ['scored', 'stopped'].includes(trial.status) && <><label className="check-row"><input type="checkbox" checked={revealChecked} onChange={e => setRevealChecked(e.target.checked)} />I confirm revealing the private Arena world</label><button className="button danger" disabled={busy || !revealChecked} onClick={() => void act(async () => { await trialAction('reveal', { confirm: 'reveal' }); setReveal(await arenaApi.read(`sessions/${trial.session_id}/reveal`, token)) })}>Reveal Arena world</button></>}
        {trial.scores && <ResultView scores={trial.scores} />}
        <div className="timeline">{trial.events?.map(event => <EventCard key={event.seq} event={event} events={trial.events} />)}</div>
      </div>}
    </section>}
    {board && <section className="panel"><h2>Leaderboards by dimension</h2><p>Scope: {board.comparison_scope === 'blind_test' ? 'Controlled blind test' : 'Diagnostic comparison'}. Contaminated trials keep their results and resource records, but are excluded from rankings.</p><p>This comparison applies only to this challenge. There is no combined score or overall winner. Missing metrics are excluded from the relevant ranking; tied values share a rank.</p>
      <div className="arena-boards">{Object.entries(board.dimensions).map(([dimension, rows]) => <div className="table-scroll" key={dimension}><table><caption>{dimensionName(dimension)} · lower values rank first</caption><thead><tr><th>Rank</th><th>Agent</th><th>Value</th></tr></thead><tbody>{rows.length ? rows.map(row => <tr key={row.session_id}><td>{row.rank}</td><td>{board.trials.find(t => t.session_id === row.session_id)?.account.name}</td><td>{fmt(row.value)}</td></tr>) : <tr><td colSpan={3}>No values available</td></tr>}</tbody></table></div>)}</div>
      <h3>Resources and stop states</h3><div className="table-scroll"><table><thead><tr><th>Agent</th><th>State</th><th>Observations</th><th>Experiments</th><th>API requests</th><th>Invalid</th></tr></thead><tbody>{board.trials.map(t => <tr key={t.session_id}><td>{t.account.name}</td><td>{statusName(t.status)}</td><td>{t.observations}</td><td>{t.executed_experiments}</td><td>{t.resources.agent_requests}</td><td>{t.resources.invalid_requests}</td></tr>)}</tbody></table></div><p className="field-hint">External client model calls, tokens and costs are not measured. The API request count is not a model-call count.</p>
    </section>}
    {audit !== null && <section className="panel"><h2>Arena audit · first page</h2><pre className="private-record">{JSON.stringify(audit, null, 2)}</pre></section>}
    {reveal !== null && <section className="panel"><h2>Private Arena record</h2><pre className="private-record">{JSON.stringify(reveal, null, 2)}</pre></section>}
  </div>
}
