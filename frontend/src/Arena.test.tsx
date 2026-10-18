import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, expect, it, vi } from 'vitest'
import { Arena } from './Arena'
import { arenaApi } from './arena-api'

const fake = vi.hoisted(() => ({ phase: 'awaiting_decision', runCalls: 0 }))
const challenge = { challenge_id: 'challenge', name: 'Trial pubblico', world_id: 'w1234567890abcdef', closed: false, rules: { experiment_budget: 2, max_messages: 30, max_points: 9, execution_policy: 'exploration_only' } }
const account = { agent_id: 'agent', name: 'Agente offline', model: 'offline', kind: 'offline_baseline', quotas: { sessions: 4, requests: 100, experiments: 12 }, usage: { sessions: 1, requests: 2, experiments: 0, invalid: 0 }, tokens: [{ token_id: 'token0123456789', expires_at: 2000000000, revoked: false }] }
function trial() { return { session_id: 'session', challenge_id: 'challenge', agent_id: 'agent', status: fake.phase, version: 2, account, messages: 1, observations: 0, executed_experiments: fake.runCalls, pending_request_id: 'e1', resources: { agent_requests: 1, invalid_requests: 0 }, scores: null, events: [] } }
vi.mock('./arena-api', () => ({ arenaApi: {
  read: vi.fn(async (path: string) => path === 'challenges' ? { challenges: [challenge] } : path === 'agents' ? { agents: [account] } : path.endsWith('/trials') ? { trials: [trial()] } : path.endsWith('/leaderboard') ? { challenge, trials: [trial()], dimensions: { acceleration_rmse: [], interpolation_rmse: [], extrapolation_rmse: [] } } : trial()),
  write: vi.fn(async (path: string, body: { message?: { type: string } }) => {
    if (path.endsWith('/run')) { fake.runCalls++; fake.phase = 'discovering' }
    else if (body.message?.type === 'operator_decision') fake.phase = 'awaiting_mode'
    else if (body.message?.type === 'execution_mode') fake.phase = 'ready_to_run'
    return trial()
  }),
} }))
beforeEach(() => { fake.phase = 'awaiting_decision'; fake.runCalls = 0; vi.clearAllMocks() })

it('rilegge e approva senza lanciare, richiede modalità e clic di esecuzione separati', async () => {
  const local = vi.spyOn(Storage.prototype, 'setItem')
  render(<Arena worlds={[{ world_id: 'w1234567890abcdef', experiment_budget: 2 }]} />)
  fireEvent.change(screen.getByLabelText("Arena operator token"), { target: { value: 'operator-test' } })
  fireEvent.click(screen.getByRole('button', { name: "Connect to Arena" }))
  fireEvent.click(await screen.findByRole('button', { name: 'Agente offline · Decision needed' }))
  fireEvent.click(await screen.findByRole('button', { name: "Approve Arena proposal" }))
  fireEvent.click(await screen.findByRole('button', { name: "Confirm Arena exploration" }))
  await screen.findByRole('button', { name: "Run Arena experiment" })
  expect(fake.runCalls).toBe(0)
  fireEvent.click(screen.getByRole('button', { name: "Run Arena experiment" }))
  await waitFor(() => expect(fake.runCalls).toBe(1))
  expect(local).not.toHaveBeenCalled()
  local.mockRestore()
})

it('mostra classifiche separate, quote e controllo di revoca', async () => {
  render(<Arena worlds={[{ world_id: 'w1234567890abcdef', experiment_budget: 2 }]} />)
  fireEvent.change(screen.getByLabelText("Arena operator token"), { target: { value: 'operator-test' } })
  fireEvent.click(screen.getByRole('button', { name: "Connect to Arena" }))
  await screen.findByText('Interpolation error (RMSE) · lower values rank first')
  expect(screen.getByText('Extrapolation error (RMSE) · lower values rank first')).toBeInTheDocument()
  expect(screen.getByText(/External client model calls, tokens and costs are not measured/)).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Revoke token 1' }))
  await waitFor(() => expect(arenaApi.write).toHaveBeenCalledWith('tokens/token0123456789/revoke', {}, 'operator-test'))
})

it('marca la contaminazione solo con un clic operatore e mostra il confronto diagnostico', async () => {
  render(<Arena worlds={[{ world_id: 'w1234567890abcdef', experiment_budget: 2 }]} />)
  fireEvent.change(screen.getByLabelText("Arena operator token"), { target: { value: 'operator-test' } })
  fireEvent.click(screen.getByRole('button', { name: "Connect to Arena" }))
  fireEvent.click(await screen.findByRole('button', { name: 'Agente offline · Decision needed' }))
  await screen.findByText(/Scope: Diagnostic comparison/)
  expect(arenaApi.write).not.toHaveBeenCalled()
  fireEvent.change(screen.getByLabelText("Contamination reason"), { target: { value: 'operator_hint' } })
  fireEvent.click(screen.getByRole('button', { name: "Mark as contaminated · irreversible" }))
  await waitFor(() => expect(arenaApi.write).toHaveBeenCalledWith('sessions/session/integrity', { expected_version: 2, reason: 'operator_hint' }, 'operator-test'))
  expect(fake.runCalls).toBe(0)
})

it('offre solo test nuovi e mondi diagnostici, esclude pratica pubblica e casi ritirati', () => {
  render(<Arena worlds={[
    { world_id: 'public', experiment_budget: 3, integrity: { state: 'public_practice', split: 'train' } },
    { world_id: 'retired', experiment_budget: 3, integrity: { state: 'retired', split: 'test' } },
    { world_id: 'blind', experiment_budget: 3, integrity: { state: 'blind_test', split: 'test' } },
  ]} />)
  const choices = screen.getByLabelText("Arena Forge world")
  expect(choices).toHaveValue('blind')
  expect(choices.querySelectorAll('option')).toHaveLength(1)
})
