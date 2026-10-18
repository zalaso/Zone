import { useEffect, useId, useState } from 'react'
import type { Experiment, LabEvent } from './types'
import { asExperiment, asText, fmt, referenceName } from './view'

export type Point = { t: number; x: number; y: number }
function publicPoints(value: unknown): Point[] {
  return Array.isArray(value) ? value.filter((p): p is Point => !!p && typeof p === 'object' &&
    [p.t, p.x, p.y].every(n => typeof n === 'number' && Number.isFinite(n))).slice(0, 101) : []
}

export function experimentScene(events: LabEvent[]) {
  const observation = events.findLast(e => e.message.type === 'observation')
  const request = events.findLast(e => e.message.type === 'experiment_request')
  // A new request takes precedence over an old observation; never imply it has run.
  const requestId = asText(request && (!observation || request.seq > observation.seq) ? request.message.request_id : observation?.message.request_id)
  const proposal = events.findLast(e => e.message.type === 'experiment_request' && e.message.request_id === requestId)
  const modified = events.findLast(e => e.message.type === 'operator_decision' && e.message.request_id === requestId && e.message.action === 'modify')
  const execution = events.findLast(e => e.message.type === 'execution_started' && e.message.request_id === requestId)
  const data = observation?.message.request_id === requestId ? observation.message : null
  const prediction = events.findLast(e => e.message.type === 'prediction' && e.message.request_id === requestId)
  return { requestId, experiment: asExperiment(execution?.message.experiment ?? modified?.message.modified_experiment ?? proposal?.message.experiment),
    points: data?.status === 'ok' ? publicPoints(data.points) : [], prediction: publicPoints(prediction?.message.points), failed: data?.status === 'error',
    purpose: asText(proposal?.message.purpose), modified: !!modified }
}

