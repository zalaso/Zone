import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { accountTransport, ApiError, request } from './api'
import { Workspace } from './Workspace'
import { PublicAccess } from './PublicAccess'

type Role = 'admin' | 'operator' | 'member'
type Quotas = Record<'sessions' | 'experiments' | 'model_calls' | 'read' | 'write' | 'run', number>
export type Account = { account_id: string; handle: string; role: Role; enabled: boolean; key_expires_at: number; quotas: Quotas; usage: Pick<Quotas, 'sessions' | 'experiments' | 'model_calls'> }
const IdentityContext = createContext<Account | null>(null)
const PublicWorkspaceContext = createContext(false)
export function usePublicWorkspace() { return useContext(PublicWorkspaceContext) }
export function useIdentity() { return useContext(IdentityContext) }
const defaults: Quotas = { sessions: 30, experiments: 100, model_calls: 50, read: 120, write: 30, run: 10 }
const quotaLabels: Record<keyof Quotas, string> = { sessions: "Total investigations", experiments: "Total experiments",
  model_calls: "Total model calls", read: "Reads per minute", write: "Writes per minute", run: "Experiments per minute" }

export function IdentityGate({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<'loading' | 'local' | 'accounts'>('loading')
  const [account, setAccount] = useState<Account | null>(null)
  const [key, setKey] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [sessions, setSessions] = useState<{ session_id: string; mode: string }[]>([])
  const [after, setAfter] = useState(0)
  const [hasMore, setHasMore] = useState(true)
  const [publicWorkspace, setPublicWorkspace] = useState(false)
  const [registrationOpen, setRegistrationOpen] = useState(false)
  useEffect(() => {
    let alive = true
    const expired = () => { setAccount(null); setKey(''); setSessions([]); setAfter(0); setHasMore(true); accountTransport(true) }
    window.addEventListener('zone-auth-expired', expired)
    void request<{ mode: 'local' | 'accounts'; public_workspace?: boolean; registration_open?: boolean }>('/auth/config').then(async data => {
      if (!alive) return
      setMode(data.mode); accountTransport(data.mode === 'accounts')
      setPublicWorkspace(data.public_workspace === true); setRegistrationOpen(data.registration_open === true)
      if (data.mode === 'accounts') {
        try {
          const me = await request<{ account: Account; csrf: string }>('/auth/me')
          if (alive) { setAccount(me.account); accountTransport(true, me.csrf) }
        } catch (e) { if (alive && !(e instanceof ApiError && e.status === 401)) setError(e instanceof Error ? e.message : "Sign-in is unavailable. Please try again.") }
      }
    }).catch(e => { if (alive) setError(e.message) })
    return () => { alive = false; window.removeEventListener('zone-auth-expired', expired) }
  }, [])
  async function act(work: () => Promise<void>) {
    setBusy(true); setError('')
    try { await work() } catch (e) { setError(e instanceof Error ? e.message : "This action could not be completed.") }
    finally { setBusy(false) }
  }
  if (mode === 'local') return children
  if (mode === 'loading') return <main className="app-shell"><p role="status">Connecting to the laboratory…</p>{error && <p role="alert">{error} Reload the page to try again.</p>}</main>
  if (publicWorkspace && !account) return <PublicAccess registrationOpen={registrationOpen} onLogin={(user, csrf) => { setAccount(user); accountTransport(true, csrf) }} />
  if (publicWorkspace && account) return <IdentityContext.Provider value={account}><PublicWorkspaceContext.Provider value={true}><Workspace account={account} admin={account.role === 'admin' ? <AdminAccounts /> : null} logout={() => void act(async () => {
    await request('/auth/logout', 'POST', {}); accountTransport(true); setAccount(null)
  })}>{children}</Workspace>{error && <p className="error" role="alert">{error}</p>}</PublicWorkspaceContext.Provider></IdentityContext.Provider>
  if (!account) return <main className="app-shell"><section className="panel"><span className="kicker">Zone · invitation access</span><h1>Enter the laboratory</h1><p>Use the access key from your administrator. Never send it to a model.</p>
    <form onSubmit={e => { e.preventDefault(); void act(async () => {
      try {
        const data = await request<{ account: Account; csrf: string }>('/auth/login', 'POST', { login_key: key })
        accountTransport(true, data.csrf); setAccount(data.account)
      } finally { setKey('') }
    }) }}><label>Access key<input type="password" autoComplete="off" required value={key} onChange={e => setKey(e.target.value)} /></label><button className="button primary" disabled={busy}>Sign in</button></form>
    <p className="field-hint">Your key is not saved in browser storage. The login expires after 30 minutes of inactivity or eight hours in total.</p>{error && <p role="alert" className="error">{error}</p>}</section></main>
  return <IdentityContext.Provider value={account}><section className="app-shell"><div className="panel"><span className="kicker">ACCOUNT / {account.role}</span><h2>{account.handle}</h2>
    <p>{account.usage.sessions}/{account.quotas.sessions} investigations · {account.usage.experiments}/{account.quotas.experiments} experiments · {account.usage.model_calls}/{account.quotas.model_calls} model calls</p>
    <div className="button-row"><button className="button secondary" disabled={busy} onClick={() => void act(async () => {
      const data = await request<{ account: Account; csrf: string }>('/auth/me'); setAccount(data.account); accountTransport(true, data.csrf)
    })}>Refresh usage</button><button className="button secondary" disabled={busy} onClick={() => void act(async () => {
      await request('/auth/logout', 'POST', {}); accountTransport(true); setAccount(null); setSessions([]); setAfter(0); setHasMore(true)
    })}>Sign out</button></div>
    <details><summary>My investigations</summary><p>Use the investigation identifier in the laboratory's advanced Open a history form.</p><ul>{sessions.map(s => <li key={s.session_id}><code>{s.session_id}</code> · {s.mode}</li>)}</ul><button className="button tiny" disabled={busy} onClick={() => void act(async () => {
      const page = await request<{ sessions: typeof sessions; next_after: number }>(`/my/sessions?after=${after}`)
      setSessions(current => [...current, ...page.sessions]); setAfter(page.next_after); setHasMore(page.sessions.length === 100)
    })}>{after ? hasMore ? "Load more investigations" : "Refresh list" : "Load investigations"}</button></details>{error && <p role="alert" className="error">{error}</p>}
  </div>{account.role === 'admin' && <AdminAccounts />}</section>{children}</IdentityContext.Provider>
}

