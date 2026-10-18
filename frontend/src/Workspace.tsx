import { useEffect, useState, type ReactNode } from 'react'
import type { Account } from './Identity'
import { Connections } from './Connections'
import { request } from './api'
import { GettingStarted, HelpCenter } from './Guide'
import { Profile } from './Profile'

const paths = [
  ['scientist', 'Scientist', 'Indaga in prima persona, senza AI. Scegli esperimenti, formula ipotesi e verifica le previsioni.'],
  ['watch_agent', 'Watch an Agent', 'Osserva la tua AI al lavoro. Controlla le proposte e autorizza ogni esperimento.'],
  ['human_vs_ai', 'Human vs AI', 'Prima indaghi tu, poi l’agente: stesso mondo e budget, registri separati.'],
  ['world_of_day', 'World of the Day', 'Parti dal mondo di oggi, già selezionato. L’indagine è manuale.'],
  ['build_universe', 'Build a Universe', 'Genera un mondo con complessità e budget a tua scelta. Per gli esperti: leggi personalizzate.'],
  ['arena', 'Zone Arena', 'Fai partecipare il tuo agente a una challenge comune e consulta i risultati dopo la chiusura.'],
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
    } catch (e) { setError(e instanceof Error ? e.message : 'Sessioni non disponibili.') }
    finally { setBusy(false) }
  }
  function showSessions() { setPage('sessions'); void loadSessions(true) }
  return <div className="zone-workspace"><a className="skip-link" href="#workspace-content">Vai al contenuto</a><header className="workspace-topbar"><a className="wordmark" href="#" onClick={e => { e.preventDefault(); setPage('home') }}>zone<span>Laboratorio di universi sconosciuti</span></a><div className="account-chip"><button className="profile-shortcut" onClick={() => setPage('account')} aria-label={`Apri profilo di ${account.handle}`}><span className="account-initial" aria-hidden="true">{account.handle[0].toUpperCase()}</span>{account.handle}</button><button className="button ghost" onClick={logout}>Esci dall’account</button></div></header>
    <div className="workspace-body"><nav className="workspace-nav" aria-label="Navigazione principale"><p>Il tuo spazio</p>{[['home', 'Esplora le modalità'], ['lab', 'Indagine in corso'], ['connections', 'Connessioni AI'], ['sessions', 'Le mie sessioni'], ['help', 'Guida a Zone'], ['account', 'Account']].map(([id, label]) => <button key={id} aria-current={page === id ? 'page' : undefined} onClick={() => { if (id === 'sessions') showSessions(); else setPage(id) }}>{label}</button>)}<div className="nav-note"><strong>Tu scegli gli esperimenti.</strong><p>L’AI propone. Ogni lancio richiede una conferma esplicita.</p><button className="button ghost" onClick={() => setPage('help')}>Come funziona Zone</button></div></nav>
      <div id="workspace-content" className="workspace-content" tabIndex={-1}>
        {page === 'home' && <section className="mode-hub"><div className="page-heading"><p className="workspace-status">Benvenuto, {account.handle}</p><h1>Quale universo<br />vuoi capire oggi?</h1><p>In Zone non conosci la legge fisica: la indaghi con esperimenti. Puoi farlo tu, guidare una AI o confrontare le vostre previsioni.</p></div><GettingStarted enter={enter} connect={() => setPage('connections')} /><div className="section-heading"><h2>Scegli il tuo percorso</h2><button className="button ghost" onClick={() => setPage('help')}>Confronta le modalità nella guida</button></div><div className="mode-directory">{paths.map(([id, name, description], i) => <button key={id} className="mode-entry" onClick={() => enter(id)}><span className="mode-number">{String(i + 1).padStart(2, '0')}</span><span><strong>{name}</strong><span>{description}</span></span><span aria-hidden="true">↗</span></button>)}</div><div className="hub-next"><h2>Porta la tua AI.</h2><p>API personali, Sign in with ChatGPT tramite connettore e modelli Ollama sul tuo computer.</p><button className="button primary" onClick={() => setPage('connections')}>Collega la tua AI</button></div></section>}
        {page === 'connections' && <Connections />}
        {page === 'help' && <HelpCenter />}
        {page === 'sessions' && <section><div className="page-heading"><h1>Le tue indagini</h1><p>Riprendi una sessione o rileggi le osservazioni. Il modello resta quello scelto all’avvio. Aprire un registro non esegue esperimenti né chiama l’AI.</p></div><button className="button secondary" disabled={busy} onClick={() => void loadSessions(true)}>Aggiorna elenco</button><ul className="session-list">{sessions.map(s => <li key={s.session_id}><div><strong>{paths.find(p => p[0] === s.mode)?.[1] ?? s.mode}</strong><code>{s.session_id}</code></div><button className="button secondary" onClick={() => { setPage('lab'); window.dispatchEvent(new CustomEvent('zone-open-session', { detail: { id: s.session_id, mode: s.mode } })) }}>Apri indagine</button></li>)}</ul>{!sessions.length && !busy && <div className="empty-guide"><h2>La tua prima indagine ti aspetta</h2><p>Le sessioni vengono salvate automaticamente. Parti da Scientist per provare senza configurare un modello.</p><button className="button primary" onClick={() => enter('scientist')}>Inizia senza AI</button></div>}{hasMore && <button className="button secondary" disabled={busy} onClick={() => void loadSessions()}>Carica altre sessioni</button>}{busy && <p role="status">Caricamento delle indagini…</p>}{error && <p className="error" role="alert">{error}</p>}</section>}
        {page === 'account' && <><Profile account={account} connect={() => setPage('connections')} sessions={showSessions} />{admin}</>}
        <div className="lab-surface" hidden={page !== 'lab'}>{children}</div>
      </div></div><footer className="workspace-footer">Zone · Laboratorio sperimentale <span>Ipotesi, evidenze e limiti restano distinti.</span></footer>
  </div>
}
