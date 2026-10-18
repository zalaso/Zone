import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import App from './App'
import type { LabEvent, SessionStatus } from './types'

const fake = vi.hoisted(() => ({ events: [] as LabEvent[], state: 'discovering', pendingId: '', runCalls: 0, revealCalls: 0, lastMessage: null as Record<string, unknown> | null }))
const sessionId = 'a'.repeat(32)
const experiment = { initial_position: { x: 0, y: 0 }, initial_velocity: { x: 0, y: 0 }, duration: 1, observation_interval: 0.25 }
const probe = { probe_id: 'p1', category: 'interpolation', x: 1, y: 2, vx: 3, vy: 4 }
function add(actor: LabEvent['actor'], message: Record<string, unknown> & { type: string }) { fake.events.push({ seq: fake.events.length + 1, actor, message }) }
function status(): SessionStatus { return { session_id: sessionId, version: fake.events.length, status: fake.state,
  executed_experiments: fake.runCalls, remaining_experiments: 3 - fake.runCalls,
  pending_request_id: ['awaiting_decision', 'awaiting_mode', 'awaiting_prediction', 'ready_to_run'].includes(fake.state) ? fake.pendingId : null,
  pending_question_id: null, running_request_id: null, challenge_available: ['awaiting_submission', 'scored'].includes(fake.state),
  result_available: fake.state === 'scored', revealed: false } }
vi.mock('./api', () => ({
  ApiError: class extends Error { constructor(message: string, public status: number) { super(message) } },
  api: {
    modes: vi.fn(async () => ({ modes: [], agent: { provider: 'offline_baseline', model: 'offline-affine-v1', real_model: false, settings: { max_calls: 20, max_turns: 15, max_points: 9, max_corrections: 2, timeout: 30 } } })),
    worlds: vi.fn(async () => [{ world_id: 'w1234567890abcdef', level: 1, experiment_budget: 3 }]),
    create: vi.fn(async () => ({ ...status(), agent_token: 'agent-secret' })),
    status: vi.fn(async () => status()),
    events: vi.fn(async () => [...fake.events]),
    result: vi.fn(async () => ({ prediction: { acceleration_rmse: 0.5, by_category: { interpolation: { acceleration_rmse: 0.5 } } }, functional: null })),
    message: vi.fn(async (_id: string, _v: number, m: Record<string, unknown>) => {
      fake.lastMessage = m
      const type = m.type
      add(type === 'operator_decision' || type === 'execution_mode' ? 'operator' : 'agent', m as LabEvent['message'])
      if (type === 'experiment_request') { fake.pendingId = String(m.request_id); fake.state = 'awaiting_decision' }
      if (type === 'operator_decision') fake.state = m.action === 'reject' ? 'discovering' : 'awaiting_mode'
      if (type === 'execution_mode') fake.state = m.mode === 'verification' ? 'awaiting_prediction' : 'ready_to_run'
      if (type === 'prediction') fake.state = 'ready_to_run'
      if (type === 'conclusion') { fake.state = 'awaiting_submission'; add('apparatus', { type: 'probe_challenge', world_id: 'w1234567890abcdef', probes: [probe] }) }
      return status()
    }),
    run: vi.fn(async () => { fake.runCalls++; add('operator', { type: 'execution_started', request_id: 'e1', experiment, executed_count: 1 }); add('apparatus', { type: 'observation', request_id: 'e1', status: 'ok', points: [{ t: 0, x: 0, y: 0 }, { t: 1, x: 1, y: 1 }] }); fake.state = 'discovering'; return status() }),
    submit: vi.fn(async () => { fake.state = 'scored'; add('agent', { type: 'scientific_submission', predictions: [{ probe_id: 'p1', ax: 0, ay: 0 }] }); add('apparatus', { type: 'result_recorded', scores: {} }); return status() }),
    score: vi.fn(async () => status()), stop: vi.fn(async () => status()),
    reveal: vi.fn(async () => { fake.revealCalls++; return { world: {}, audit: {} } }),
  },
}))

