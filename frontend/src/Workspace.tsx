import { useEffect, useState, type ReactNode } from 'react'
import type { Account } from './Identity'
import { Connections } from './Connections'
import { request } from './api'
import { GettingStarted, HelpCenter } from './Guide'
import { Profile } from './Profile'

const paths = [
  ['scientist', 'Scientist', "Investigate for yourself, without AI. Choose experiments, form hypotheses and test your predictions."],
  ['watch_agent', 'Watch an Agent', "Watch your AI investigate. Review its proposals and authorize every experiment."],
  ['human_vs_ai', 'Human vs AI', "Investigate first, then let the agent try. Same world and budget, separate histories."],
  ['world_of_day', 'World of the Day', "Start with today's world, already selected. Conduct the investigation yourself."],
  ['build_universe', 'Build a Universe', "Generate a world with your chosen complexity and budget. Advanced users can author a law."],
  ['arena', 'Zone Arena', "Enter your agent in a shared challenge. Compare results once the challenge closes."],
]
export function Workspace({ account, children, logout, admin }: { account: Account; children: ReactNode; logout: () => void; admin: ReactNode }) {
  const [page, setPage] = useState('home')
  const [sessions, setSessions] = useState<{ session_id: string; mode: string }[]>([])
  const [after, setAfter] = useState(0)
  const [hasMore, setHasMore] = useState(true)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  function enter(mode: string) {
    setPage('lab'); window.dispatchEvent(new CustomEvent('zone-select-mode', { detail: mode }))
  }
  useEffect(() => {
    const navigate = (event: Event) => { const target = (event as CustomEvent<string>).detail; if (target === 'connections') setPage(target); else if (paths.some(p => p[0] === target)) enter(target) }
    window.addEventListener('zone-workspace-page', navigate)
    return () => window.removeEventListener('zone-workspace-page', navigate)
  }, [])
  async function loadSessions(reset = false) {
    setBusy(true); setError('')
    try {
      const data = await request<{ sessions: typeof sessions; next_after: number | null }>(`/my/sessions?after=${reset ? 0 : after}`)
      setSessions(current => reset ? data.sessions : [...current, ...data.sessions.filter(s => !current.some(c => c.session_id === s.session_id))]); setAfter(data.next_after ?? 0); setHasMore(data.next_after !== null && data.sessions.length > 0)
    } catch (e) { setError(e instanceof Error ? e.message : "Your investigations could not be loaded.") }
    finally { setBusy(false) }
  }
  function showSessions() { setPage('sessions'); void loadSessions(true) }
  return <div className="zone-workspace"><a className="skip-link" href="#workspace-content">Skip to content</a><header className="workspace-topbar"><a className="wordmark" href="#" onClick={e => { e.preventDefault(); setPage('home') }}>zone<span>A laboratory of unknown universes</span></a><div className="account-chip"><button className="profile-shortcut" onClick={() => setPage('account')} aria-label={`Open profile for ${account.handle}`}><span className="account-initial" aria-hidden="true">{account.handle[0].toUpperCase()}</span>{account.handle}</button><button className="button ghost" onClick={logout}>Sign out</button></div></header>
    <div className="workspace-body"><nav className="workspace-nav" aria-label={"Main navigation"}><p>Your workspace</p>{[['home', "Explore modes"], ['lab', "Current investigation"], ['connections', "AI connections"], ['sessions', "My investigations"], ['help', "Guide to Zone"], ['account', 'Account']].map(([id, label]) => <button key={id} aria-current={page === id ? 'page' : undefined} onClick={() => { if (id === 'sessions') showSessions(); else setPage(id) }}>{label}</button>)}<div className="nav-note"><strong>You choose the experiments.</strong><p>The AI proposes. Every experiment needs your explicit confirmation.</p><button className="button ghost" onClick={() => setPage('help')}>How Zone works</button></div></nav>
      <div id="workspace-content" className="workspace-content" tabIndex={-1}>
        {page === 'home' && <section className="mode-hub"><div className="page-heading"><p className="workspace-status">Welcome, {account.handle}</p><h1>Which universe<br />would you like to understand?</h1><p>In Zone, you discover a hidden physical law through experiments. Investigate yourself, guide an AI or compare your predictions.</p></div><GettingStarted enter={enter} connect={() => setPage('connections')} /><div className="section-heading"><h2>Choose your path</h2><button className="button ghost" onClick={() => setPage('help')}>Compare modes in the guide</button></div><div className="mode-directory">{paths.map(([id, name, description]) => <button key={id} className="mode-entry" onClick={() => enter(id)}><span><strong>{name}</strong><span>{description}</span></span><span aria-hidden="true">↗</span></button>)}</div><div className="hub-next"><h2>Bring your own AI.</h2><p>Personal APIs, Sign in with ChatGPT through a local connector, and Ollama models on your computer.</p><button className="button primary" onClick={() => setPage('connections')}>Connect your AI</button></div></section>}
        {page === 'connections' && <Connections />}
        {page === 'help' && <HelpCenter />}
        {page === 'sessions' && <section><div className="page-heading"><h1>Your investigations</h1><p>Continue an investigation or revisit its observations. It keeps the model chosen at the start. Opening a history does not run experiments or call an AI.</p></div><button className="button secondary" disabled={busy} onClick={() => void loadSessions(true)}>Refresh list</button><ul className="session-list">{sessions.map((s, i) => <li key={s.session_id}><div><strong>{paths.find(p => p[0] === s.mode)?.[1] ?? s.mode}</strong><span>Investigation {i + 1}</span><details><summary>Technical identifier</summary><code>{s.session_id}</code></details></div><button className="button secondary" onClick={() => { setPage('lab'); window.dispatchEvent(new CustomEvent('zone-open-session', { detail: { id: s.session_id, mode: s.mode } })) }}>Open investigation</button></li>)}</ul>{!sessions.length && !busy && <div className="empty-guide"><h2>Your first investigation starts here</h2><p>Investigations are saved automatically. Start with Scientist to try Zone without setting up a model.</p><button className="button primary" onClick={() => enter('scientist')}>Start without AI</button></div>}{hasMore && <button className="button secondary" disabled={busy} onClick={() => void loadSessions()}>Load more investigations</button>}{busy && <p role="status">Loading investigations…</p>}{error && <p className="error" role="alert">{error}</p>}</section>}
        {page === 'account' && <><Profile account={account} connect={() => setPage('connections')} sessions={showSessions} />{admin}</>}
        <div className="lab-surface" hidden={page !== 'lab'}>{children}</div>
      </div></div><footer className="workspace-footer">Zone · experimental laboratory <span>Keep hypotheses, evidence and limits distinct.</span></footer>
  </div>
}
