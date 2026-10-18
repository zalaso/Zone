import { useEffect, useState } from 'react'
import type { Account } from './Identity'
import { request } from './api'

export function Profile({ account, connect, sessions }: { account: Account; connect: () => void; sessions: () => void }) {
  const [stats, setStats] = useState(account)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [updated, setUpdated] = useState('')
  const [connection, setConnection] = useState("Loading connection…")
  useEffect(() => {
    let alive = true
    void request<{ connections: { id: string; label: string; model: string; enabled: number }[]; selected: string | null }>('/my/connections')
      .then(data => { const chosen = data.connections.find(c => c.enabled && c.id === data.selected); if (alive) setConnection(chosen ? `${chosen.label} · ${chosen.model}` : "Numerical offline baseline · not an LLM") })
      .catch(() => { if (alive) setConnection("Status unavailable. Check AI connections.") })
    return () => { alive = false }
  }, [])
  async function refresh() {
    setBusy(true); setError('')
    try { const data = await request<{ account: Account }>('/auth/me'); setStats(data.account); setUpdated(new Date().toLocaleTimeString('en-US')) }
    catch (e) { setError(e instanceof Error ? e.message : "Usage limits are unavailable. Try again.") }
    finally { setBusy(false) }
  }
  useEffect(() => { void refresh() }, [account.account_id])
  return <section className="profile-page"><div className="profile-heading"><span className="profile-avatar" aria-hidden="true">{account.handle.slice(0, 2).toUpperCase()}</span><div><h1>Your account</h1><p>@{account.handle} · {({ member: "Laboratory member", admin: "Administrator", operator: "Operator" })[account.role]}</p></div></div><p>Review your usage, selected model and account recovery options.</p><section className="profile-section"><div className="section-heading"><h2>Your laboratory</h2><button className="button secondary" onClick={sessions}>Open my investigations</button></div><p><strong>AI for new investigations:</strong> {connection}</p><button className="button secondary" onClick={connect}>Manage AI connections</button><p className="field-hint">Existing investigations keep the model chosen at the start. Changing this selection affects only new investigations.</p></section><section className="profile-section"><div className="section-heading"><h2>Usage limits</h2><button className="button secondary" disabled={busy} onClick={() => void refresh()}>{busy ? "Updating…" : "Refresh usage"}</button></div><p>These limits apply to Zone. API credit, ChatGPT allowance and local computing resources are managed separately by your provider or your computer.</p><div className="quota-list">{([['sessions', "Investigations", "Investigations started, including Arena trials."], ['experiments', "Experiments", "Authorized runs, including failed ones. Rejecting a proposal does not run an experiment."], ['model_calls', "Model calls", "Requests to a model, including corrections. This is separate from the experiment count."]] as const).map(([key, name, hint]) => <div key={key}><div className="section-heading"><h3>{name}</h3><span>{stats.usage[key]} of {stats.quotas[key]}</span></div><progress aria-label={`Limit ${name.toLowerCase()}`} max={Math.max(1, stats.quotas[key])} value={Math.min(stats.usage[key], stats.quotas[key])} /><p>{hint} Remaining: {Math.max(0, stats.quotas[key] - stats.usage[key])}.</p></div>)}</div>{updated && <p role="status">Usage refreshed at {updated}.</p>}{error && <p className="error" role="alert">{error}</p>}<details><summary>Technical request limits</summary><p>Per minute: {stats.quotas.read} reads, {stats.quotas.write} writes and {stats.quotas.run} experiments. If a limit is reached, wait rather than retrying automatically. Total quotas do not imply an automatic renewal date.</p></details></section><section className="profile-section"><h2>Access and recovery</h2><p>Keep your recovery code in a password manager. It cannot be retrieved from this page. Use it on the sign-in screen to choose a new password and receive a replacement code. This revokes previous login sessions and AI connections.</p><p>Your username identifies this account on this installation. Every Zone installation has separate accounts and data. Your Zone password is separate from your ChatGPT or AI provider password.</p><details><summary>Your data and security</summary><p>Passwords and keys are never included in prompts. Server-side API keys are encrypted. ChatGPT tokens and local connector credentials stay on your computer. The history stores scientific messages and measurements: avoid entering personal data.</p><p>Username changes, email recovery and self-service account deletion are not available. Contact your installation's operator for data management.</p><p>Account identifier: <code>{account.account_id}</code></p></details></section></section>
}
