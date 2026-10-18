import { ScientificText } from './ScientificText'
import type { LabEvent, Experiment, Probe, Scores } from './types'

export function asText(value: unknown): string { return typeof value === 'string' ? value : '' }
export function asNumber(value: unknown): number { return typeof value === 'number' ? value : 0 }
export function asExperiment(value: unknown): Experiment | null {
  if (!value || typeof value !== 'object') return null
  const item = value as Experiment
  return item.initial_position && item.initial_velocity ? item : null
}
export function asProbes(value: unknown): Probe[] { return Array.isArray(value) ? value as Probe[] : [] }
export function fmt(value: unknown): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '—'
  const magnitude = Math.abs(value)
  return new Intl.NumberFormat('en-US', magnitude > 0 && (magnitude < 0.0001 || magnitude >= 1e6)
    ? { notation: 'scientific', maximumSignificantDigits: 4 }
    : { maximumFractionDigits: 4 }).format(Object.is(value, -0) ? 0 : value)
}

const statusNames: Record<string, string> = {
  discovering: 'Investigation in progress', awaiting_decision: 'Decision needed', awaiting_mode: 'Choose an execution mode',
  awaiting_prediction: 'Prediction needed', ready_to_run: 'Ready to run', execution_started: 'Experiment interrupted',
  awaiting_answer: 'Answer needed', awaiting_submission: 'Final test available', scoring_pending: 'Evaluation pending',
  scored: 'Results available', stopped: 'Investigation stopped', revealed: 'World revealed',
}
export function statusName(status: string): string { return statusNames[status] ?? 'Check the investigation history' }
export function integrityName(state?: string): string {
  return ({ blind_test: 'Blind test', public_practice: 'Public practice', untracked: 'Not tracked',
    retired: 'Retired', contaminated: 'Contaminated', known_law: 'Law already known', operator_hint: 'Operator hint',
    external_disclosure: 'External disclosure', protocol_violation: 'Protocol violation' } as Record<string, string>)[state ?? 'untracked'] ?? 'Diagnostic only'
}
export function dimensionName(dimension: string): string {
  return ({ acceleration_rmse: 'Overall numerical error (RMSE)', interpolation_rmse: 'Interpolation error (RMSE)',
    extrapolation_rmse: 'Extrapolation error (RMSE)', functional_rmse: 'AST functional error (RMSE)',
    ast_nodes: 'Complexity · AST nodes', calibration_nll: 'Calibration · negative log likelihood',
    missed_dependencies: 'Missing dependencies', spurious_dependencies: 'Extra dependencies',
    max_acceleration_error: 'Maximum acceleration error', normalized_rmse: 'Normalized error', normalized_error: 'Normalized error',
    position_rmse: 'Position error (RMSE)' } as Record<string, string>)[dimension] ?? dimension.replaceAll('_', ' ')
}
export function referenceName(events: LabEvent[], kind: 'experiment_request' | 'hypothesis', id: unknown): string {
  if (!id) return 'None'
  const field = kind === 'hypothesis' ? 'hypothesis_id' : 'request_id'
  const index = events.filter(e => e.message.type === kind).findIndex(e => e.message[field] === id)
  const name = kind === 'hypothesis' ? 'Hypothesis' : 'Experiment'
  return index < 0 ? `Earlier ${name.toLowerCase()}` : `${name} ${index + 1}`
}
function stopReason(reason: unknown): string {
  return ({ provider_error: 'The model provider could not complete the request.', invalid_response_limit: 'The model reached the invalid reply limit.',
    operator_stop: 'Stopped by the operator.', interrupted_execution: 'An interrupted experiment was closed without repeating it.',
    call_limit: 'The model call budget was reached.', turn_limit: 'The message limit was reached.' } as Record<string, string>)[asText(reason)] ?? 'A safety or resource limit stopped this investigation. Check the technical record.'
}

