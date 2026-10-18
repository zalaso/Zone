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
const quotaLabels: Record<keyof Quotas, string> = { sessions: 'Sessioni totali', experiments: 'Esperimenti totali',
  model_calls: 'Chiamate al modello totali', read: 'Letture al minuto', write: 'Scritture al minuto', run: 'Lanci al minuto' }

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
        } catch (e) { if (alive && !(e instanceof ApiError && e.status === 401)) setError(e instanceof Error ? e.message : 'Accesso non disponibile.') }
      }
    }).catch(e => { if (alive) setError(e.message) })
    return () => { alive = false; window.removeEventListener('zone-auth-expired', expired) }
  }, [])
  async function act(work: () => Promise<void>) {
    setBusy(true); setError('')
    try { await work() } catch (e) { setError(e instanceof Error ? e.message : 'Operazione non riuscita.') }
    finally { setBusy(false) }
  }
  if (mode === 'local') return children
  if (mode === 'loading') return <main className="app-shell"><p role="status">Connessione al laboratorio…</p>{error && <p role="alert">{error} Ricarica la pagina per riprovare.</p>}</main>
  if (publicWorkspace && !account) return <PublicAccess registrationOpen={registrationOpen} onLogin={(user, csrf) => { setAccount(user); accountTransport(true, csrf) }} />
  if (publicWorkspace && account) return <IdentityContext.Provider value={account}><PublicWorkspaceContext.Provider value={true}><Workspace account={account} admin={account.role === 'admin' ? <AdminAccounts /> : null} logout={() => void act(async () => {
    await request('/auth/logout', 'POST', {}); accountTransport(true); setAccount(null)
  })}>{children}</Workspace>{error && <p className="error" role="alert">{error}</p>}</PublicWorkspaceContext.Provider></IdentityContext.Provider>
  if (!account) return <main className="app-shell"><section className="panel"><span className="kicker">ZONE / ACCESSO SU INVITO</span><h1>Entra nel laboratorio</h1><p>Usa la chiave ricevuta dall’amministratore. Non inviarla al modello.</p>
    <form onSubmit={e => { e.preventDefault(); void act(async () => {
      try {
        const data = await request<{ account: Account; csrf: string }>('/auth/login', 'POST', { login_key: key })
        accountTransport(true, data.csrf); setAccount(data.account)
      } finally { setKey('') }
    }) }}><label>Chiave di accesso<input type="password" autoComplete="off" required value={key} onChange={e => setKey(e.target.value)} /></label><button className="button primary" disabled={busy}>Accedi</button></form>
    <p className="field-hint">La chiave non viene salvata nel browser. La sessione scade dopo 30 minuti di inattività, o al massimo dopo 8 ore.</p>{error && <p role="alert" className="error">{error}</p>}</section></main>
  return <IdentityContext.Provider value={account}><section className="app-shell"><div className="panel"><span className="kicker">ACCOUNT / {account.role}</span><h2>{account.handle}</h2>
    <p>{account.usage.sessions}/{account.quotas.sessions} sessioni · {account.usage.experiments}/{account.quotas.experiments} lanci · {account.usage.model_calls}/{account.quotas.model_calls} chiamate al modello</p>
    <div className="button-row"><button className="button secondary" disabled={busy} onClick={() => void act(async () => {
      const data = await request<{ account: Account; csrf: string }>('/auth/me'); setAccount(data.account); accountTransport(true, data.csrf)
    })}>Aggiorna utilizzo</button><button className="button secondary" disabled={busy} onClick={() => void act(async () => {
      await request('/auth/logout', 'POST', {}); accountTransport(true); setAccount(null); setSessions([]); setAfter(0); setHasMore(true)
    })}>Esci dall’account</button></div>
    <details><summary>Le mie sessioni</summary><p>Copia un ID nel campo “Apri un replay” del laboratorio.</p><ul>{sessions.map(s => <li key={s.session_id}><code>{s.session_id}</code> · {s.mode}</li>)}</ul><button className="button tiny" disabled={busy} onClick={() => void act(async () => {
      const page = await request<{ sessions: typeof sessions; next_after: number }>(`/my/sessions?after=${after}`)
      setSessions(current => [...current, ...page.sessions]); setAfter(page.next_after); setHasMore(page.sessions.length === 100)
    })}>{after ? hasMore ? 'Carica altre sessioni' : 'Aggiorna elenco' : 'Carica sessioni'}</button></details>{error && <p role="alert" className="error">{error}</p>}
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
    try { await work() } catch (e) { setError(e instanceof Error ? e.message : 'Operazione non riuscita.') }
    finally { setBusy(false) }
  }
  return <details className="panel"><summary>Amministrazione account</summary><p>Accesso su invito. La disabilitazione revoca gli accessi; una modifica a ruolo o quote chiude le sessioni browser. L’utilizzo non viene azzerato.</p>
    <button className="button tiny" disabled={busy} onClick={() => void act(async () => {
      const page = await request<{ accounts: Account[]; next_after: number }>(`/admin/accounts?after=${after}`)
      setAccounts(current => [...current, ...page.accounts]); setAfter(page.next_after)
    })}>Carica account / pagina successiva</button>
    <label>Account da gestire<select aria-label="Account da gestire" value={selected} onChange={e => {
      setSelected(e.target.value); setIssued('')
      const target = accounts.find(a => a.account_id === e.target.value)
      setHandle(target?.handle ?? ''); setRole(target?.role ?? 'member'); setEnabled(target?.enabled ?? true); setQuotas(target?.quotas ?? defaults)
    }}><option value="">Nuovo account</option>{accounts.map(a => <option key={a.account_id} value={a.account_id}>{a.handle} · {a.role} · {a.enabled ? 'attivo' : 'disabilitato'}</option>)}</select></label>
    <form onSubmit={e => { e.preventDefault(); void act(async () => {
      if (selected) {
        await request(`/admin/accounts/${selected}`, 'POST', { role, enabled, quotas })
      } else {
        const data = await request<Account & { login_key: string }>('/admin/accounts', 'POST', { handle, role, quotas })
        setIssued(data.login_key)
      }
      const page = await request<{ accounts: Account[]; next_after: number }>('/admin/accounts')
      setAccounts(page.accounts); setAfter(page.next_after)
    }) }}><label>Nome account<input value={handle} onChange={e => setHandle(e.target.value)} disabled={!!selected} required pattern="[a-z][a-z0-9_-]{2,47}" /></label>
    <label>Ruolo<select aria-label="Ruolo account" value={role} onChange={e => setRole(e.target.value as Role)}>{(['member', 'operator', 'admin'] as const).map(r => <option key={r}>{r}</option>)}</select></label>
    {selected && <label className="check-row"><input type="checkbox" checked={enabled} onChange={e => setEnabled(e.target.checked)} />Account abilitato</label>}
    <fieldset className="field-grid"><legend>Quote totali e richieste al minuto</legend>{(Object.keys(defaults) as (keyof Quotas)[]).map(name => <label key={name}>{quotaLabels[name]}<input type="number" min="0" max="1000000" required value={quotas[name]} onChange={e => setQuotas({ ...quotas, [name]: e.target.valueAsNumber })} /></label>)}</fieldset>
    <button className="button primary" disabled={busy}>{selected ? 'Salva ruolo, stato e quote' : 'Crea account invitato'}</button></form>
    {selected && <><button className="button danger" disabled={busy} onClick={() => void act(async () => {
      const data = await request<{ login_key: string }>(`/admin/accounts/${selected}/rotate`, 'POST', { ttl_seconds: 2592000 }); setIssued(data.login_key)
    })}>Ruota chiave e revoca sessioni</button><form onSubmit={e => { e.preventDefault(); void act(async () => { await request(`/admin/accounts/${selected}/arena/${agentId}`, 'POST', {}); setAgentId('') }) }}>
      <label>ID agente Arena da associare<input value={agentId} onChange={e => setAgentId(e.target.value)} pattern="[0-9a-f]{32}" required /></label><button className="button secondary" disabled={busy}>Associa agente prima dei trial</button></form></>}
    {issued && <div className="notice"><p>Chiave mostrata una sola volta. Consegnala al destinatario tramite un canale sicuro.</p><label>Nuova chiave<input readOnly type={showIssued ? 'text' : 'password'} autoComplete="off" value={issued} /></label><button className="button tiny" onClick={() => setShowIssued(value => !value)}>{showIssued ? 'Nascondi chiave' : 'Mostra chiave'}</button><button className="button tiny" onClick={() => void navigator.clipboard.writeText(issued).catch(() => setError('Copia non disponibile: mostra e seleziona la chiave nel campo.'))}>Copia chiave</button><button className="button tiny" onClick={() => setIssued('')}>Nascondi e dimentica</button></div>}
    {error && <p role="alert" className="error">{error}</p>}
  </details>
}