beforeEach(() => { fake.events = []; fake.state = 'discovering'; fake.pendingId = ''; fake.runCalls = 0; fake.revealCalls = 0; fake.lastMessage = null; add('apparatus', { type: 'apparatus', experiment_budget: 3, coordinates: 'x/y' }) })
async function createSession() {
  render(<App />)
  await screen.findByRole('option', { name: /World 1/ })
  fireEvent.change(screen.getByLabelText("Operator token"), { target: { value: 'operator-secret' } })
  fireEvent.click(screen.getByRole('button', { name: /Create investigation/ }))
  await waitFor(() => expect(screen.getByText(sessionId)).toBeInTheDocument())
}
async function requestExperiment() {
  fireEvent.change(screen.getByLabelText("Experiment purpose"), { target: { value: 'Misurare la traiettoria' } })
  fireEvent.click(screen.getByRole('button', { name: "Submit proposal" }))
  await waitFor(() => expect(fake.state).toBe('awaiting_decision'))
}

describe('percorso locale del laboratorio', () => {
  it('una nuova sessione non eredita la decisione Modifica o le bozze dell’indagine precedente', async () => {
    await createSession(); await requestExperiment()
    const panel = screen.getByRole('heading', { name: "Review the proposal" }).closest('section')!
    fireEvent.click(within(panel).getByLabelText("Modify"))
    fireEvent.change(within(panel).getByLabelText("Reason"), { target: { value: 'Decisione della prima indagine' } })
    fireEvent.click(within(panel).getByRole('button', { name: "Save decision" }))
    await waitFor(() => expect(fake.state).toBe('awaiting_mode'))
    fireEvent.click(screen.getByText("New investigation and settings", { exact: true }))
    fake.state = 'discovering'; fake.pendingId = ''; fake.events = []
    fireEvent.click(screen.getByRole('button', { name: /Create investigation/ }))
    await screen.findByRole('heading', { name: "Propose an experiment" })
    expect(screen.getByLabelText("Experiment purpose")).toHaveValue('')
    await requestExperiment()
    const nextPanel = screen.getByRole('heading', { name: "Review the proposal" }).closest('section')!
    expect(within(nextPanel).getByLabelText("Approve")).toBeChecked()
    expect(within(nextPanel).getByLabelText("Reason")).toHaveValue('')
    expect(within(nextPanel).queryByLabelText("Duration (s)")).not.toBeInTheDocument()
  })
  it('separa il cambio percorso dall’indagine attiva e conserva il registro', async () => {
    await createSession()
    fireEvent(window, new CustomEvent('zone-select-mode', { detail: 'build_universe' }))
    await screen.findByRole('heading', { name: "Build a universe" })
    expect(screen.queryByRole('heading', { name: "Propose an experiment" })).not.toBeInTheDocument()
    fireEvent.click(screen.getByText("New investigation and settings", { exact: true }))
    await screen.findByRole('heading', { name: "Propose an experiment" })
    expect(screen.getByText(sessionId)).toBeInTheDocument()
  })
  it('richiede approvazione e lancio espliciti, poi mostra misure, challenge e risultato', async () => {
    await createSession(); await requestExperiment()
    expect(fake.runCalls).toBe(0)
    const decisionPanel = screen.getByRole('heading', { name: "Review the proposal" }).closest('section')!
    fireEvent.change(within(decisionPanel).getByLabelText("Reason"), { target: { value: 'Parametri validi' } })
    fireEvent.click(within(decisionPanel).getByRole('button', { name: "Save decision" }))
    await waitFor(() => expect(fake.state).toBe('awaiting_mode'))
    expect(fake.runCalls).toBe(0)
    fireEvent.click(screen.getByRole('button', { name: "Exploration" }))
    await waitFor(() => expect(fake.state).toBe('ready_to_run'))
    expect(fake.runCalls).toBe(0)
    fireEvent.click(screen.getByRole('button', { name: /Run experiment/ }))
    await waitFor(() => expect(fake.runCalls).toBe(1))
    await screen.findByText('2 measurements recorded')
    fireEvent.click(screen.getByText("Record a hypothesis or ask a question", { exact: true }))
    fireEvent.change(screen.getByLabelText("Hypothesis"), { target: { value: 'Accelerazione costante' } })
    fireEvent.click(screen.getByRole('button', { name: "Save hypothesis" }))
    await waitFor(() => expect(fake.lastMessage?.type).toBe('hypothesis'))
    fireEvent.click(screen.getByText("Conclude and take the final test", { exact: true }))
    fireEvent.change(screen.getByLabelText("Conclusion"), { target: { value: 'La legge sembra costante' } })
    fireEvent.change(screen.getByLabelText(/Limits/), { target: { value: 'Solo un lancio' } })
    fireEvent.click(screen.getByRole('button', { name: "Save conclusion" }))
    await waitFor(() => expect(fake.state).toBe('awaiting_submission'))
    expect(screen.getByText(/True accelerations remain hidden/)).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('ax for state 1'), { target: { value: '0.1' } })
    fireEvent.change(screen.getByLabelText('ay for state 1'), { target: { value: '-9.8' } })
    fireEvent.click(screen.getByRole('button', { name: "Submit predictions" }))
    await waitFor(() => expect(fake.state).toBe('scored'))
    expect(await screen.findByText("Numerical prediction")).toBeInTheDocument()
    expect(fake.revealCalls).toBe(0)
    expect(screen.getByRole('button', { name: "Reveal world" })).toBeDisabled()
  })

  it('registra un rifiuto e una modifica senza eseguire il lancio', async () => {
    await createSession(); await requestExperiment()
    const panel = screen.getByRole('heading', { name: "Review the proposal" }).closest('section')!
    fireEvent.click(within(panel).getByLabelText("Reject"))
    fireEvent.change(within(panel).getByLabelText("Reason"), { target: { value: 'Serve un controllo' } })
    fireEvent.click(within(panel).getByRole('button', { name: "Save decision" }))
    await waitFor(() => expect(fake.state).toBe('discovering'))
    expect(fake.lastMessage).toMatchObject({ type: 'operator_decision', action: 'reject' })
    expect(fake.runCalls).toBe(0)
    await requestExperiment()
    const nextPanel = screen.getByRole('heading', { name: "Review the proposal" }).closest('section')!
    fireEvent.click(within(nextPanel).getByLabelText("Modify"))
    fireEvent.change(within(nextPanel).getByLabelText("Velocity x (m/s)"), { target: { value: '3' } })
    fireEvent.change(within(nextPanel).getByLabelText("Reason"), { target: { value: 'Confronto controllato' } })
    fireEvent.click(within(nextPanel).getByRole('button', { name: "Save decision" }))
    await waitFor(() => expect(fake.state).toBe('awaiting_mode'))
    expect(fake.lastMessage).toMatchObject({ action: 'modify', modified_experiment: { initial_velocity: { x: 3, y: 0 } } })
    expect(fake.runCalls).toBe(0)
  })

  it('usa i parametri modificati per i tempi della previsione preregistrata', async () => {
    await createSession(); await requestExperiment()
    const panel = screen.getByRole('heading', { name: "Review the proposal" }).closest('section')!
    fireEvent.click(within(panel).getByLabelText("Modify"))
    fireEvent.change(within(panel).getByLabelText("Duration (s)"), { target: { value: '0.5' } })
    fireEvent.change(within(panel).getByLabelText("Reason"), { target: { value: 'Verifica più breve' } })
    fireEvent.click(within(panel).getByRole('button', { name: "Save decision" }))
    await waitFor(() => expect(fake.state).toBe('awaiting_mode'))
    fireEvent.click(screen.getByRole('button', { name: "Verification with a prediction" }))
    await waitFor(() => expect(fake.state).toBe('awaiting_prediction'))
    expect(screen.getByText("Record a hypothesis first.")).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText("Hypothesis"), { target: { value: 'Moto uniforme' } })
    fireEvent.click(screen.getByRole('button', { name: "Save hypothesis" }))
    const submit = await screen.findByRole('button', { name: "Preregister prediction" })
    for (const time of ['0', '0.25', '0.5']) {
      fireEvent.change(screen.getByLabelText(`x at ${time} seconds`), { target: { value: '1' } })
      fireEvent.change(screen.getByLabelText(`y at ${time} seconds`), { target: { value: '2' } })
    }
    fireEvent.click(submit)
    await waitFor(() => expect(fake.lastMessage?.type).toBe('prediction'))
    expect(fake.lastMessage?.points).toEqual([{ t: 0, x: 1, y: 2 }, { t: 0.25, x: 1, y: 2 }, { t: 0.5, x: 1, y: 2 }])
    expect(fake.runCalls).toBe(0)
  })
})
