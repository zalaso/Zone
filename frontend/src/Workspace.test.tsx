import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { IdentityGate } from './Identity'
import { Connections } from './Connections'
import { PersonalArena } from './PersonalArena'
import { accountTransport } from './api'

afterEach(() => { cleanup(); accountTransport(false); vi.unstubAllGlobals() })
const account = { account_id: 'a'.repeat(32), handle: 'alice', role: 'member', enabled: true,
  quotas: { sessions: 30, experiments: 100, model_calls: 50, read: 120, write: 30, run: 10 },
  usage: { sessions: 0, experiments: 0, model_calls: 0 } }

it('registra senza chiavi AI e richiede di conservare il recupero prima di entrare', async () => {
  const fetcher = vi.fn().mockImplementation(async (path: string, options: RequestInit) => {
    if (path.endsWith('/config')) return new Response('{"mode":"accounts","public_workspace":true,"registration_open":true}')
    if (path.endsWith('/me')) return new Response('{}', { status: 401 })
    expect(path).toBe('/v1/auth/register')
    expect(JSON.parse(options.body as string)).toEqual({ handle: 'alice', password: 'synthetic-password-123' })
    return new Response(JSON.stringify({ account, csrf: 'csrf', recovery_code: 'synthetic-recovery' }))
  })
  vi.stubGlobal('fetch', fetcher)
  const user = userEvent.setup()
  render(<IdentityGate><p>Indagine privata</p></IdentityGate>)
  await user.type(await screen.findByLabelText("Username"), 'alice')
  await user.type(screen.getByLabelText('Password'), 'synthetic-password-123')
  await user.click(screen.getByRole('button', { name: "Create account and continue" }))
  await screen.findByLabelText("Recovery code")
  expect(screen.queryByText('Indagine privata')).not.toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: "I have saved my code" }))
  await screen.findByRole('heading', { name: /Which universe/ })
  expect(screen.queryByLabelText("Recovery code")).not.toBeInTheDocument()
  expect(screen.queryByText("Account administration")).not.toBeInTheDocument()
})

it('salvare una API invia solo la configurazione della connessione e dimentica la chiave', async () => {
  const fetcher = vi.fn().mockImplementation(async (path: string, options: RequestInit) => {
    expect(path).toBe('/v1/my/connections')
    if (options.method === 'POST') {
      expect(JSON.parse(options.body as string)).toEqual({ label: 'OpenAI API', provider: 'openai', model: 'test-model', transport: 'api', api_key: 'synthetic-key' })
      return new Response('{"id":"a","connector_key":null}')
    }
    return new Response('{"connections":[],"selected":null,"api_enabled":true}')
  })
  vi.stubGlobal('fetch', fetcher)
  const user = userEvent.setup()
  render(<Connections />)
  await screen.findByText("No AI selected. You can still use the clearly labeled offline baseline.")
  await user.type(screen.getByLabelText("Model ID"), 'test-model')
  await user.type(screen.getByLabelText("Personal API key"), 'synthetic-key')
  await user.click(screen.getByRole('button', { name: "Save connection" }))
  await waitFor(() => expect(screen.getByLabelText("Personal API key")).toHaveValue(''))
  expect(fetcher.mock.calls.filter(([, o]) => o.method === 'POST')).toHaveLength(1)
})

it('ChatGPT prepara solo il connettore e spiega dove avviene il sign in', async () => {
  vi.stubGlobal('fetch', vi.fn().mockImplementation(async (_path: string, options: RequestInit) => {
    if (options.method === 'POST') {
      expect(JSON.parse(options.body as string)).toEqual({ label: 'ChatGPT', provider: 'chatgpt', model: 'my-model', transport: 'connector' })
      return new Response('{"id":"a","connector_key":"zc_synthetic_only"}')
    }
    return new Response('{"connections":[],"selected":null,"api_enabled":false}')
  }))
  const user = userEvent.setup()
  render(<Connections />)
  await user.click(screen.getByRole('button', { name: 'ChatGPT' }))
  expect(screen.queryByLabelText("Personal API key")).not.toBeInTheDocument()
  await user.type(screen.getByLabelText("Model ID"), 'my-model')
  await user.click(screen.getByRole('button', { name: "Set up Sign in with ChatGPT" }))
  await screen.findByLabelText("Connector key, shown only once")
  expect(screen.getByText(/python -m hidden_lab connector/)).toHaveTextContent('--login')
  await user.click(screen.getByRole('button', { name: "I have saved the key" }))
  expect(screen.queryByDisplayValue('zc_synthetic_only')).not.toBeInTheDocument()
})

it('Arena personale approva senza eseguire: modalità e lancio richiedono clic distinti', async () => {
  let state = { session_id: 'a'.repeat(32), version: 2, status: 'awaiting_decision', executed_experiments: 0,
    observations: 0, pending_request_id: 'e1', events: [], account: { name: 'My agent' } }
  const writes: string[] = []
  vi.stubGlobal('fetch', vi.fn().mockImplementation(async (path: string, options: RequestInit) => {
    if (options.method === 'POST') {
      writes.push(path)
      expect((options.headers as Record<string, string>)['Idempotency-Key']).toBeTruthy()
      const body = JSON.parse(options.body as string)
      state = { ...state, version: state.version + 1, status: body.message?.type === 'operator_decision' ? 'awaiting_mode' : 'ready_to_run' }
      return new Response(JSON.stringify(state))
    }
    if (path.endsWith('/challenges')) return new Response('{"challenges":[]}')
    if (path.endsWith('/my/arena')) return new Response('{"agents":[],"trials":[]}')
    return new Response(JSON.stringify(state))
  }))
  const user = userEvent.setup()
  render(<PersonalArena initialSession={state.session_id} />)
  await screen.findByRole('heading', { name: 'Decide what to run' })
  await user.click(await screen.findByRole('button', { name: "Approve proposal" }))
  await user.click(await screen.findByRole('button', { name: "Confirm Arena exploration" }))
  await screen.findByRole('button', { name: "Run this experiment" })
  expect(writes).toHaveLength(2)
  expect(writes.every(path => path.endsWith('/messages'))).toBe(true)
})