export function ExperimentStage({ experiment, points = [], prediction = [], label = "Experiment view", failed = false }: {
  experiment: Experiment | null; points?: Point[]; prediction?: Point[]; label?: string; failed?: boolean
}) {
  const [index, setIndex] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [showPrediction, setShowPrediction] = useState(true)
  const markerId = useId().replaceAll(':', '')
  const pointKey = points.map(p => `${p.t}:${p.x}:${p.y}`).join('|')
  useEffect(() => { setIndex(0); setPlaying(false) }, [pointKey])
  useEffect(() => {
    if (!playing) return
    const timer = window.setInterval(() => setIndex(current => {
      if (current >= points.length - 1) { setPlaying(false); return current }
      return current + 1
    }), 650)
    return () => window.clearInterval(timer)
  }, [playing, points.length])
  const initial = experiment?.initial_position
  const positions = [...points, ...(showPrediction ? prediction : []), ...(initial ? [{ ...initial, t: 0 }] : [])].filter(p => Number.isFinite(p.x) && Number.isFinite(p.y))
  const xs = positions.map(p => p.x), ys = positions.map(p => p.y)
  const minX = Math.min(-1, ...xs), maxX = Math.max(1, ...xs), minY = Math.min(-1, ...ys), maxY = Math.max(1, ...ys)
  const padX = (maxX - minX) * .12, padY = (maxY - minY) * .15
  const x = (n: number) => 52 + (n - minX + padX) / (maxX - minX + 2 * padX) * 506
  const y = (n: number) => 246 - (n - minY + padY) / (maxY - minY + 2 * padY) * 214
  const selected = points[Math.min(index, points.length - 1)]
  const velocity = experiment?.initial_velocity
  const magnitude = velocity ? Math.hypot(velocity.x, velocity.y) : 0
  const initialFinite = initial && Number.isFinite(initial.x) && Number.isFinite(initial.y)
  return <figure className="experiment-stage"><figcaption><strong>{label}</strong><span>{points.length ? "Laboratory measurements" : failed ? "No measurements returned" : "Initial conditions · trajectory unknown"}</span></figcaption>
    <svg viewBox="0 0 600 285" role="img" aria-label={points.length ? `Trajectory: ${points.length} measured samples. Selected point at ${fmt(selected?.t)} seconds.` : "Coordinate plane showing initial position and velocity direction. No simulated trajectory is shown."}>
      <defs><marker id={markerId} markerWidth="7" markerHeight="7" refX="5" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6" fill="currentColor" /></marker></defs>
      {[0, 1, 2, 3, 4].map(i => <g className="plot-grid" key={i}><line x1={52 + i * 126.5} x2={52 + i * 126.5} y1="32" y2="246" /><line x1="52" x2="558" y1={32 + i * 53.5} y2={32 + i * 53.5} /></g>)}
      <g className="plot-axes"><line x1="52" x2="558" y1={y(0)} y2={y(0)} /><line x1={x(0)} x2={x(0)} y1="32" y2="246" /></g>
      <g className="plot-labels"><text x="558" y="278" textAnchor="end">x [m] →</text><text x="12" y="20">y [m] ↑</text><text x="52" y="265">{fmt(minX - padX)}</text><text x="558" y="265" textAnchor="end">{fmt(maxX + padX)}</text><text x="5" y="43">{fmt(maxY + padY)}</text><text x="5" y="246">{fmt(minY - padY)}</text></g>
      {showPrediction && prediction.length > 0 && <polyline className="predicted-path" points={prediction.map(p => `${x(p.x)},${y(p.y)}`).join(' ')} />}
      {points.length > 0 ? <><polyline className="observed-path" points={points.map(p => `${x(p.x)},${y(p.y)}`).join(' ')} />{points.map((p, i) => <circle className="sample-point" key={i} cx={x(p.x)} cy={y(p.y)} r="3" />)}{selected && <circle className="current-point" cx={x(selected.x)} cy={y(selected.y)} r="8" />}</> : initialFinite && <><circle className="current-point" cx={x(initial.x)} cy={y(initial.y)} r="8" />{magnitude > 0 && velocity && <line className="velocity-vector" x1={x(initial.x)} y1={y(initial.y)} x2={x(initial.x) + velocity.x / magnitude * 38} y2={y(initial.y) - velocity.y / magnitude * 38} markerEnd={`url(#${markerId})`} />}</>}
    </svg>
    {points.length > 0 && <div className="playback-controls"><button className="button secondary" onClick={() => { if (index >= points.length - 1) setIndex(0); setPlaying(!playing) }}>{playing ? "Pause replay" : "Play measurements"}</button><label>Observed sample<input type="range" min="0" max={points.length - 1} value={Math.min(index, points.length - 1)} onChange={e => { setPlaying(false); setIndex(Number(e.target.value)) }} /></label><output>t = {fmt(selected?.t)} s · x = {fmt(selected?.x)} m · y = {fmt(selected?.y)} m</output></div>}
    {prediction.length > 0 && <label className="check-row"><input type="checkbox" checked={showPrediction} onChange={e => setShowPrediction(e.target.checked)} />Show preregistered prediction (dashed)</label>}
    <p>{points.length ? "Blue points are measurements also available to the agent. Lines connect samples and add no observations. Each axis has its own scale." : failed ? "The laboratory returned no valid measurements. No trajectory is invented." : "The point marks the starting position; the arrow shows only the initial velocity direction. Motion becomes visible after the experiment runs."}</p>
  </figure>
}

