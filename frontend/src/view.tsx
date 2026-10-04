import type { LabEvent, Experiment, Probe, Scores } from './types'

export function asText(value: unknown): string { return typeof value === 'string' ? value : '' }
export function asNumber(value: unknown): number { return typeof value === 'number' ? value : 0 }
export function asExperiment(value: unknown): Experiment | null {
  if (!value || typeof value !== 'object') return null
  const item = value as Experiment
  return item.initial_position && item.initial_velocity ? item : null
}
export function asProbes(value: unknown): Probe[] { return Array.isArray(value) ? value as Probe[] : [] }
export function fmt(value: unknown): string { return typeof value === 'number' ? new Intl.NumberFormat('it-IT', { maximumFractionDigits: 4 }).format(value) : '—' }

export function EventCard({ event }: { event: LabEvent }) {
  const m = event.message
  const type = m.type
  const title: Record<string, string> = {
    apparatus: 'Apparato', experiment_request: 'Richiesta di esperimento', operator_decision: 'Decisione operatore',
    execution_mode: 'Modalità di esecuzione', execution_started: 'Esperimento avviato', observation: 'Osservazione',
    hypothesis: 'Ipotesi', prediction: 'Previsione preregistrata', verification: 'Verifica',
    operator_question: 'Domanda all’operatore', operator_answer: 'Risposta operatore', conclusion: 'Conclusione',
    probe_challenge: 'Challenge', scientific_submission: 'Submission', result_recorded: 'Risultato',
    reveal_recorded: 'Reveal', investigation_stopped: 'Indagine arrestata', protocol_error: 'Errore di protocollo',
  }
  const experiment = asExperiment(m.experiment ?? m.modified_experiment)
  const points = Array.isArray(m.points) ? m.points as { t: number; x: number; y: number }[] : []
  return <article className="event-card" aria-label={`Evento ${event.seq}: ${title[type] ?? type}`}>
    <div className="event-meta"><span className="event-seq">{String(event.seq).padStart(2, '0')}</span><span>{event.actor}</span></div>
    <div className="event-body"><h3>{title[type] ?? type}</h3>
      {type === 'apparatus' && <p>Coordinate: {asText(m.coordinates)}. Budget: {fmt(m.experiment_budget)} esperimenti.</p>}
      {type === 'experiment_request' && <><p>{asText(m.purpose)}</p><p className="muted">Richiesta {asText(m.request_id)}</p></>}
      {type === 'operator_decision' && <p>{asText(m.action)} · {asText(m.reason)}</p>}
      {type === 'execution_mode' && <p>{m.mode === 'verification' ? 'Verifica con previsione' : 'Esplorazione'}</p>}
      {type === 'hypothesis' && <><p>{asText(m.statement)}</p><p className="muted">ID {asText(m.hypothesis_id)} · Evidenze: {Array.isArray(m.evidence) && m.evidence.length ? m.evidence.join(', ') : 'nessuna'}</p>{Array.isArray(m.uncertainties) && m.uncertainties.length > 0 && <p className="muted">Incertezze: {m.uncertainties.join('; ')}</p>}</>}
      {type === 'prediction' && <p>{points.length} punti preregistrati per {asText(m.request_id)}. Ipotesi {asText(m.hypothesis_id)}.</p>}
      {type === 'operator_question' && <><p>{asText(m.question)}</p><p className="muted">Scopo: {asText(m.purpose)}</p></>}
      {type === 'operator_answer' && <p>{asText(m.answer)}</p>}
      {type === 'observation' && <p>{m.status === 'ok' ? `${points.length} misure registrate` : asText((m.error as { message?: unknown } | null)?.message)}</p>}
      {type === 'verification' && (m.status === 'ok' && m.metrics && typeof m.metrics === 'object' ? <dl className="experiment-summary"><div><dt>RMSE posizione</dt><dd>{fmt((m.metrics as Record<string, unknown>).position_rmse)} m</dd></div><div><dt>Errore massimo</dt><dd>{fmt((m.metrics as Record<string, unknown>).max_position_error)} m</dd></div></dl> : <p>Verifica non disponibile.</p>)}
      {type === 'conclusion' && <><p>{asText(m.summary)}</p><p className="muted">Ipotesi finale: {asText(m.final_hypothesis_id) || 'nessuna'} · Evidenze: {Array.isArray(m.evidence) && m.evidence.length ? m.evidence.join(', ') : 'nessuna'}</p><p className="muted">Limiti: {Array.isArray(m.limits) ? m.limits.join('; ') : ''}</p><p className="muted">Alternative: {Array.isArray(m.alternatives) && m.alternatives.length ? m.alternatives.join('; ') : 'nessuna indicata'}</p></>}
      {type === 'probe_challenge' && <p>{asProbes(m.probes).length} stati da prevedere. Le accelerazioni vere restano nascoste.</p>}
      {type === 'scientific_submission' && <p>Previsioni consegnate per {Array.isArray(m.predictions) ? m.predictions.length : 0} probe.</p>}
      {type === 'result_recorded' && <p>Valutazione completata. I punteggi sono visibili nel pannello Risultato.</p>}
      {type === 'investigation_stopped' && <p>Motivo: {asText(m.reason)}</p>}
      {experiment && <dl className="experiment-summary"><div><dt>Posizione iniziale</dt><dd>{fmt(experiment.initial_position.x)}, {fmt(experiment.initial_position.y)} m</dd></div><div><dt>Velocità iniziale</dt><dd>{fmt(experiment.initial_velocity.x)}, {fmt(experiment.initial_velocity.y)} m/s</dd></div><div><dt>Durata / passo</dt><dd>{fmt(experiment.duration)} / {fmt(experiment.observation_interval)} s</dd></div></dl>}
      {(type === 'observation' || type === 'prediction') && points.length > 0 && <div className="table-scroll"><table><caption>{type === 'observation' ? 'Misure in metri' : 'Posizioni previste in metri'}</caption><thead><tr><th scope="col">t (s)</th><th scope="col">x (m)</th><th scope="col">y (m)</th></tr></thead><tbody>{points.map((p, i) => <tr key={i}><td>{fmt(p.t)}</td><td>{fmt(p.x)}</td><td>{fmt(p.y)}</td></tr>)}</tbody></table></div>}
    </div>
  </article>
}