export function EventCard({ event, events = [event] }: { event: LabEvent; events?: LabEvent[] }) {
  const m = event.message
  const type = m.type
  const title: Record<string, string> = {
    apparatus: "Apparatus", experiment_request: "Experiment proposal", operator_decision: "Operator decision",
    execution_mode: "Execution mode", execution_started: "Experiment started", observation: "Observation",
    hypothesis: "Hypothesis", prediction: "Preregistered prediction", verification: "Verification",
    operator_question: "Question for the operator", operator_answer: "Operator answer", conclusion: "Conclusion",
    probe_challenge: 'Challenge', scientific_submission: 'Submission', result_recorded: "Results",
    reveal_recorded: 'Reveal', investigation_stopped: "Investigation stopped", protocol_error: "Protocol error",
  }
  const experiment = asExperiment(m.experiment ?? m.modified_experiment)
  const points = Array.isArray(m.points) ? m.points as { t: number; x: number; y: number }[] : []
  const experimentName = (id: unknown) => referenceName(events, 'experiment_request', id)
  const hypothesisName = (id: unknown) => referenceName(events, 'hypothesis', id)
  const evidence = Array.isArray(m.evidence) && m.evidence.length ? m.evidence.map(experimentName).join(', ') : 'none'
  return <article className="event-card" aria-label={`Event ${event.seq}: ${title[type] ?? type}`}>
    <div className="event-meta"><span className="event-seq">{event.seq}</span><span>{{ apparatus: 'Laboratory', agent: 'Agent', operator: 'Operator', system: 'System' }[event.actor] ?? 'Laboratory'}</span></div>
    <div className="event-body"><h3>{title[type] ?? type}</h3>
      {type === 'apparatus' && <p>x points right; y points up. Units: meters and seconds. Budget: {fmt(m.experiment_budget)} experiments.</p>}
      {type === 'experiment_request' && <><p><ScientificText text={asText(m.purpose)} /></p><p className="muted">{experimentName(m.request_id)}</p></>}
      {type === 'operator_decision' && <p>{m.action === 'approve' ? "Approved" : m.action === 'modify' ? "Modified" : "Rejected"} · {asText(m.reason)}</p>}
      {type === 'execution_mode' && <p>{m.mode === 'verification' ? "Verification with a prediction" : "Exploration"}</p>}
      {type === 'hypothesis' && <><p><ScientificText text={asText(m.statement)} /></p><p className="muted">{hypothesisName(m.hypothesis_id)} · Evidence: {evidence}</p>{Array.isArray(m.uncertainties) && m.uncertainties.length > 0 && <p className="muted">Uncertainties: {m.uncertainties.join('; ')}</p>}</>}
      {type === 'prediction' && <p>{points.length} points preregistered for {experimentName(m.request_id)}. Reference: {hypothesisName(m.hypothesis_id)}.</p>}
      {type === 'operator_question' && <><p><ScientificText text={asText(m.question)} /></p><p className="muted">Purpose: <ScientificText text={asText(m.purpose)} /></p></>}
      {type === 'operator_answer' && <p><ScientificText text={asText(m.answer)} /></p>}
      {type === 'observation' && <p>{m.status === 'ok' ? `${points.length} measurements recorded` : asText((m.error as { message?: unknown } | null)?.message)}</p>}
      {type === 'verification' && (m.status === 'ok' && m.metrics && typeof m.metrics === 'object' ? <dl className="experiment-summary"><div><dt>Position error (RMSE)</dt><dd>{fmt((m.metrics as Record<string, unknown>).position_rmse)} m</dd></div><div><dt>Maximum error</dt><dd>{fmt((m.metrics as Record<string, unknown>).max_position_error)} m</dd></div></dl> : <p>Verification is unavailable.</p>)}
      {type === 'conclusion' && <><p><ScientificText text={asText(m.summary)} /></p><p className="muted">Final hypothesis: {hypothesisName(m.final_hypothesis_id)} · Evidence: {evidence}</p><p className="muted">Limits: {Array.isArray(m.limits) ? m.limits.join('; ') : ''}</p><p className="muted">Alternatives: {Array.isArray(m.alternatives) && m.alternatives.length ? m.alternatives.join('; ') : "none stated"}</p></>}
      {type === 'probe_challenge' && <p>{asProbes(m.probes).length} states to predict. True accelerations remain hidden.</p>}
      {type === 'scientific_submission' && <p>Predictions submitted for {Array.isArray(m.predictions) ? m.predictions.length : 0} probe.</p>}
      {type === 'result_recorded' && <p>Evaluation completed. Scores are available in the Results panel.</p>}
      {type === 'investigation_stopped' && <p>{stopReason(m.reason)}</p>}
      {experiment && <dl className="experiment-summary"><div><dt>Initial position</dt><dd>{fmt(experiment.initial_position.x)}, {fmt(experiment.initial_position.y)} m</dd></div><div><dt>Initial velocity</dt><dd>{fmt(experiment.initial_velocity.x)}, {fmt(experiment.initial_velocity.y)} m/s</dd></div><div><dt>Duration / interval</dt><dd>{fmt(experiment.duration)} / {fmt(experiment.observation_interval)} s</dd></div></dl>}
      {(type === 'observation' || type === 'prediction') && points.length > 0 && <div className="table-scroll"><table><caption>{type === 'observation' ? "Measured positions in meters" : "Predicted positions in meters"}</caption><thead><tr><th scope="col">t (s)</th><th scope="col">x (m)</th><th scope="col">y (m)</th></tr></thead><tbody>{points.map((p, i) => <tr key={i}><td>{fmt(p.t)}</td><td>{fmt(p.x)}</td><td>{fmt(p.y)}</td></tr>)}</tbody></table></div>}
    </div>
  </article>
}

function metric(label: string, value: unknown) { return <div className="metric" key={label}><span>{label}</span><strong>{fmt(value)}</strong></div> }
function metricGroup(label: string, value: unknown) {
  if (!value || typeof value !== 'object') return null
  const data = value as Record<string, unknown>
  return <section className="result-group" key={label}><h3>{label}</h3><div className="metric-grid">
    {Object.entries(data).filter(([, v]) => typeof v === 'number').map(([key, v]) => metric(dimensionName(key), v))}
    {typeof data.empirically_equivalent === 'boolean' && <p>Empirically equivalent: <strong>{data.empirically_equivalent ? "Yes" : 'No'}</strong></p>}
    {typeof data.exact_match === 'boolean' && <p>Exact dependencies: <strong>{data.exact_match ? "Yes" : 'No'}</strong></p>}
  </div>{Boolean(data.by_category) && <div className="category-grid">{Object.entries(data.by_category as Record<string, unknown>).map(([name, nested]) => metricGroup(name === 'interpolation' ? "Inside the domain (interpolation)" : name === 'extrapolation' ? "Outside the domain (extrapolation)" : name, nested))}</div>}
  {Boolean(data.metrics) && metricGroup("Private evaluation grid", data.metrics)}</section>
}
export function ResultView({ scores }: { scores: Scores }) {
  return <div className="result-grid">{metricGroup("Numerical prediction", scores.prediction)}{metricGroup("Candidate law", scores.functional)}{metricGroup("Complexity", scores.complexity)}{metricGroup("Dependencies", scores.dependencies)}{metricGroup("Calibration", scores.calibration)}</div>
}
