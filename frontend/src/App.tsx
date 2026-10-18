import { useEffect, useMemo, useState, type FormEvent, type ReactNode } from 'react'
import { api, ApiError } from './api'
import { asExperiment, asProbes, asText, EventCard, fmt, referenceName, ResultView, statusName } from './view'
import { AgentDescription, MatchView, modes, UniverseBuilder } from './Modes'
import type { AgentInfo, Experiment, LabEvent, Match, Probe, Scores, SessionStatus, WorldManifest } from './types'
import './styles.css'
import { Arena } from './Arena'
import { ModeGuide } from './Guide'
import { Activity, ExperimentStage, NextStep, PublicExperiment, type ActivityKind } from './LabVisuals'
import { ScientificText } from './ScientificText'
import { PersonalArena } from './PersonalArena'
import { useIdentity, usePublicWorkspace } from './Identity'

const emptyExperiment: Experiment = {
  initial_position: { x: 0, y: 0 }, initial_velocity: { x: 0, y: 0 }, duration: 1, observation_interval: 0.25,
}
function newId(prefix: string) { return `${prefix}${crypto.randomUUID().replaceAll('-', '').slice(0, 10)}` }
function textList(value: string) { return value.split('\n').map(s => s.trim()).filter(Boolean) }
function validExperiment(e: Experiment) {
  const values = [e.initial_position.x, e.initial_position.y, e.initial_velocity.x, e.initial_velocity.y]
  const count = e.duration / e.observation_interval
  return values.every(v => Number.isFinite(v) && v >= -20 && v <= 20) &&
    e.duration >= 0.1 && e.duration <= 5 && e.observation_interval >= 0.05 && e.observation_interval <= 1 &&
    Number.isInteger(Math.round(count)) && Math.abs(count - Math.round(count)) < 1e-8
}

function Panel({ title, kicker, children }: { title: string; kicker?: string; children: ReactNode }) {
  return <section className="panel"><div className="panel-heading">{kicker && <span className="kicker">{kicker}</span>}<h2>{title}</h2></div>{children}</section>
}
function ExperimentFields({ value, onChange }: { value: Experiment; onChange: (value: Experiment) => void }) {
  function set(group: 'initial_position' | 'initial_velocity', axis: 'x' | 'y', number: number) {
    onChange({ ...value, [group]: { ...value[group], [axis]: number } })
  }
  return <fieldset className="field-grid"><legend>Experiment settings</legend>
    <label>Position x (m)<input type="number" min="-20" max="20" step="any" required value={value.initial_position.x} onChange={e => set('initial_position', 'x', e.target.valueAsNumber)} /></label>
    <label>Position y (m)<input type="number" min="-20" max="20" step="any" required value={value.initial_position.y} onChange={e => set('initial_position', 'y', e.target.valueAsNumber)} /></label>
    <label>Velocity x (m/s)<input type="number" min="-20" max="20" step="any" required value={value.initial_velocity.x} onChange={e => set('initial_velocity', 'x', e.target.valueAsNumber)} /></label>
    <label>Velocity y (m/s)<input type="number" min="-20" max="20" step="any" required value={value.initial_velocity.y} onChange={e => set('initial_velocity', 'y', e.target.valueAsNumber)} /></label>
    <label>Duration (s)<input type="number" min="0.1" max="5" step="any" required value={value.duration} onChange={e => onChange({ ...value, duration: e.target.valueAsNumber })} /></label>
    <label>Measurement interval (s)<input type="number" min="0.05" max="1" step="any" required value={value.observation_interval} onChange={e => onChange({ ...value, observation_interval: e.target.valueAsNumber })} /></label>
    <p className="field-hint">x is horizontal and y is vertical. There is no floor. Initial velocity sets the starting motion, not a force. Duration must be a multiple of the measurement interval. Choose 2–101 samples, including time zero.</p>
  </fieldset>
}