function AdminAccounts() {
  const [accounts, setAccounts] = useState<Account[]>([])
  const [after, setAfter] = useState(0)
  const [handle, setHandle] = useState('')
  const [selected, setSelected] = useState('')
  const [role, setRole] = useState<Role>('member')
  const [enabled, setEnabled] = useState(true)
  const [quotas, setQuotas] = useState<Quotas>(defaults)
  const [issued, setIssued] = useState('')
  const [showIssued, setShowIssued] = useState(false)
  const [agentId, setAgentId] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  async function act(work: () => Promise<void>) {
    setBusy(true); setError(''); setIssued(''); setShowIssued(false)
    try { await work() } catch (e) { setError(e instanceof Error ? e.message : "This action could not be completed.") }
    finally { setBusy(false) }
  }
  return <details className="panel"><summary>Account administration</summary><p>Manage invited accounts. Disabling an account revokes access. Changing a role or limits signs out browser sessions without resetting usage.</p>
    <button className="button tiny" disabled={busy} onClick={() => void act(async () => {
      const page = await request<{ accounts: Account[]; next_after: number }>(`/admin/accounts?after=${after}`)
      setAccounts(current => [...current, ...page.accounts]); setAfter(page.next_after)
    })}>Load accounts / next page</button>
    <label>Account to manage<select aria-label={"Account to manage"} value={selected} onChange={e => {
      setSelected(e.target.value); setIssued('')
      const target = accounts.find(a => a.account_id === e.target.value)
      setHandle(target?.handle ?? ''); setRole(target?.role ?? 'member'); setEnabled(target?.enabled ?? true); setQuotas(target?.quotas ?? defaults)
    }}><option value="">New account</option>{accounts.map(a => <option key={a.account_id} value={a.account_id}>{a.handle} · {a.role} · {a.enabled ? 'active' : 'disabled'}</option>)}</select></label>
    <form onSubmit={e => { e.preventDefault(); void act(async () => {
      if (selected) {
        await request(`/admin/accounts/${selected}`, 'POST', { role, enabled, quotas })
      } else {
        const data = await request<Account & { login_key: string }>('/admin/accounts', 'POST', { handle, role, quotas })
        setIssued(data.login_key)
      }
      const page = await request<{ accounts: Account[]; next_after: number }>('/admin/accounts')
      setAccounts(page.accounts); setAfter(page.next_after)
    }) }}><label>Account name<input value={handle} onChange={e => setHandle(e.target.value)} disabled={!!selected} required pattern="[a-z][a-z0-9_-]{2,47}" /></label>
    <label>Role<select aria-label={"Account role"} value={role} onChange={e => setRole(e.target.value as Role)}>{(['member', 'operator', 'admin'] as const).map(r => <option key={r}>{r}</option>)}</select></label>
    {selected && <label className="check-row"><input type="checkbox" checked={enabled} onChange={e => setEnabled(e.target.checked)} />Account enabled</label>}
    <fieldset className="field-grid"><legend>Total quotas and requests per minute</legend>{(Object.keys(defaults) as (keyof Quotas)[]).map(name => <label key={name}>{quotaLabels[name]}<input type="number" min="0" max="1000000" required value={quotas[name]} onChange={e => setQuotas({ ...quotas, [name]: e.target.valueAsNumber })} /></label>)}</fieldset>
    <button className="button primary" disabled={busy}>{selected ? "Save role, status and limits" : "Create invited account"}</button></form>
    {selected && <><button className="button danger" disabled={busy} onClick={() => void act(async () => {
      const data = await request<{ login_key: string }>(`/admin/accounts/${selected}/rotate`, 'POST', { ttl_seconds: 2592000 }); setIssued(data.login_key)
    })}>Rotate access key and sign out sessions</button><form onSubmit={e => { e.preventDefault(); void act(async () => { await request(`/admin/accounts/${selected}/arena/${agentId}`, 'POST', {}); setAgentId('') }) }}>
      <label>Arena agent identifier to link<input value={agentId} onChange={e => setAgentId(e.target.value)} pattern="[0-9a-f]{32}" required /></label><button className="button secondary" disabled={busy}>Link agent before starting trials</button></form></>}
    {issued && <div className="notice"><p>This key is shown only once. Share it with the intended recipient through a secure channel.</p><label>New access key<input readOnly type={showIssued ? 'text' : 'password'} autoComplete="off" value={issued} /></label><button className="button tiny" onClick={() => setShowIssued(value => !value)}>{showIssued ? "Hide key" : "Show key"}</button><button className="button tiny" onClick={() => void navigator.clipboard.writeText(issued).catch(() => setError("Copy unavailable. Reveal and select the key in the field."))}>Copy key</button><button className="button tiny" onClick={() => setIssued('')}>Hide and forget</button></div>}
    {error && <p role="alert" className="error">{error}</p>}
  </details>
}
