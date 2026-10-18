import { useEffect, useId, useState } from 'react'
import type { Experiment, LabEvent } from './types'
import { asExperiment, asText, fmt } from './view'

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

export function ExperimentStage({ experiment, points = [], prediction = [], label = 'Vista dell’esperimento', failed = false }: {
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
  return <figure className="experiment-stage"><figcaption><strong>{label}</strong><span>{points.length ? 'Misure del laboratorio' : failed ? 'Lancio senza misure' : 'Condizioni iniziali · traiettoria sconosciuta'}</span></figcaption>
    <svg viewBox="0 0 600 285" role="img" aria-label={points.length ? `Traiettoria: ${points.length} campioni misurati. Punto selezionato a ${fmt(selected?.t)} secondi.` : 'Piano cartesiano con posizione iniziale e direzione della velocità. Nessuna traiettoria simulata.'}>
      <defs><marker id={markerId} markerWidth="7" markerHeight="7" refX="5" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6" fill="currentColor" /></marker></defs>
      {[0, 1, 2, 3, 4].map(i => <g className="plot-grid" key={i}><line x1={52 + i * 126.5} x2={52 + i * 126.5} y1="32" y2="246" /><line x1="52" x2="558" y1={32 + i * 53.5} y2={32 + i * 53.5} /></g>)}
      <g className="plot-axes"><line x1="52" x2="558" y1={y(0)} y2={y(0)} /><line x1={x(0)} x2={x(0)} y1="32" y2="246" /></g>
      <g className="plot-labels"><text x="558" y="278" textAnchor="end">x [m] →</text><text x="12" y="20">y [m] ↑</text><text x="52" y="265">{fmt(minX - padX)}</text><text x="558" y="265" textAnchor="end">{fmt(maxX + padX)}</text><text x="5" y="43">{fmt(maxY + padY)}</text><text x="5" y="246">{fmt(minY - padY)}</text></g>
      {showPrediction && prediction.length > 0 && <polyline className="predicted-path" points={prediction.map(p => `${x(p.x)},${y(p.y)}`).join(' ')} />}
      {points.length > 0 ? <><polyline className="observed-path" points={points.map(p => `${x(p.x)},${y(p.y)}`).join(' ')} />{points.map((p, i) => <circle className="sample-point" key={i} cx={x(p.x)} cy={y(p.y)} r="3" />)}{selected && <circle className="current-point" cx={x(selected.x)} cy={y(selected.y)} r="8" />}</> : initialFinite && <><circle className="current-point" cx={x(initial.x)} cy={y(initial.y)} r="8" />{magnitude > 0 && velocity && <line className="velocity-vector" x1={x(initial.x)} y1={y(initial.y)} x2={x(initial.x) + velocity.x / magnitude * 38} y2={y(initial.y) - velocity.y / magnitude * 38} markerEnd={`url(#${markerId})`} />}</>}
    </svg>
    {points.length > 0 && <div className="playback-controls"><button className="button secondary" onClick={() => { if (index >= points.length - 1) setIndex(0); setPlaying(!playing) }}>{playing ? 'Pausa replay' : 'Riproduci misure'}</button><label>Campione osservato<input type="range" min="0" max={points.length - 1} value={Math.min(index, points.length - 1)} onChange={e => { setPlaying(false); setIndex(Number(e.target.value)) }} /></label><output>t = {fmt(selected?.t)} s · x = {fmt(selected?.x)} m · y = {fmt(selected?.y)} m</output></div>}
    {prediction.length > 0 && <label className="check-row"><input type="checkbox" checked={showPrediction} onChange={e => setShowPrediction(e.target.checked)} />Mostra previsione preregistrata (tratteggio)</label>}
    <p>{points.length ? 'Punti blu: misure disponibili anche all’agente. Le linee uniscono i campioni, non aggiungono osservazioni. Assi con scale indipendenti.' : failed ? 'Il laboratorio non ha restituito misure valide. Nessuna traiettoria viene inventata.' : 'Il punto indica la partenza; la freccia mostra solo la direzione della velocità iniziale. Il moto diventa visibile dopo il lancio.'}</p>
  </figure>
}

export function PublicExperiment({ events }: { events: LabEvent[] }) {
  const scene = experimentScene(events)
  return <section className="public-experiment" aria-label="Esperimento visibile all’agente"><div className="section-heading"><h2>Lo stesso esperimento che vede l’agente</h2><span className="data-badge">Solo dati pubblici</span></div>{scene.purpose && <p><strong>Scopo:</strong> {scene.purpose}</p>}{scene.modified && <p>Parametri aggiornati dalla decisione dell’operatore: sono questi quelli comunicati al modello prima della previsione.</p>}<ExperimentStage {...scene} label={scene.requestId ? `Esperimento ${scene.requestId}` : 'L’apparato è pronto'} /><details><summary>Cosa riceve davvero l’AI?</summary><p>Condizioni iniziali, tempi richiesti, decisioni e misure numeriche del registro. Questo grafico è una rappresentazione per te: non viene inviato come immagine al modello. Legge vera e configurazione privata restano nascoste.</p>{scene.experiment && <dl className="experiment-summary"><div><dt>Partenza (x, y)</dt><dd>{fmt(scene.experiment.initial_position.x)}, {fmt(scene.experiment.initial_position.y)} m</dd></div><div><dt>Velocità (vx, vy)</dt><dd>{fmt(scene.experiment.initial_velocity.x)}, {fmt(scene.experiment.initial_velocity.y)} m/s</dd></div><div><dt>Durata / intervallo</dt><dd>{fmt(scene.experiment.duration)} / {fmt(scene.experiment.observation_interval)} s</dd></div></dl>}</details></section>
}

export type ActivityKind = 'model' | 'world' | 'experiment' | 'sync'
export function Activity({ kind }: { kind: ActivityKind }) {
  const [seconds, setSeconds] = useState(0)
  useEffect(() => { setSeconds(0); const start = Date.now(); const timer = window.setInterval(() => setSeconds(Math.floor((Date.now() - start) / 1000)), 1000); return () => window.clearInterval(timer) }, [kind])
  const content = {
    model: ['L’agente sta preparando una risposta', 'Sta ricevendo la storia pubblica e le osservazioni disponibili. Non vediamo il suo ragionamento interno. Nessun esperimento parte durante l’attesa.'],
    world: ['Il laboratorio sta preparando il mondo', 'Il server genera e valida il candidato prima di registrarlo. L’animazione indica attesa, non una percentuale di avanzamento.'],
    experiment: ['Esperimento in esecuzione', 'Il lancio è stato autorizzato. Attendiamo le misure del laboratorio: non vengono anticipate o inventate.'],
    sync: ['Aggiornamento del laboratorio', 'Attendi la conferma del server prima di compiere un’altra azione.'],
  }[kind]
  return <section className={`lab-activity activity-${kind}`} aria-busy="true"><div className="activity-instrument" aria-hidden="true"><span /><span /><span /></div><div><h3 role="status">{content[0]}</h3><p>{content[1]}</p><small>Attesa trascorsa: {seconds} s</small></div></section>
}

export function NextStep({ status, managed = false, restricted = false }: { status: string; managed?: boolean; restricted?: boolean }) {
  const text: Record<string, [string, string]> = {
    discovering: [managed ? 'Chiedi il prossimo passo all’agente' : 'Progetta il tuo prossimo esperimento', managed ? 'Premi Avanza agente: una chiamata, un messaggio. Può proporre un lancio, registrare un’ipotesi o concludere.' : 'Imposta lo scopo e le condizioni iniziali. Puoi anche registrare un’ipotesi o concludere con informazioni insufficienti.'],
    awaiting_decision: ['Controlla la proposta', restricted ? 'Leggi scopo e parametri. Questa prova mantiene fisse le condizioni: usa le decisioni disponibili, senza modifiche o suggerimenti teorici. Il silenzio non è un’approvazione.' : 'Leggi scopo e parametri, poi approva, modifica o rifiuta. Il silenzio non è un’approvazione.'],
    awaiting_mode: ['Scegli cosa vuoi imparare', 'Esplorazione raccoglie informazioni. Verifica confronta misure con posizioni previste e registrate prima del lancio.'],
    awaiting_prediction: ['Registra le posizioni previste', managed ? 'Chiedi un passo dell’agente. Deve prevedere sui parametri definitivi approvati; il lancio resta bloccato fino a quel momento.' : 'Seleziona un’ipotesi e inserisci x e y per ogni tempo. La previsione si congela e non potrà essere corretta dopo le misure.'],
    ready_to_run: ['Tutto pronto: autorizza il lancio', 'Il pulsante Esegui consuma un esperimento, anche se la traiettoria fallisce. L’approvazione precedente non lo ha ancora eseguito.'],
    awaiting_answer: ['L’agente ti ha fatto una domanda', 'Rispondi nel modulo. Suggerimenti teorici possono influenzare l’indagine e saranno registrati.'],
    awaiting_submission: ['L’indagine è conclusa: prova su stati nuovi', 'I probe sono stati pubblicati. Consegna accelerazioni numeriche; gli errori verranno valutati senza un punteggio unico.'],
    scoring_pending: ['La risposta è congelata', 'Completa la valutazione quando disponibile. Nessun esperimento verrà ripetuto.'],
    scored: ['Risultato disponibile', 'Rileggi misure e ipotesi nel replay. Un errore basso sostiene la previsione sui punti valutati, non prova una legge in ogni possibile stato.'],
    stopped: ['Indagine arrestata', 'I registri rimangono disponibili. Un arresto non equivale a una conclusione scientifica dell’agente.'],
    execution_started: ['Lancio interrotto: controlla il registro', 'Non rilanciare automaticamente. Usa l’arresto dell’indagine per chiudere l’esecuzione interrotta.'],
    revealed: ['Mondo rivelato', 'La legge privata è ora visibile all’operatore. Questa indagine non è più una prova cieca.'],
  }
  const current = text[status]
  return current && <section className="next-step"><h2>{current[0]}</h2><p>{current[1]}</p></section>
}