function metric(label: string, value: unknown) { return <div className="metric" key={label}><span>{label}</span><strong>{fmt(value)}</strong></div> }
function metricGroup(label: string, value: unknown) {
  if (!value || typeof value !== 'object') return null
  const data = value as Record<string, unknown>
  return <section className="result-group" key={label}><h3>{label}</h3><div className="metric-grid">
    {Object.entries(data).filter(([, v]) => typeof v === 'number').map(([key, v]) => metric(key.replaceAll('_', ' '), v))}
    {typeof data.empirically_equivalent === 'boolean' && <p>Equivalenza empirica: <strong>{data.empirically_equivalent ? 'Sì' : 'No'}</strong></p>}
    {typeof data.exact_match === 'boolean' && <p>Dipendenze esatte: <strong>{data.exact_match ? 'Sì' : 'No'}</strong></p>}
  </div>{Boolean(data.by_category) && <div className="category-grid">{Object.entries(data.by_category as Record<string, unknown>).map(([name, nested]) => metricGroup(name, nested))}</div>}
  {Boolean(data.metrics) && metricGroup('Griglia privata', data.metrics)}</section>
}
export function ResultView({ scores }: { scores: Scores }) {
  return <div className="result-grid">{metricGroup('Previsione numerica', scores.prediction)}{metricGroup('Legge candidata', scores.functional)}{metricGroup('Complessità', scores.complexity)}{metricGroup('Dipendenze', scores.dependencies)}{metricGroup('Calibrazione', scores.calibration)}</div>
}