function PredictionForm({ experiment, hypotheses, requestId, send, busy }: {
  experiment: Experiment; hypotheses: string[]; requestId: string; send: (message: unknown) => Promise<void>; busy: boolean
}) {
  const times = useMemo(() => { const count = Math.round(experiment.duration / experiment.observation_interval); return Array.from({ length: count + 1 }, (_, i) => i * experiment.duration / count) }, [experiment])
  const [hypothesis, setHypothesis] = useState(hypotheses[0] ?? '')
  const selectedHypothesis = hypothesis || hypotheses[0] || ''
  const [predictionId] = useState(() => newId('p'))
  const [points, setPoints] = useState(() => times.map(() => ({ x: '', y: '' })))
  async function submit(e: FormEvent) {
    e.preventDefault()
    if (!selectedHypothesis || points.some(p => p.x.trim() === '' || p.y.trim() === '')) return
    await send({ type: 'prediction', prediction_id: predictionId, hypothesis_id: selectedHypothesis,
      request_id: requestId, points: times.map((t, i) => ({ t, x: Number(points[i].x), y: Number(points[i].y) })) })
  }
  return <Panel title={"Record a prediction"} kicker={"Prediction"}><p>These times come from the approved settings. Your prediction is locked before the experiment runs.</p>
    {hypotheses.length === 0 ? <p className="notice">Record a hypothesis first.</p> : <form onSubmit={submit}>
      <label>Reference hypothesis<select value={selectedHypothesis} onChange={e => setHypothesis(e.target.value)}>{hypotheses.map((id, i) => <option key={id} value={id}>Hypothesis {i + 1}</option>)}</select></label>
      <div className="table-scroll prediction-table"><table><caption>Predicted positions for this experiment</caption><thead><tr><th scope="col">t (s)</th><th scope="col">x (m)</th><th scope="col">y (m)</th></tr></thead><tbody>{times.map((t, i) => <tr key={i}><th scope="row">{fmt(t)}</th>{(['x', 'y'] as const).map(axis => <td key={axis}><label className="sr-only" htmlFor={`point-${i}-${axis}`}>{axis} at {fmt(t)} seconds</label><input id={`point-${i}-${axis}`} type="number" step="any" min="-1000000" max="1000000" required value={points[i]?.[axis] ?? ''} onChange={e => setPoints(current => current.map((p, j) => j === i ? { ...p, [axis]: e.target.value } : p))} /></td>)}</tr>)}</tbody></table></div>
      <button className="button primary" disabled={busy}>Preregister prediction</button>
    </form>}
  </Panel>
}

function SubmissionForm({ probes, send, busy }: { probes: Probe[]; send: (submission: unknown) => Promise<void>; busy: boolean }) {
  const [rows, setRows] = useState(() => probes.map(() => ({ ax: '', ay: '', sigma: '' })))
  const [law, setLaw] = useState('')
  const withSigma = rows.some(row => row.sigma.trim() !== '')
  async function submit(e: FormEvent) {
    e.preventDefault()
    if (rows.some(row => row.ax.trim() === '' || row.ay.trim() === '') || (withSigma && rows.some(row => row.sigma.trim() === ''))) return
    const submission: Record<string, unknown> = { predictions: probes.map((probe, i) => ({ probe_id: probe.probe_id, ax: Number(rows[i].ax), ay: Number(rows[i].ay) })) }
    if (withSigma) submission.uncertainty_sigma = rows.map(row => Number(row.sigma))
    if (law.trim()) submission.law_ast_json = law.trim()
    await send(submission)
  }
  return <Panel title={"Predict new states"} kicker={"Final test"}><p>This final test uses new states and does not run another experiment. Acceleration describes how velocity changes each second. Enter horizontal acceleration ax and vertical acceleration ay for each state. Uncertainty σ and a candidate AST law are optional. The browser does not execute formulas entered here.</p>
    <form onSubmit={submit}><div className="table-scroll"><table><caption>Public test states · acceleration in m/s²</caption><thead><tr><th scope="col">State</th><th scope="col">x, y</th><th scope="col">vx, vy</th><th scope="col">ax</th><th scope="col">ay</th><th scope="col">Optional σ</th></tr></thead><tbody>{probes.map((probe, i) => <tr key={probe.probe_id}><th scope="row">State {i + 1}<small>{probe.category === 'interpolation' ? 'Inside the domain' : 'Outside the domain'}</small></th><td>{fmt(probe.x)}, {fmt(probe.y)}</td><td>{fmt(probe.vx)}, {fmt(probe.vy)}</td>{(['ax', 'ay', 'sigma'] as const).map(axis => <td key={axis}><label className="sr-only" htmlFor={`${probe.probe_id}-${axis}`}>{axis} for state {i + 1}</label><input id={`${probe.probe_id}-${axis}`} type="number" step="any" required={axis !== 'sigma' || withSigma} min={axis === 'sigma' ? 0.001 : -1000000} max={axis === 'sigma' ? 1000 : 1000000} value={rows[i]?.[axis] ?? ''} onChange={e => setRows(current => current.map((row, j) => j === i ? { ...row, [axis]: e.target.value } : row))} /></td>)}</tr>)}</tbody></table></div>
      <label>Candidate AST law as JSON (optional)<textarea value={law} rows={4} onChange={e => setLaw(e.target.value)} placeholder={"Use only the documented AST format. Leave blank to evaluate numerical predictions alone."} /></label>
      <button className="button primary" disabled={busy}>Submit predictions</button></form>
  </Panel>
}

