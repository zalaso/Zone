import { useEffect, useMemo, useState, type FormEvent, type ReactNode } from 'react'
import { api, ApiError } from './api'
import { asExperiment, asProbes, asText, EventCard, fmt, ResultView } from './view'
import { AgentDescription, MatchView, modes, UniverseBuilder } from './Modes'
import type { AgentInfo, Experiment, LabEvent, Match, Probe, Scores, SessionStatus, WorldManifest } from './types'
import './styles.css'

const emptyExperiment: Experiment = {
  initial_position: { x: 0, y: 0 }, initial_velocity: { x: 0, y: 0 }, duration: 1, observation_interval: 0.25,
}
const statusLabels: Record<string, string> = {
  discovering: 'Indagine aperta', awaiting_decision: 'Decisione richiesta', awaiting_mode: 'Scegli modalità',
  awaiting_prediction: 'Previsione richiesta', ready_to_run: 'Pronto per il lancio',
  execution_started: 'Lancio interrotto', awaiting_answer: 'Risposta richiesta',
  awaiting_submission: 'Challenge disponibile', scoring_pending: 'Valutazione in attesa',
  scored: 'Risultato disponibile', stopped: 'Indagine arrestata', revealed: 'Mondo rivelato',
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
  return <fieldset className="field-grid"><legend>Parametri dell’esperimento</legend>
    <label>Posizione x (m)<input type="number" min="-20" max="20" step="any" required value={value.initial_position.x} onChange={e => set('initial_position', 'x', e.target.valueAsNumber)} /></label>
    <label>Posizione y (m)<input type="number" min="-20" max="20" step="any" required value={value.initial_position.y} onChange={e => set('initial_position', 'y', e.target.valueAsNumber)} /></label>
    <label>Velocità x (m/s)<input type="number" min="-20" max="20" step="any" required value={value.initial_velocity.x} onChange={e => set('initial_velocity', 'x', e.target.valueAsNumber)} /></label>
    <label>Velocità y (m/s)<input type="number" min="-20" max="20" step="any" required value={value.initial_velocity.y} onChange={e => set('initial_velocity', 'y', e.target.valueAsNumber)} /></label>
    <label>Durata (s)<input type="number" min="0.1" max="5" step="any" required value={value.duration} onChange={e => onChange({ ...value, duration: e.target.valueAsNumber })} /></label>
    <label>Intervallo (s)<input type="number" min="0.05" max="1" step="any" required value={value.observation_interval} onChange={e => onChange({ ...value, observation_interval: e.target.valueAsNumber })} /></label>
    <p className="field-hint">La durata deve essere un multiplo dell’intervallo. Da 2 a 101 misure.</p>
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
  return <Panel title="Registra una previsione" kicker="04 / verifica"><p>Questi tempi derivano dai parametri approvati. La previsione non può essere cambiata dopo il lancio.</p>
    {hypotheses.length === 0 ? <p className="notice">Registra prima un’ipotesi.</p> : <form onSubmit={submit}>
      <label>Ipotesi di riferimento<select value={selectedHypothesis} onChange={e => setHypothesis(e.target.value)}>{hypotheses.map(id => <option key={id}>{id}</option>)}</select></label>
      <div className="table-scroll prediction-table"><table><caption>Posizioni previste per il lancio {requestId}</caption><thead><tr><th scope="col">t (s)</th><th scope="col">x (m)</th><th scope="col">y (m)</th></tr></thead><tbody>{times.map((t, i) => <tr key={i}><th scope="row">{fmt(t)}</th>{(['x', 'y'] as const).map(axis => <td key={axis}><label className="sr-only" htmlFor={`point-${i}-${axis}`}>{axis} a {fmt(t)} secondi</label><input id={`point-${i}-${axis}`} type="number" step="any" min="-1000000" max="1000000" required value={points[i]?.[axis] ?? ''} onChange={e => setPoints(current => current.map((p, j) => j === i ? { ...p, [axis]: e.target.value } : p))} /></td>)}</tr>)}</tbody></table></div>
      <button className="button primary" disabled={busy}>Preregistra previsione</button>
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
  return <Panel title="Predici gli stati nascosti" kicker="06 / challenge"><p>Inserisci l’accelerazione prevista per ogni stato. La legge AST e l’incertezza sono facoltative; nessuna formula inserita qui viene eseguita nel browser.</p>
    <form onSubmit={submit}><div className="table-scroll"><table><caption>Probe pubblici · accelerazioni in m/s²</caption><thead><tr><th scope="col">Stato</th><th scope="col">x, y</th><th scope="col">vx, vy</th><th scope="col">ax</th><th scope="col">ay</th><th scope="col">σ facoltativa</th></tr></thead><tbody>{probes.map((probe, i) => <tr key={probe.probe_id}><th scope="row">{probe.probe_id}<small>{probe.category}</small></th><td>{fmt(probe.x)}, {fmt(probe.y)}</td><td>{fmt(probe.vx)}, {fmt(probe.vy)}</td>{(['ax', 'ay', 'sigma'] as const).map(axis => <td key={axis}><label className="sr-only" htmlFor={`${probe.probe_id}-${axis}`}>{axis} per {probe.probe_id}</label><input id={`${probe.probe_id}-${axis}`} type="number" step="any" required={axis !== 'sigma' || withSigma} min={axis === 'sigma' ? 0.001 : -1000000} max={axis === 'sigma' ? 1000 : 1000000} value={rows[i]?.[axis] ?? ''} onChange={e => setRows(current => current.map((row, j) => j === i ? { ...row, [axis]: e.target.value } : row))} /></td>)}</tr>)}</tbody></table></div>
      <label>Legge candidata AST JSON (facoltativa)<textarea value={law} rows={4} onChange={e => setLaw(e.target.value)} placeholder="Solo AST nel formato documentato; lascia vuoto per valutare le previsioni numeriche." /></label>
      <button className="button primary" disabled={busy}>Consegna e valuta</button></form>
  </Panel>
}

export default function App() {
  const [worlds, setWorlds] = useState<WorldManifest[]>([])
  const [worldId, setWorldId] = useState('')
  const [mode, setMode] = useState('scientist')
  const [configuredAgent, setConfiguredAgent] = useState<AgentInfo | null>(null)
  const [dailyLabel, setDailyLabel] = useState('')
  const [match, setMatch] = useState<Match | null>(null)
  const [matchInput, setMatchInput] = useState('')
  const [humanToken, setHumanToken] = useState('')
  const [operatorToken, setOperatorToken] = useState('')
  const [agentToken, setAgentToken] = useState('')
  const [showAgentToken, setShowAgentToken] = useState(false)
  const [sessionInput, setSessionInput] = useState('')
  const [sessionId, setSessionId] = useState('')
  const [status, setStatus] = useState<SessionStatus | null>(null)
  const [events, setEvents] = useState<LabEvent[]>([])
  const [scores, setScores] = useState<Scores | null>(null)
  const [reveal, setReveal] = useState<unknown>(null)
  const [revealChecked, setRevealChecked] = useState(false)
  const [busy, setBusy] = useState(false)
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
  async function action(work: () => Promise<unknown>, success: string) {
    setBusy(true); setError(''); setNotice('')
    try { await work(); setNotice(success) }
    catch (e) {
      const err = e as Error
      setError(err instanceof ApiError && err.status === 409 ? `${err.message} Stato aggiornato: controlla prima di riprovare.` : err.message)
      if (sessionId) try { await refresh() } catch { /* Keep the original error. */ }
    } finally { setBusy(false) }
  }
  async function create(e: FormEvent) {
    e.preventDefault()
    await action(async () => {
      let created: SessionStatus & { agent_token?: string | null }
      if (mode === 'human_vs_ai') {
        const paired = await api.createMatch(worldId, operatorToken)
        setHumanToken(paired.human_agent_token); setMatchInput(paired.match_id)
        created = { ...paired.human, agent_token: paired.human_agent_token }
      } else created = await api.create(worldId, operatorToken, mode === 'build_universe' ? 'scientist' : mode)
      setSessionId(created.session_id); setSessionInput(created.session_id); setAgentToken(created.agent_token ?? '')
      setReplayTo(null); setReveal(null)
      await refresh(created.session_id)
    }, mode === 'watch_agent' ? 'Sessione creata. Avanza con un passo agente esplicito.' : 'Sessione creata. Conserva il token agente: il server lo mostra una volta sola.')
  }
  async function open(e: FormEvent) {
    e.preventDefault()
    if (!/^[0-9a-f]{32}$/.test(sessionInput.trim())) { setError('ID sessione non valido.'); return }
    await action(async () => {
      await refresh(sessionInput.trim())
      setSessionId(sessionInput.trim()); setAgentToken(''); setShowAgentToken(false); setReplayTo(null); setReveal(null)
    }, 'Replay pubblico caricato. Inserisci i token per continuare a scrivere.')
  }
  async function send(message: unknown, role: 'agent' | 'operator' = 'agent') {
    if (!status) return
    await action(async () => { await api.message(sessionId, status.version, message, role === 'agent' ? agentToken : operatorToken); await refresh() }, 'Evento registrato.')
  }
  function registerWorld(world: WorldManifest) {
    setWorlds(current => [...current.filter(item => item.world_id !== world.world_id), world]); setWorldId(world.world_id)
  }
  async function selectMode(value: string) {
    setMode(value)
    if (value === 'world_of_day') await action(async () => {
      const data = await api.daily(); registerWorld(data.world); setDailyLabel(`${data.day} · ${data.timezone}`)
    }, 'Mondo del giorno selezionato.')
  }
  async function switchParticipant(id: string) {
    await action(async () => {
      await refresh(id); setSessionId(id); setSessionInput(id)
      setAgentToken(id === match?.human_session_id ? humanToken : '')
      setReplayTo(null); setReveal(null)
    }, 'Partecipante selezionato; registro separato caricato.')
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

  return <div className="app-shell"><header className="topbar"><a className="brand" href="#top" aria-label="Zone, inizio pagina"><span className="brand-mark" aria-hidden="true">Z<span>·</span></span><span>ZONE <small>LABORATORIO</small></span></a><span className="topbar-note">Sessione locale · Fase 6</span></header>
    <main id="top"><section className="intro"><div><span className="eyebrow">UNIVERSI SCONOSCIUTI / METODO SPERIMENTALE</span><h1>Scopri la legge.<br /><em>Mostra le prove.</em></h1><p>Un’indagine condivisa fra agente e operatore. Ogni richiesta, decisione, misura e previsione entra nel registro pubblico.</p></div><div className="intro-index" aria-hidden="true"><span>01 — 06</span><span>OSSERVA<br />IPOTIZZA<br />VERIFICA</span></div></section>
      <div className="setup-grid"><Panel title="Nuova sessione" kicker="01 / connessione"><form onSubmit={create}><label>Percorso<select aria-label="Percorso" value={mode} onChange={e => void selectMode(e.target.value)}>{modes.map(([id, name]) => <option key={id} value={id}>{name}</option>)}</select></label><p className="field-hint">{modes.find(item => item[0] === mode)?.[2]}</p>{['watch_agent', 'human_vs_ai'].includes(mode) && configuredAgent && <AgentDescription agent={configuredAgent} />}{mode === 'world_of_day' && <p className="field-hint">{dailyLabel}</p>}<label>Mondo pubblico<select value={worldId} onChange={e => setWorldId(e.target.value)} required disabled={mode === 'world_of_day'}>{worlds.map(w => <option key={w.world_id} value={w.world_id}>{w.world_id} · livello {w.level ?? '—'} · {w.experiment_budget} lanci</option>)}</select></label><label>Token operatore<input type="password" autoComplete="off" value={operatorToken} onChange={e => setOperatorToken(e.target.value)} required placeholder="Inserisci ZONE_OPERATOR_TOKEN" /></label><button className="button primary" disabled={busy || !worldId}>Crea sessione <span aria-hidden="true">↗</span></button></form><p className="field-hint">Il token resta nella memoria della pagina. Non viene salvato nel browser.</p></Panel>
        <Panel title="Apri un replay" kicker="SESSIONE ESISTENTE"><form onSubmit={open}><label>ID sessione<input value={sessionInput} onChange={e => setSessionInput(e.target.value)} placeholder="32 caratteri esadecimali" required /></label><button className="button secondary" disabled={busy}>Apri sessione</button></form><p className="field-hint">Il registro pubblico si legge senza token. Per continuare l’indagine servono i token originali.</p><div className="divider" /><form onSubmit={e => { e.preventDefault(); if (!/^[0-9a-f]{32}$/.test(matchInput.trim())) { setError('ID confronto non valido.'); return } void action(async () => { const paired = await api.match(matchInput.trim()); await refresh(paired.human_session_id); setSessionId(paired.human_session_id); setSessionInput(paired.human_session_id); setAgentToken(''); setHumanToken(''); setReveal(null); setReplayTo(null) }, 'Confronto riaperto. Reinserisci il token umano per continuare.') }}><label>ID confronto<input value={matchInput} onChange={e => setMatchInput(e.target.value)} required /></label><button className="button secondary" disabled={busy}>Apri confronto</button></form></Panel>{mode === 'build_universe' && <UniverseBuilder token={operatorToken} busy={busy} action={action} ready={registerWorld} />}</div>
      <div className="feedback" role="status" aria-live="polite">{error && <p className="error">{error}</p>}{notice && <p className="notice">{notice}</p>}</div>
      {status && <>{match && <MatchView match={match} current={sessionId} busy={busy} change={switchParticipant} />}<section className="session-bar" aria-label="Stato della sessione"><div><span className="kicker">SESSIONE</span><strong className="session-id">{sessionId}</strong></div><div><span className="kicker">STATO</span><strong>{statusLabels[status.status] ?? status.status}</strong></div><div><span className="kicker">LANCI</span><strong>{status.executed_experiments} / {status.executed_experiments + status.remaining_experiments}</strong></div><button className="button ghost" disabled={busy} onClick={() => void action(() => refresh(), 'Registro aggiornato.')}>Aggiorna ↻</button></section>
        <div className="workspace"><div className="workflow">
          {!status.managed_agent && <Panel title="Credenziali della sessione" kicker="ACCESSO LOCALE"><label>Token agente<input type={showAgentToken ? 'text' : 'password'} autoComplete="off" value={agentToken} onChange={e => { setAgentToken(e.target.value); if (status.participant === 'human') setHumanToken(e.target.value) }} placeholder="Token ricevuto alla creazione" /></label><div className="button-row credential-actions"><button type="button" className="button tiny" onClick={() => setShowAgentToken(value => !value)}>{showAgentToken ? 'Nascondi token' : 'Mostra token'}</button><button type="button" className="button tiny" disabled={!agentToken} onClick={() => void navigator.clipboard.writeText(agentToken).then(() => setNotice('Token agente copiato negli appunti.')).catch(() => setError('Impossibile copiare: seleziona il token manualmente.'))}>Copia token agente</button></div><p className="field-hint">Il token agente può proporre e concludere. Solo l’operatore può approvare ed eseguire. Alla riapertura, reinserisci i token: non sono conservati dal browser.</p></Panel>}
          {status.managed_agent && status.agent && <Panel title="Passo dell’agente" kicker="AGENTE GESTITO"><AgentDescription agent={status.agent} /><p>{status.agent.calls} / {status.agent.settings.max_calls} chiamate · {status.agent.turns} / {status.agent.settings.max_turns} turni · {status.agent.invalid_responses} risposte invalide.</p><p>Un passo registra un solo messaggio. I lanci richiedono sempre la tua decisione, la modalità e il comando di esecuzione.</p><button className="button primary" disabled={busy || !operatorToken || !['discovering', 'awaiting_prediction', 'awaiting_submission'].includes(status.status) || (status.agent.calls ?? 0) >= status.agent.settings.max_calls || (status.agent.turns ?? 0) >= status.agent.settings.max_turns || (!!match && !['scoring_pending', 'scored', 'revealed'].includes(match.human.status))} onClick={() => void action(async () => { await api.step(sessionId, status.version, operatorToken); await refresh() }, 'Messaggio agente registrato; nessun lancio automatico.')}>Avanza agente →</button></Panel>}
          {status.status === 'awaiting_answer' && <Panel title="Rispondi alla domanda" kicker="OPERATORE"><blockquote>{asText(questionEvent?.message.question)}</blockquote><p className="muted">Scopo: {asText(questionEvent?.message.purpose)}</p><form onSubmit={e => { e.preventDefault(); void send({ type: 'operator_answer', question_id: status.pending_question_id, answer }, 'operator').then(() => setAnswer('')) }}><label>Risposta<textarea required maxLength={2000} value={answer} onChange={e => setAnswer(e.target.value)} /></label><button className="button primary" disabled={busy || !operatorToken}>Registra risposta</button></form></Panel>}
          {canInvestigate && status.status !== 'awaiting_answer' && <>
            {!status.managed_agent && !status.pending_request_id && status.remaining_experiments > 0 && <Panel title="Proponi un esperimento" kicker="02 / AGENTE"><form onSubmit={e => { e.preventDefault(); if (!validExperiment(experiment)) { setError('Parametri fuori limite o durata non multipla dell’intervallo.'); return } void send({ type: 'experiment_request', request_id: newId('e'), purpose, experiment }).then(() => setPurpose('')) }}><label>Scopo del lancio<textarea required maxLength={2000} value={purpose} onChange={e => setPurpose(e.target.value)} placeholder="Quale ipotesi o comportamento vuoi esaminare?" /></label><ExperimentFields value={experiment} onChange={setExperiment} /><button className="button primary" disabled={busy || !agentToken}>Invia richiesta</button></form></Panel>}
            {status.status === 'awaiting_decision' && pendingExperiment && <Panel title="Decidi sul lancio" kicker="03 / OPERATORE"><p className="lead">{asText(pending?.message.purpose)}</p><p className="muted">Richiesta {status.pending_request_id}. Nessun esperimento parte senza una decisione e un comando di esecuzione.</p><form onSubmit={e => { e.preventDefault(); if (decision === 'modify' && !validExperiment(modified)) { setError('Parametri modificati non validi.'); return } void send({ type: 'operator_decision', request_id: status.pending_request_id, action: decision, reason, ...(decision === 'modify' ? { modified_experiment: modified } : {}) }, 'operator') }}><fieldset className="choice-group"><legend>Decisione esplicita</legend>{(match ? ['approve'] as const : ['approve', 'modify', 'reject'] as const).map(choice => <label key={choice} className="choice"><input type="radio" name="decision" value={choice} checked={decision === choice} onChange={() => { setDecision(choice); if (choice === 'modify') setModified(pendingExperiment) }} /><span>{choice === 'approve' ? 'Approva' : choice === 'modify' ? 'Modifica' : 'Rifiuta'}</span></label>)}</fieldset>{decision === 'modify' && <ExperimentFields value={modified} onChange={setModified} />}<label>Motivazione<input required maxLength={2000} value={reason} onChange={e => setReason(e.target.value)} placeholder="Perché questa decisione?" /></label><button className="button primary" disabled={busy || !operatorToken}>Registra decisione</button></form></Panel>}
            {status.status === 'awaiting_mode' && <Panel title="Scegli la modalità" kicker="OPERATORE"><p>I parametri approvati sono visibili nel registro. In verifica, l’agente deve preregistrare le posizioni previste prima dell’esecuzione.</p><div className="button-row"><button className="button secondary" disabled={busy || !operatorToken} onClick={() => void send({ type: 'execution_mode', request_id: status.pending_request_id, mode: 'exploration' }, 'operator')}>Esplorazione</button>{!match && <button className="button primary" disabled={busy || !operatorToken} onClick={() => void send({ type: 'execution_mode', request_id: status.pending_request_id, mode: 'verification' }, 'operator')}>Verifica con previsione</button>}</div></Panel>}
            {!status.managed_agent && status.status === 'awaiting_prediction' && approvedExperiment && <PredictionForm key={`${status.pending_request_id}:${JSON.stringify(approvedExperiment)}`} experiment={approvedExperiment} hypotheses={hypotheses} requestId={status.pending_request_id ?? ''} send={message => send(message)} busy={busy || !agentToken} />}
            {status.status === 'ready_to_run' && <Panel title="Esegui il lancio" kicker="OPERATORE"><p>Richiesta <strong>{status.pending_request_id}</strong> pronta. Il lancio consuma una unità di budget, anche se la traiettoria fallisce.</p><button className="button primary" disabled={busy || !operatorToken} onClick={() => void action(async () => { await api.run(sessionId, status.version, status.pending_request_id ?? '', operatorToken); await refresh() }, 'Esperimento eseguito; osservazione registrata.')}>Esegui esperimento →</button></Panel>}
            {!status.managed_agent && <Panel title="Ipotesi e dialogo" kicker="AGENTE"><p>Registra una nuova ipotesi dopo aver letto le misure, oppure chiedi un chiarimento all’operatore.</p><form onSubmit={e => { e.preventDefault(); void send({ type: 'hypothesis', hypothesis_id: hypothesisId, statement: hypothesisText, uncertainties: textList(uncertainties), evidence }).then(() => { setHypothesisId(newId('h')); setHypothesisText('') }) }}><label>Ipotesi<textarea required maxLength={2000} value={hypothesisText} onChange={e => setHypothesisText(e.target.value)} /></label><label>Incertezze (una per riga)<textarea value={uncertainties} onChange={e => setUncertainties(e.target.value)} /></label><EvidenceChoices observations={observations} selected={evidence} change={setEvidence} /><button className="button secondary" disabled={busy || !agentToken}>Registra ipotesi</button></form>{!match && <><div className="divider" /><form onSubmit={e => { e.preventDefault(); void send({ type: 'operator_question', question_id: newId('q'), question, purpose: questionPurpose }).then(() => { setQuestion(''); setQuestionPurpose('') }) }}><label>Domanda<textarea required maxLength={2000} value={question} onChange={e => setQuestion(e.target.value)} /></label><label>Scopo della domanda<input required maxLength={2000} value={questionPurpose} onChange={e => setQuestionPurpose(e.target.value)} /></label><button className="button secondary" disabled={busy || !agentToken}>Chiedi all’operatore</button></form></>}</Panel>}
            {!status.managed_agent && <Panel title="Concludi l’indagine" kicker="05 / AGENTE"><p>Puoi dichiarare che le informazioni sono insufficienti. Il backend pubblicherà i probe solo dopo la conclusione.</p><form onSubmit={e => { e.preventDefault(); void send({ type: 'conclusion', final_hypothesis_id: finalHypothesis || null, summary, evidence, limits: textList(limits), alternatives: textList(alternatives) }) }}><label>Ipotesi finale<select value={finalHypothesis} onChange={e => setFinalHypothesis(e.target.value)}><option value="">Nessuna: evidenze insufficienti</option>{hypotheses.map(id => <option key={id}>{id}</option>)}</select></label><label>Conclusione<textarea required maxLength={2000} value={summary} onChange={e => setSummary(e.target.value)} /></label><EvidenceChoices observations={observations} selected={evidence} change={setEvidence} /><label>Limiti (almeno uno, uno per riga)<textarea required value={limits} onChange={e => setLimits(e.target.value)} /></label><label>Alternative plausibili (una per riga)<textarea value={alternatives} onChange={e => setAlternatives(e.target.value)} /></label><button className="button secondary" disabled={busy || !agentToken || !textList(limits).length}>Registra conclusione</button></form></Panel>}
          </>}
          {!status.managed_agent && status.status === 'awaiting_submission' && <SubmissionForm key={sessionId} probes={probes} busy={busy || !agentToken} send={submission => action(async () => { await api.submit(sessionId, status.version, submission, agentToken); await refresh() }, 'Submission valutata.')} />}
          {status.status === 'scoring_pending' && <Panel title="Riprendi valutazione" kicker="OPERATORE"><p>La submission è già congelata. {match && !match.complete ? 'Attendi anche la consegna dell’altro partecipante prima dei punteggi.' : 'Riprendi solo il calcolo del punteggio; nessun lancio verrà ripetuto.'}</p><button className="button primary" disabled={busy || !operatorToken || (!!match && !['scoring_pending', 'scored', 'revealed'].includes(match.agent.status))} onClick={() => void action(async () => { await api.score(sessionId, status.version, operatorToken); await refresh() }, 'Valutazione completata.')}>Calcola punteggio</button></Panel>}
          {scores && <Panel title="Risultato" kicker="07 / VALUTAZIONE"><p>Le dimensioni restano separate. La legge AST è facoltativa e l’equivalenza, se presente, è empirica sulla griglia privata.</p><ResultView scores={scores} /></Panel>}
          {(status.status === 'scored' || status.status === 'stopped') && <Panel title="Rivela il mondo" kicker="OPERATORE · IRREVERSIBILE"><p>Il reveal espone configurazione e audit privati su questa pagina. Fallo solo dopo aver concluso la valutazione.</p><label className="check-row"><input type="checkbox" checked={revealChecked} onChange={e => setRevealChecked(e.target.checked)} />Confermo di voler rivelare il mondo privato</label><button className="button danger" disabled={busy || !operatorToken || !revealChecked || (!!match && ![match.human.status, match.agent.status].every(s => ['scored', 'stopped', 'revealed'].includes(s)))} onClick={() => void action(async () => { const data = await api.reveal(sessionId, status.version, operatorToken); setReveal(data); await refresh() }, 'Mondo rivelato.')}>Rivela mondo</button></Panel>}
          {reveal !== null && <Panel title="Record privato" kicker="SOLO OPERATORE"><pre className="private-record">{JSON.stringify(reveal, null, 2)}</pre></Panel>}
          {status.status !== 'scored' && status.status !== 'stopped' && status.status !== 'revealed' && <details className="stop-area"><summary>Arresta l’indagine</summary><p>L’arresto non inventa una conclusione. Un lancio interrotto non verrà rieseguito.</p><button className="button danger" disabled={busy || !operatorToken} onClick={() => void action(async () => { await api.stop(sessionId, status.version, status.status === 'execution_started' ? 'interrupted_execution' : 'operator_stop', operatorToken); await refresh() }, 'Indagine arrestata.')}>Conferma arresto</button></details>}
        </div><aside className="replay"><div className="replay-heading"><span className="kicker">REGISTRO PUBBLICO</span><h2>Replay <span>{visibleEvents.length}/{events.length}</span></h2><p>Eventi in ordine canonico. I contenuti restano pubblici anche dopo il reveal.</p><label>Fino all’evento <input aria-label="Fino all’evento" type="range" min="1" max={Math.max(1, events.length)} value={replayTo ?? Math.max(1, events.length)} onChange={e => setReplayTo(Number(e.target.value))} /></label><div className="button-row"><button className="button tiny" disabled={events.length < 2} onClick={() => setReplayTo(Math.max(1, (replayTo ?? events.length) - 1))}>← Prima</button><button className="button tiny" disabled={replayTo === null} onClick={() => setReplayTo(null)}>Tutti gli eventi</button></div></div><div className="timeline">{visibleEvents.map(event => <EventCard key={event.seq} event={event} />)}</div></aside></div>
      </>}
    </main><footer className="footer"><span>ZONE / LABORATORIO LOCALE</span><span>Fase 6 · Agenti e segreti restano sul server locale</span></footer></div>
}

function EvidenceChoices({ observations, selected, change }: { observations: string[]; selected: string[]; change: (ids: string[]) => void }) {
  return <fieldset className="evidence"><legend>Misure a sostegno</legend>{observations.length ? observations.map(id => <label key={id} className="check-row"><input type="checkbox" checked={selected.includes(id)} onChange={e => change(e.target.checked ? [...selected, id] : selected.filter(item => item !== id))} />Osservazione {id}</label>) : <p className="field-hint">Nessuna misura riuscita disponibile.</p>}</fieldset>
}
