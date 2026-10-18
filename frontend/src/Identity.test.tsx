import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { IdentityGate } from './Identity'
import { accountTransport } from './api'

afterEach(() => { cleanup(); accountTransport(false); vi.unstubAllGlobals() })
const account = { account_id: 'a'.repeat(32), handle: 'alice', role: 'member', enabled: true,
  quotas: { sessions: 30, experiments: 100, model_calls: 50, read: 120, write: 30, run: 10 },
  usage: { sessions: 1, experiments: 1, model_calls: 2 } }

it('il laboratorio resta smontato prima del login; la chiave è dimenticata e il logout smonta i dati', async () => {
  const fetcher = vi.fn().mockImplementation(async (path: string, options: RequestInit) => {
    if (path.endsWith('/config')) return new Response('{"mode":"accounts"}')
    if (path.endsWith('/me')) return new Response('{"detail":"Accesso richiesto"}', { status: 401 })
    if (path.endsWith('/login')) {
      expect(options.body).toBe('{"login_key":"synthetic-key"}')
      expect(options.credentials).toBe('same-origin')
      return new Response(JSON.stringify({ account, csrf: 'csrf-test' }))
    }
    if (path.endsWith('/logout')) {
      expect((options.headers as Record<string, string>)['X-Zone-CSRF']).toBe('csrf-test')
      return new Response('{"logged_out":true}')
    }
    throw new Error('Richiesta inattesa')
  })
  vi.stubGlobal('fetch', fetcher)
  const user = userEvent.setup()
  render(<IdentityGate><p>Laboratorio riservato</p></IdentityGate>)
  await screen.findByLabelText('Chiave di accesso')
  expect(screen.queryByText('Laboratorio riservato')).not.toBeInTheDocument()
  await user.type(screen.getByLabelText('Chiave di accesso'), 'synthetic-key')
  await user.click(screen.getByRole('button', { name: 'Accedi' }))
  await screen.findByText('Laboratorio riservato')
  expect(screen.queryByText('Amministrazione account')).not.toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Esci dall’account' }))
  await waitFor(() => expect(screen.queryByText('Laboratorio riservato')).not.toBeInTheDocument())
  expect(screen.getByLabelText('Chiave di accesso')).toHaveValue('')
})

it('ripristina il cookie e mostra l’amministrazione solo per admin; una revoca rimuove i dati', async () => {
  vi.stubGlobal('fetch', vi.fn().mockImplementation(async (path: string) => path.endsWith('/config')
    ? new Response('{"mode":"accounts"}')
    : new Response(JSON.stringify({ account: { ...account, role: 'admin' }, csrf: 'csrf-test' }))))
  render(<IdentityGate><p>Dati del laboratorio</p></IdentityGate>)
  await screen.findByText('Amministrazione account')
  window.dispatchEvent(new Event('zone-auth-expired'))
  await screen.findByLabelText('Chiave di accesso')
  expect(screen.queryByText('Dati del laboratorio')).not.toBeInTheDocument()
})

it('mantiene il percorso locale senza login', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{"mode":"local"}')))
  render(<IdentityGate><p>Laboratorio locale</p></IdentityGate>)
  await screen.findByText('Laboratorio locale')
  expect(screen.queryByLabelText('Chiave di accesso')).not.toBeInTheDocument()
})

it('crea inviti e aggiorna un account selezionabile dopo il refresh', async () => {
  const invited = { ...account, account_id: 'b'.repeat(32), handle: 'invited' }
  const fetcher = vi.fn().mockImplementation(async (path: string, options: RequestInit) => {
    if (path.endsWith('/config')) return new Response('{"mode":"accounts"}')
    if (path.endsWith('/me')) return new Response(JSON.stringify({ account: { ...account, role: 'admin' }, csrf: 'csrf-test' }))
    if (path.endsWith('/admin/accounts') && options.method === 'POST') return new Response(JSON.stringify({ ...invited, login_key: 'zk_synthetic_invite' }))
    if (path.endsWith('/admin/accounts')) return new Response(JSON.stringify({ accounts: [invited], next_after: 1 }))
    if (path.endsWith(invited.account_id)) {
      expect(JSON.parse(options.body as string)).toMatchObject({ role: 'operator', enabled: false, quotas: account.quotas })
      return new Response(JSON.stringify(invited))
    }
    throw new Error('Richiesta inattesa')
  })
  vi.stubGlobal('fetch', fetcher)
  const user = userEvent.setup()
  render(<IdentityGate><p>Laboratorio</p></IdentityGate>)
  await user.click(await screen.findByText('Amministrazione account'))
  await user.type(screen.getByLabelText('Nome account'), 'invited')
  await user.click(screen.getByRole('button', { name: 'Crea account invitato' }))
  expect(await screen.findByLabelText('Nuova chiave')).toHaveValue('zk_synthetic_invite')
  await user.click(screen.getByRole('button', { name: 'Nascondi e dimentica' }))
  await user.selectOptions(screen.getByLabelText('Account da gestire'), invited.account_id)
  await user.selectOptions(screen.getByLabelText('Ruolo account'), 'operator')
  await user.click(screen.getByLabelText('Account abilitato'))
  await user.click(screen.getByRole('button', { name: 'Salva ruolo, stato e quote' }))
  await waitFor(() => expect(fetcher.mock.calls.filter(([path]) => path.endsWith(invited.account_id))).toHaveLength(1))
})