export default function App() {
  const identity = useIdentity()
  const publicWorkspace = usePublicWorkspace()
  const availableModes = modes.filter(([id]) => id !== 'build_universe' || !identity || identity.role === 'admin' || publicWorkspace)
  const [arenaOpen, setArenaOpen] = useState(false)
  const [arenaSession, setArenaSession] = useState<string | null>(null)
  const [worlds, setWorlds] = useState<WorldManifest[]>([])
  const [worldId, setWorldId] = useState('')
  const [mode, setMode] = useState('scientist')
  const [setupOpen, setSetupOpen] = useState(true)
  const [configuredAgent, setConfiguredAgent] = useState<AgentInfo | null>(null)
  const [dailyLabel, setDailyLabel] = useState('')
  const [match, setMatch] = useState<Match | null>(null)
  const [matchInput, setMatchInput] = useState('')
  const [humanToken, setHumanToken] = useState('')
  const [localOperatorToken, setOperatorToken] = useState('')
  const operatorToken = identity ? 'account' : localOperatorToken
  const [localAgentToken, setAgentToken] = useState('')
  const agentToken = identity ? 'account' : localAgentToken
  const [showAgentToken, setShowAgentToken] = useState(false)
  const [sessionInput, setSessionInput] = useState('')
  const [sessionId, setSessionId] = useState('')
  const [status, setStatus] = useState<SessionStatus | null>(null)
  const [events, setEvents] = useState<LabEvent[]>([])
  const [scores, setScores] = useState<Scores | null>(null)
  const [reveal, setReveal] = useState<unknown>(null)
  const [revealChecked, setRevealChecked] = useState(false)
  const [busy, setBusy] = useState(false)
  const [activity, setActivity] = useState<ActivityKind>('sync')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [replayTo, setReplayTo] = useState<number | null>(null)
  const [experiment, setExperiment] = useState<Experiment>(emptyExperiment)
  const [purpose, setPurpose] = useState('')
  const [decision, setDecision] = useState<'approve' | 'modify' | 'reject'>('approve')
  const [reason, setReason] = useState('')
  const [modified, setModified] = useState<Experiment>(emptyExperiment)
  const [hypothesisId, setHypothesisId] = useState(() => newId('h'))
  const [hypothesisText, setHypothesisText] = useState('')
  const [uncertainties, setUncertainties] = useState('')
  const [question, setQuestion] = useState('')
  const [questionPurpose, setQuestionPurpose] = useState('')
  const [answer, setAnswer] = useState('')
  const [summary, setSummary] = useState('')
  const [limits, setLimits] = useState('')
  const [alternatives, setAlternatives] = useState('')
  const [finalHypothesis, setFinalHypothesis] = useState('')
  const [evidence, setEvidence] = useState<string[]>([])

  function resetDrafts() {
    setDecision('approve'); setReason(''); setModified(emptyExperiment); setExperiment(emptyExperiment); setPurpose('')
    setHypothesisId(newId('h')); setHypothesisText(''); setUncertainties(''); setQuestion(''); setQuestionPurpose(''); setAnswer('')
    setSummary(''); setLimits(''); setAlternatives(''); setFinalHypothesis(''); setEvidence([]); setRevealChecked(false); setShowAgentToken(false)
  }

  useEffect(() => { api.worlds().then(data => { setWorlds(data); setWorldId(data[0]?.world_id ?? '') }).catch(e => setError(e.message)) }, [])
  useEffect(() => { api.modes().then(data => setConfiguredAgent(data.agent)).catch(e => setError(e.message)) }, [])
  async function refresh(id = sessionId) {
    const [nextStatus, nextEvents] = await Promise.all([api.status(id), api.events(id)])
    setStatus(nextStatus); setEvents(nextEvents)
    setMatch(nextStatus.match_id ? await api.match(nextStatus.match_id) : null)
    if (nextStatus.result_available) setScores(await api.result(id))
    else setScores(null)
    return { nextStatus, nextEvents }
  }
  async function action(work: () => Promise<unknown>, success: string, kind: ActivityKind = 'sync') {
    setActivity(kind); setBusy(true); setError(''); setNotice('')
    try { await work(); setNotice(success) }
    catch (e) {
      const err = e as Error
      setError(err instanceof ApiError && err.status === 409 ? `${err.message} The state has changed. Review it before trying again.` : err.message)
      if (sessionId) try { await refresh() } catch { /* Keep the original error. */ }
    } finally { setBusy(false) }
  }
  async function create(e: FormEvent) {
    e.preventDefault()
    await action(async () => {
      let created: SessionStatus & { agent_token?: string | null }
      if (mode === 'human_vs_ai') {
        const paired = await api.createMatch(worldId, operatorToken)
        setHumanToken(identity ? '' : paired.human_agent_token); setMatchInput(paired.match_id)
        created = { ...paired.human, agent_token: paired.human_agent_token }
      } else created = await api.create(worldId, operatorToken, mode === 'build_universe' ? 'scientist' : mode)
      setSessionId(created.session_id); setSessionInput(created.session_id); setAgentToken(identity ? '' : created.agent_token ?? '')
      resetDrafts()
      setReplayTo(null); setReveal(null)
      await refresh(created.session_id); setSetupOpen(false)
    }, mode === 'watch_agent' ? "Investigation created. Ask the agent for a step when you are ready." : identity ? "Investigation created and saved to your account." : "Investigation created. Save the agent token: it is shown only once.")
  }
  async function open(e: FormEvent) {
    e.preventDefault()
    if (!/^[0-9a-f]{32}$/.test(sessionInput.trim())) { setError("Enter a valid investigation identifier."); return }
    await action(async () => {
      await refresh(sessionInput.trim()); setSetupOpen(false)
      resetDrafts()
      setSessionId(sessionInput.trim()); setAgentToken(''); setShowAgentToken(false); setReplayTo(null); setReveal(null)
    }, identity ? "Investigation opened with your account permissions." : "History loaded. Enter your tokens to continue the investigation.")
  }
  async function send(message: unknown, role: 'agent' | 'operator' = 'agent') {
    if (!status) return
    await action(async () => { await api.message(sessionId, status.version, message, role === 'agent' ? agentToken : operatorToken); await refresh() }, "Saved to the investigation history.")
  }
  function registerWorld(world: WorldManifest) {
    setWorlds(current => [...current.filter(item => item.world_id !== world.world_id), world]); setWorldId(world.world_id)
  }
  async function selectMode(value: string) {
    setMode(value); setSetupOpen(true)
    if (value === 'world_of_day') await action(async () => {
      const data = await api.daily(); registerWorld(data.world); setDailyLabel(`${data.day} · ${data.timezone}`)
    }, "Today's world is selected.")
  }
  async function switchParticipant(id: string) {
    await action(async () => {
      await refresh(id); setSessionId(id); setSessionInput(id)
      resetDrafts()
      setAgentToken(id === match?.human_session_id ? humanToken : '')
      setReplayTo(null); setReveal(null)
    }, "Participant selected. Their separate history is loaded.")
  }
  const pending = events.findLast(event => event.message.type === 'experiment_request' && event.message.request_id === status?.pending_request_id)
  const pendingExperiment = asExperiment(pending?.message.experiment)
  const modification = events.findLast(event => event.message.type === 'operator_decision' && event.message.request_id === status?.pending_request_id && event.message.action === 'modify')
  const approvedExperiment = asExperiment(modification?.message.modified_experiment) ?? pendingExperiment
  const hypotheses = events.filter(e => e.message.type === 'hypothesis').map(e => asText(e.message.hypothesis_id))
  const observations = events.filter(e => e.message.type === 'observation' && e.message.status === 'ok').map(e => asText(e.message.request_id))
  const questionEvent = events.findLast(e => e.message.type === 'operator_question' && e.message.question_id === status?.pending_question_id)
  const challenge = events.findLast(e => e.message.type === 'probe_challenge')
  const probes = asProbes(challenge?.message.probes)
  const visibleEvents = replayTo === null ? events : events.filter(e => e.seq <= replayTo)
  const canInvestigate = status && !['awaiting_submission', 'scoring_pending', 'scored', 'stopped', 'revealed', 'execution_started'].includes(status.status)
  useEffect(() => {
    const navigate = (event: Event) => {
      const selected = (event as CustomEvent<string>).detail
      setArenaOpen(selected === 'arena')
      if (selected !== 'arena' && modes.some(item => item[0] === selected)) void selectMode(selected)
    }
    const reopen = (event: Event) => {
      const { id, mode: storedMode } = (event as CustomEvent<{ id: string; mode: string }>).detail
      if (!/^[0-9a-f]{32}$/.test(id)) return
      setSetupOpen(false)
      if (storedMode === 'arena') { setArenaOpen(true); setArenaSession(id); return }
      setArenaOpen(false)
      void action(async () => { await refresh(id); resetDrafts(); setSessionId(id); setSessionInput(id); setReveal(null); setReplayTo(null) }, "Investigation reopened.")
    }
    const changed = () => { void api.modes().then(data => setConfiguredAgent(data.agent)).catch(e => setError(e.message)) }
    window.addEventListener('zone-select-mode', navigate)
    window.addEventListener('zone-open-session', reopen)
    window.addEventListener('zone-connections-changed', changed)
    return () => { window.removeEventListener('zone-select-mode', navigate); window.removeEventListener('zone-open-session', reopen); window.removeEventListener('zone-connections-changed', changed) }
  })

  return <div className="app-shell"><header className="topbar"><a className="brand" href="#top" aria-label={"Zone home"}><span className="brand-mark" aria-hidden="true">Z<span>·</span></span><span>ZONE <small>Laboratory</small></span></a><span className="topbar-note">{identity ? `Account ${identity.handle}` : "Local session"}</span><nav className="button-row" aria-label={"Zone workspace"}><button className="button tiny" aria-pressed={!arenaOpen} onClick={() => setArenaOpen(false)}>Laboratory</button><button className="button tiny" aria-pressed={arenaOpen} onClick={() => setArenaOpen(true)}>Zone Arena</button></nav></header>
    <main id="top">{publicWorkspace ? <section className="page-heading"><h1>{arenaOpen ? 'Zone Arena' : modes.find(item => item[0] === (!setupOpen && status?.mode ? status.mode : mode))?.[1] ?? "Your laboratory"}</h1><p>{status ? "Follow the next step below. Every measurement stays in the history." : "Choose a world and start an investigation. Its law stays hidden until you finish."}</p></section> : <section className="intro"><div><span className="eyebrow">Discover through experiments</span><h1>Discover the rules.<br /><em>Show the evidence.</em></h1><p>Investigate together as agent and operator. Every proposal, decision, measurement and prediction enters the public scientific history.</p></div><div className="intro-index" aria-hidden="true"><span>Observe<br />Form a hypothesis<br />Test it</span></div></section>}
      {arenaOpen ? (publicWorkspace ? <><PersonalArena initialSession={arenaSession} />{identity && identity.role !== 'member' && <details className="panel"><summary>Arena staff console</summary><Arena worlds={worlds} /></details>}</> : <Arena worlds={worlds} />) : <><ModeGuide mode={!setupOpen && status?.mode ? status.mode : mode} expanded={setupOpen} /><section className="session-setup"><button type="button" className="setup-toggle" aria-expanded={setupOpen} aria-controls="session-configuration" onClick={() => setSetupOpen(value => !value)}><span aria-hidden="true">{setupOpen ? "▾" : "▸"}</span> New investigation and settings</button><div id="session-configuration" hidden={!setupOpen}><div className="setup-grid"><Panel title={"New investigation"} kicker={"Setup"}><form onSubmit={create}><label>Mode<select aria-label={"Mode"} value={mode} onChange={e => void selectMode(e.target.value)}>{availableModes.map(([id, name]) => <option key={id} value={id}>{name}</option>)}</select></label><p className="field-hint">{modes.find(item => item[0] === mode)?.[2]}</p>{['watch_agent', 'human_vs_ai'].includes(mode) && configuredAgent && <AgentDescription agent={configuredAgent} />}{mode === 'world_of_day' && <p className="field-hint">{dailyLabel}</p>}<label>Available world<select value={worldId} onChange={e => setWorldId(e.target.value)} required disabled={mode === 'world_of_day'}>{worlds.map((w, i) => <option key={w.world_id} value={w.world_id}>World {i + 1} · Level {w.level ?? '—'} · {w.experiment_budget} experiments</option>)}</select></label>{!identity && <label>Operator token<input type="password" autoComplete="off" value={operatorToken} onChange={e => setOperatorToken(e.target.value)} required placeholder={"Enter ZONE_OPERATOR_TOKEN"} /></label>}<button className="button primary" disabled={busy || !worldId}>Create investigation <span aria-hidden="true">↗</span></button></form><p className="field-hint">{identity ? "Your account grants access to your investigations." : "The token stays in page memory and is not saved in browser storage."}</p></Panel>
        <details className="reopen-panel"><summary>Open an investigation by identifier (advanced)</summary><Panel title={"Open a history"} kicker={"Existing investigation"}><form onSubmit={open}><label>Investigation identifier<input value={sessionInput} onChange={e => setSessionInput(e.target.value)} placeholder={"32 hexadecimal characters"} required /></label><button className="button secondary" disabled={busy}>Open investigation</button></form><p className="field-hint">{identity ? "The agent can read the scientific history. Only its owner and authorized staff can open it on the site." : "The scientific history can be read without a token in legacy mode. Continuing requires the original tokens."}</p><div className="divider" /><form onSubmit={e => { e.preventDefault(); if (!/^[0-9a-f]{32}$/.test(matchInput.trim())) { setError("Enter a valid comparison identifier."); return } void action(async () => { const paired = await api.match(matchInput.trim()); await refresh(paired.human_session_id); resetDrafts(); setSetupOpen(false); setSessionId(paired.human_session_id); setSessionInput(paired.human_session_id); setAgentToken(''); setHumanToken(''); setReveal(null); setReplayTo(null) }, identity ? "Comparison reopened." : "Comparison reopened. Enter the human participant's token to continue.") }}><label>Comparison identifier<input value={matchInput} onChange={e => setMatchInput(e.target.value)} required /></label><button className="button secondary" disabled={busy}>Open comparison</button></form></Panel></details>{mode === 'build_universe' && <UniverseBuilder token={operatorToken} busy={busy} action={action} ready={registerWorld} />}</div></div></section>
      {busy && <Activity kind={activity} />}<div className="feedback" role="status" aria-live="polite">{error && <p className="error">{error}</p>}{notice && <p className="notice">{notice}</p>}</div>
      {status && !setupOpen && <>{match && <MatchView match={match} current={sessionId} busy={busy} change={switchParticipant} />}<section className="session-bar" aria-label={"Investigation status"} data-session-id={sessionId}><div><span className="kicker">Investigation</span><strong>{modes.find(item => item[0] === status.mode)?.[1] ?? 'Investigation'}</strong></div><div><span className="kicker">Status</span><strong>{statusName(status.status)}</strong></div><div><span className="kicker">Experiments</span><strong>{status.executed_experiments} / {status.executed_experiments + status.remaining_experiments}</strong></div><button className="button ghost" disabled={busy} onClick={() => void action(() => refresh(), "History updated.")}>Refresh</button></section>
        <details className="technical-notes"><summary>Technical identifiers</summary><p>Investigation: <code>{sessionId}</code></p></details><NextStep status={status.status} managed={status.managed_agent} restricted={!!match} /><PublicExperiment events={visibleEvents} /><div className="workspace"><div className="workflow">
          {!identity && !status.managed_agent && <Panel title={"Investigation credentials"} kicker={"Local access"}><label>Agent token<input type={showAgentToken ? 'text' : 'password'} autoComplete="off" value={agentToken} onChange={e => { setAgentToken(e.target.value); if (status.participant === 'human') setHumanToken(e.target.value) }} placeholder={"Token issued when the investigation was created"} /></label><div className="button-row credential-actions"><button type="button" className="button tiny" onClick={() => setShowAgentToken(value => !value)}>{showAgentToken ? "Hide token" : "Show token"}</button><button type="button" className="button tiny" disabled={!agentToken} onClick={() => void navigator.clipboard.writeText(agentToken).then(() => setNotice("Agent token copied.")).catch(() => setError("Copy unavailable. Select the token manually."))}>Copy agent token</button></div><p className="field-hint">An agent can propose experiments and conclude. Only the operator can approve and run an experiment. Tokens must be re-entered after reopening; they are not stored in the browser.</p></Panel>}
          {status.managed_agent && status.agent && <Panel title={"Agent step"} kicker={"Agent"}><AgentDescription agent={status.agent} /><p>{status.agent.calls} / {status.agent.settings.max_calls} calls · {status.agent.turns} / {status.agent.settings.max_turns} turns · {status.agent.invalid_responses} invalid replies.</p><p>One step records one message. Each experiment still requires your decision, execution mode and explicit run command.</p><button className="button primary" disabled={busy || !operatorToken || !['discovering', 'awaiting_prediction', 'awaiting_submission'].includes(status.status) || (status.agent.calls ?? 0) >= status.agent.settings.max_calls || (status.agent.turns ?? 0) >= status.agent.settings.max_turns || (!!match && !['scoring_pending', 'scored', 'revealed'].includes(match.human.status))} onClick={() => void action(async () => { await api.step(sessionId, status.version, operatorToken); await refresh() }, "Agent message saved. No experiment was run automatically.", 'model')}>Ask for next step</button></Panel>}
          {status.status === 'awaiting_answer' && <Panel title={"Answer the question"} kicker={"Operator"}><blockquote>{asText(questionEvent?.message.question)}</blockquote><p className="muted">Purpose: {asText(questionEvent?.message.purpose)}</p><form onSubmit={e => { e.preventDefault(); void send({ type: 'operator_answer', question_id: status.pending_question_id, answer }, 'operator').then(() => setAnswer('')) }}><label>Answer<textarea required maxLength={2000} value={answer} onChange={e => setAnswer(e.target.value)} /></label><button className="button primary" disabled={busy || !operatorToken}>Save answer</button></form></Panel>}
          {canInvestigate && status.status !== 'awaiting_answer' && <>
            {!status.managed_agent && !status.pending_request_id && status.remaining_experiments > 0 && <Panel title={"Propose an experiment"} kicker={"Proposal"}><form onSubmit={e => { e.preventDefault(); if (!validExperiment(experiment)) { setError("Check the allowed ranges. Duration must be a multiple of the measurement interval."); return } void send({ type: 'experiment_request', request_id: newId('e'), purpose, experiment }).then(() => setPurpose('')) }}><label>Experiment purpose<textarea required maxLength={2000} value={purpose} onChange={e => setPurpose(e.target.value)} placeholder={"What hypothesis or behavior do you want to investigate?"} /></label><ExperimentFields value={experiment} onChange={setExperiment} /><details className="preview-toggle"><summary>Preview initial position and velocity</summary><ExperimentStage experiment={experiment} label={"Your proposed initial conditions"} /></details><button className="button primary" disabled={busy || !agentToken}>Submit proposal</button></form></Panel>}
            {status.status === 'awaiting_decision' && pendingExperiment && <Panel title={"Review the proposal"} kicker={"Your decision"}><p className="lead"><ScientificText text={asText(pending?.message.purpose)} /></p><p className="muted">{referenceName(events, 'experiment_request', status.pending_request_id)}. No experiment runs without a decision and a separate run command.</p><form onSubmit={e => { e.preventDefault(); if (decision === 'modify' && !validExperiment(modified)) { setError("Check the modified experiment settings."); return } void send({ type: 'operator_decision', request_id: status.pending_request_id, action: decision, reason, ...(decision === 'modify' ? { modified_experiment: modified } : {}) }, 'operator') }}><fieldset className="choice-group"><legend>Your decision</legend>{(match ? ['approve'] as const : ['approve', 'modify', 'reject'] as const).map(choice => <label key={choice} className="choice"><input type="radio" name="decision" value={choice} checked={decision === choice} onChange={() => { setDecision(choice); if (choice === 'modify') setModified(pendingExperiment) }} /><span>{choice === 'approve' ? "Approve" : choice === 'modify' ? "Modify" : "Reject"}</span></label>)}</fieldset>{decision === 'modify' && !match && <ExperimentFields value={modified} onChange={setModified} />}<label>Reason<input required maxLength={2000} value={reason} onChange={e => setReason(e.target.value)} placeholder={"Why did you choose this decision?"} /></label><button className="button primary" disabled={busy || !operatorToken}>Save decision</button></form></Panel>}
            {status.status === 'awaiting_mode' && <Panel title={"Choose an execution mode"} kicker={"Operator"}><p>The approved settings are in the history. Verification requires predicted positions to be recorded before the experiment runs.</p><div className="button-row"><button className="button secondary" disabled={busy || !operatorToken} onClick={() => void send({ type: 'execution_mode', request_id: status.pending_request_id, mode: 'exploration' }, 'operator')}>Exploration</button>{!match && <button className="button primary" disabled={busy || !operatorToken} onClick={() => void send({ type: 'execution_mode', request_id: status.pending_request_id, mode: 'verification' }, 'operator')}>Verification with a prediction</button>}</div></Panel>}
            {!status.managed_agent && status.status === 'awaiting_prediction' && approvedExperiment && <PredictionForm key={`${status.pending_request_id}:${JSON.stringify(approvedExperiment)}`} experiment={approvedExperiment} hypotheses={hypotheses} requestId={status.pending_request_id ?? ''} send={message => send(message)} busy={busy || !agentToken} />}
            {status.status === 'ready_to_run' && <Panel title={"Run the experiment"} kicker={"Operator"}><p><strong>{referenceName(events, 'experiment_request', status.pending_request_id)}</strong> is ready. Running uses one experiment from your budget, even if the trajectory fails.</p><button className="button primary" disabled={busy || !operatorToken} onClick={() => void action(async () => { await api.run(sessionId, status.version, status.pending_request_id ?? '', operatorToken); await refresh() }, "Experiment completed. Measurements saved.", 'experiment')}>Run experiment</button></Panel>}
            {!status.managed_agent && <details className="research-notes" open={status.status === "awaiting_prediction" && hypotheses.length === 0}><summary>Record a hypothesis or ask a question</summary><Panel title={"Hypotheses and questions"} kicker="Agent"><p>Record a new hypothesis after reviewing the measurements, or ask the operator a question.</p><form onSubmit={e => { e.preventDefault(); void send({ type: 'hypothesis', hypothesis_id: hypothesisId, statement: hypothesisText, uncertainties: textList(uncertainties), evidence }).then(() => { setHypothesisId(newId('h')); setHypothesisText('') }) }}><p className="field-hint">Write a tentative explanation and include uncertainties. For formulas, put LaTeX between dollar signs. Formulas are displayed, never executed.</p><label>Hypothesis<textarea required maxLength={2000} value={hypothesisText} onChange={e => setHypothesisText(e.target.value)} /></label><div className="formula-preview"><strong>Hypothesis preview</strong><p><ScientificText text={hypothesisText} /></p></div><label>Uncertainties (one per line)<textarea value={uncertainties} onChange={e => setUncertainties(e.target.value)} /></label><EvidenceChoices observations={observations} selected={evidence} change={setEvidence} /><button className="button secondary" disabled={busy || !agentToken}>Save hypothesis</button></form>{!match && <><div className="divider" /><form onSubmit={e => { e.preventDefault(); void send({ type: 'operator_question', question_id: newId('q'), question, purpose: questionPurpose }).then(() => { setQuestion(''); setQuestionPurpose('') }) }}><label>Question<textarea required maxLength={2000} value={question} onChange={e => setQuestion(e.target.value)} /></label><label>Question purpose<input required maxLength={2000} value={questionPurpose} onChange={e => setQuestionPurpose(e.target.value)} /></label><button className="button secondary" disabled={busy || !agentToken}>Ask the operator</button></form></>}</Panel></details>}
            {!status.managed_agent && <details className="research-notes"><summary>Conclude and take the final test</summary><Panel title={"Conclude the investigation"} kicker={"Conclusion"}><p>You can conclude that the information is insufficient. New test states become available only after your conclusion.</p><form onSubmit={e => { e.preventDefault(); void send({ type: 'conclusion', final_hypothesis_id: finalHypothesis || null, summary, evidence, limits: textList(limits), alternatives: textList(alternatives) }) }}><label>Final hypothesis<select value={finalHypothesis} onChange={e => setFinalHypothesis(e.target.value)}><option value="">None: insufficient evidence</option>{hypotheses.map((id, i) => <option key={id} value={id}>Hypothesis {i + 1}</option>)}</select></label><label>Conclusion<textarea required maxLength={2000} value={summary} onChange={e => setSummary(e.target.value)} /></label><EvidenceChoices observations={observations} selected={evidence} change={setEvidence} /><label>Limits (at least one, one per line)<textarea required value={limits} onChange={e => setLimits(e.target.value)} /></label><label>Plausible alternatives (one per line)<textarea value={alternatives} onChange={e => setAlternatives(e.target.value)} /></label><button className="button secondary" disabled={busy || !agentToken || !textList(limits).length}>Save conclusion</button></form></Panel></details>}
          </>}
          {!status.managed_agent && status.status === 'awaiting_submission' && <SubmissionForm key={sessionId} probes={probes} busy={busy || !agentToken} send={submission => action(async () => { await api.submit(sessionId, status.version, submission, agentToken); await refresh() }, "Predictions submitted for evaluation.")} />}
          {status.status === 'scoring_pending' && <Panel title={"Complete the evaluation"} kicker={"Operator"}><p>The submitted predictions are already locked. {match && !match.complete ? "Results become available after both participants have submitted." : "Resume scoring only. No experiment will be repeated."}</p><button className="button primary" disabled={busy || !operatorToken || (!!match && !['scoring_pending', 'scored', 'revealed'].includes(match.agent.status))} onClick={() => void action(async () => { await api.score(sessionId, status.version, operatorToken); await refresh() }, "Evaluation completed.")}>Calculate results</button></Panel>}
          {scores && <Panel title={"Results"} kicker={"Evaluation"}><p>Lower numerical errors mean better predictions on the evaluated states. Interpolation tests states inside the allowed domain; extrapolation tests states outside it. Metrics stay separate. A candidate AST law is optional, and any reported equivalence applies only to the private evaluation grid.</p><ResultView scores={scores} /></Panel>}
          {(!identity || identity.role === 'admin') && (status.status === 'scored' || status.status === 'stopped') && <Panel title={"Reveal the world"} kicker={"Operator · irreversible"}><p>Revealing displays the private law and audit on this page. Do this only after finishing the evaluation.</p><label className="check-row"><input type="checkbox" checked={revealChecked} onChange={e => setRevealChecked(e.target.checked)} />I confirm that I want to reveal the private world</label><button className="button danger" disabled={busy || !operatorToken || !revealChecked || (!!match && ![match.human.status, match.agent.status].every(s => ['scored', 'stopped', 'revealed'].includes(s)))} onClick={() => void action(async () => { const data = await api.reveal(sessionId, status.version, operatorToken); setReveal(data); await refresh() }, "World revealed.")}>Reveal world</button></Panel>}
          {reveal !== null && <Panel title={"Private record"} kicker={"Operator only"}><pre className="private-record">{JSON.stringify(reveal, null, 2)}</pre></Panel>}
          {status.status !== 'scored' && status.status !== 'stopped' && status.status !== 'revealed' && <details className="stop-area"><summary>Stop the investigation</summary><p>Stopping does not invent a conclusion. An interrupted experiment will not be run again.</p><button className="button danger" disabled={busy || !operatorToken} onClick={() => void action(async () => { await api.stop(sessionId, status.version, status.status === 'execution_started' ? 'interrupted_execution' : 'operator_stop', operatorToken); await refresh() }, "Investigation stopped.")}>Confirm stop</button></details>}
        </div><aside className="replay"><div className="replay-heading"><span className="kicker">Scientific history</span><h2>Replay <span>{visibleEvents.length}/{events.length}</span></h2><p>Follow the recorded sequence. Moving back shows only information available at that point.</p><label>History up to this event <input aria-label={"History up to this event"} type="range" min="1" max={Math.max(1, events.length)} value={replayTo ?? Math.max(1, events.length)} onChange={e => setReplayTo(Number(e.target.value))} /></label><div className="button-row"><button className="button tiny" disabled={events.length < 2} onClick={() => setReplayTo(Math.max(1, (replayTo ?? events.length) - 1))}>Previous event</button><button className="button tiny" disabled={replayTo === null} onClick={() => setReplayTo(null)}>All events</button></div></div><div className="timeline">{visibleEvents.map(event => <EventCard key={event.seq} event={event} events={visibleEvents} />)}</div></aside></div>
      </>}
      </>}
    </main><footer className="footer"><span>Zone · local laboratory</span><span>Public messages and private data kept separate</span></footer></div>
}

function EvidenceChoices({ observations, selected, change }: { observations: string[]; selected: string[]; change: (ids: string[]) => void }) {
  return <fieldset className="evidence"><legend>Supporting measurements</legend>{observations.length ? observations.map((id, i) => <label key={id} className="check-row"><input type="checkbox" checked={selected.includes(id)} onChange={e => change(e.target.checked ? [...selected, id] : selected.filter(item => item !== id))} />Measurement set {i + 1}</label>) : <p className="field-hint">No successful measurements are available yet.</p>}</fieldset>
}