export function PublicExperiment({ events }: { events: LabEvent[] }) {
  const scene = experimentScene(events)
  return <section className="public-experiment" aria-label={"Experiment visible to the agent"}><div className="section-heading"><h2>The experiment you and the agent share</h2><span className="data-badge">Public data only</span></div>{scene.purpose && <p><strong>Purpose:</strong> {scene.purpose}</p>}{scene.modified && <p>These settings include the operator's changes. The model receives them before making its prediction.</p>}<ExperimentStage {...scene} label={scene.requestId ? referenceName(events, 'experiment_request', scene.requestId) : "The apparatus is ready"} /><details><summary>What does the AI actually receive?</summary><p>Initial conditions, requested times, decisions and numerical measurements from the history. This graph is for you; it is not sent to the model as an image. The true law and private configuration remain hidden.</p>{scene.experiment && <dl className="experiment-summary"><div><dt>Starting position (x, y)</dt><dd>{fmt(scene.experiment.initial_position.x)}, {fmt(scene.experiment.initial_position.y)} m</dd></div><div><dt>Velocity (vx, vy)</dt><dd>{fmt(scene.experiment.initial_velocity.x)}, {fmt(scene.experiment.initial_velocity.y)} m/s</dd></div><div><dt>Duration / interval</dt><dd>{fmt(scene.experiment.duration)} / {fmt(scene.experiment.observation_interval)} s</dd></div></dl>}</details></section>
}

export type ActivityKind = 'model' | 'world' | 'experiment' | 'sync'
export function Activity({ kind }: { kind: ActivityKind }) {
  const [seconds, setSeconds] = useState(0)
  useEffect(() => { setSeconds(0); const start = Date.now(); const timer = window.setInterval(() => setSeconds(Math.floor((Date.now() - start) / 1000)), 1000); return () => window.clearInterval(timer) }, [kind])
  const content = {
    model: ["The agent is preparing a response", "It receives the public history and available observations. Its private reasoning is not visible. No experiment runs while you wait."],
    world: ["The laboratory is preparing your world", "The server generates and validates the candidate before creating it. The animation indicates waiting, not a completion percentage."],
    experiment: ["Experiment running", "You authorized this experiment. Waiting for measurements from the laboratory; none are shown early or invented."],
    sync: ["Updating the laboratory", "Wait for the server to confirm before taking another action."],
  }[kind]
  return <section className={`lab-activity activity-${kind}`} aria-busy="true"><div className="activity-instrument" aria-hidden="true"><span /><span /><span /></div><div><h3 role="status">{content[0]}</h3><p>{content[1]}</p><small>Time elapsed: {seconds} s</small></div></section>
}

export function NextStep({ status, managed = false, restricted = false }: { status: string; managed?: boolean; restricted?: boolean }) {
  const text: Record<string, [string, string]> = {
    discovering: [managed ? "Ask the agent for its next step" : "Design your next experiment", managed ? "Choose Ask for next step: one call, one message. The agent can propose an experiment, record a hypothesis or conclude." : "Set a purpose and initial conditions. You can also record a hypothesis or conclude that the information is insufficient."],
    awaiting_decision: ["Decide what to run", restricted ? "Read the purpose and settings. This trial keeps conditions fixed: use the available decisions without changes or theoretical hints. Silence is never approval." : "Read the purpose and settings, then approve, modify or reject. Silence is never approval."],
    awaiting_mode: ["Choose what you want to learn", "Exploration gathers information. Verification compares measurements with predicted positions recorded before the experiment runs."],
    awaiting_prediction: ["Record the predicted positions", managed ? "Ask the agent for a step. It must predict using the final approved settings before you can run the experiment." : "Select a hypothesis and enter x and y for each time. Predictions are locked and cannot be changed after measuring."],
    ready_to_run: ["Ready: authorize the experiment", "Run experiment uses one experiment from your budget, even if the trajectory fails. Your earlier approval has not run it yet."],
    awaiting_answer: ["The agent has a question for you", "Answer in the form below. Theoretical hints can influence the investigation and will be recorded."],
    awaiting_submission: ["Investigation concluded: test new states", "New test states are available. Submit numerical accelerations. Errors are evaluated separately, without a combined score."],
    scoring_pending: ["Your answer is locked", "Complete the evaluation when it is available. No experiment will be repeated."],
    scored: ["Results available", "Review measurements and hypotheses in the history. Low error supports predictions on the evaluated states; it does not prove a law for every possible state."],
    stopped: ["Investigation stopped", "The history remains available. Stopping is not a scientific conclusion from the agent."],
    execution_started: ["Experiment interrupted: check the history", "Do not run it again automatically. Stop the investigation to close the interrupted execution."],
    revealed: ["World revealed", "The private law is now visible to the operator. This investigation is no longer a blind test."],
  }
  const current = text[status]
  return current && <section className="next-step"><h2>{current[0]}</h2><p>{current[1]}</p></section>
}
