import { useState } from 'react'
import { request } from './api'
import { ExperimentStage } from './LabVisuals'
import type { Account } from './Identity'

export function PublicAccess({ registrationOpen, onLogin }: { registrationOpen: boolean; onLogin: (account: Account, csrf: string) => void }) {
  const [tab, setTab] = useState(registrationOpen ? 'register' : 'password')
  const [handle, setHandle] = useState('')
  const [password, setPassword] = useState('')
  const [key, setKey] = useState('')
  const [recovery, setRecovery] = useState('')
  const [issued, setIssued] = useState('')
  const [pending, setPending] = useState<{ account: Account; csrf: string } | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function submit() {
    setBusy(true); setError('')
    try {
      if (tab === 'recover') {
        const data = await request<{ recovery_code: string }>('/auth/recover', 'POST', { handle, password, recovery_code: recovery })
        setIssued(data.recovery_code)
      } else {
        const data = await request<{ account: Account; csrf: string; recovery_code?: string }>(`/auth/${tab === 'key' ? 'login' : tab}`, 'POST', tab === 'key' ? { login_key: key } : { handle, password })
        if (data.recovery_code) { setIssued(data.recovery_code); setPending(data) }
        else onLogin(data.account, data.csrf)
      }
    } catch (e) { setError(e instanceof Error ? e.message : "Sign-in is unavailable. Please try again.") }
    finally { setBusy(false); setPassword(''); setKey(''); setRecovery('') }
  }
  return <div className="public-access"><header className="workspace-topbar"><a className="wordmark" href="#">zone<span>Your laboratory. Your AI.</span></a><span>Open source · your models, your experiments</span></header><main className="access-layout"><section className="access-story"><p className="workspace-status">One universe. Its rules are yours to discover.</p><h1>Ask questions.<br />Design experiments.<br />Show the evidence.</h1><p>Zone is a virtual laboratory. Set a particle in motion, observe what happens and test your ideas. The world's physical law stays hidden: discover its behavior through experiments and predictions.</p><details className="landing-demo"><summary>Try a demo, no account or AI needed</summary><p>These illustrative samples are demonstration data, not measurements from a hidden evaluation world. Press Play measurements to follow them.</p><ExperimentStage experiment={null} label={"Illustrative example · demonstration data"} points={[{ t: 0, x: 0, y: 0 }, { t: .25, x: .5, y: .75 }, { t: .5, x: 1, y: 1 }, { t: .75, x: 1.5, y: .75 }, { t: 1, x: 2, y: 0 }]} /></details><div className="experiment-visual" aria-label={"Experiment cycle: propose, confirm, observe, predict"}><span>Propose the setup</span><span>You authorize the run</span><span>Observe the measurements</span><span>Test your prediction</span></div><p>Start manually, without knowing any formulas. To guide an AI, connect your own provider account. Zone does not supply credit for model calls.</p><p className="access-footnote">Personal APIs · ChatGPT through a local connector · Ollama<br />The AI cannot authorize its own experiments.</p></section>
    <section className="panel access-form"><h2>{issued ? "Save your recovery code" : tab === 'register' ? "Create your laboratory" : tab === 'recover' ? "Recover your account" : "Welcome back to Zone"}</h2>
      {issued ? <><p>This code is shown only once. Save it in your password manager. Using it resets your password, signs out previous sessions and disconnects existing AI connections.</p><label>Recovery code<input readOnly type="text" value={issued} /></label><button className="button primary" onClick={() => { setIssued(''); if (pending) onLogin(pending.account, pending.csrf); else setTab('password') }}>I have saved my code</button></> : <><div className="auth-tabs" aria-label={"Sign in"}>{registrationOpen && <button className="button secondary" aria-pressed={tab === 'register'} onClick={() => setTab('register')}>Create account</button>}<button className="button secondary" aria-pressed={tab === 'password'} onClick={() => setTab('password')}>Sign in</button><button className="button ghost" aria-pressed={tab === 'key'} onClick={() => setTab('key')}>I have an invite</button></div>
      <form onSubmit={e => { e.preventDefault(); void submit() }}>{tab === 'key' ? <label>Access key<input type="password" value={key} onChange={e => setKey(e.target.value)} required autoComplete="off" /></label> : <><label>Username<input value={handle} onChange={e => setHandle(e.target.value)} required pattern="[a-z][a-z0-9_-]{2,47}" autoComplete="username" /></label>{tab === 'recover' && <label>Recovery code<input type="password" value={recovery} onChange={e => setRecovery(e.target.value)} required autoComplete="off" /></label>}<label>{tab === 'recover' ? "New password" : 'Password'}<input type="password" value={password} onChange={e => setPassword(e.target.value)} required minLength={12} maxLength={256} autoComplete={tab === 'password' ? 'current-password' : 'new-password'} /></label><p className="field-hint">Username: 3–48 lowercase letters, numbers, _ or -, starting with a letter. Password: at least 12 characters. No AI key is needed to create an account.</p></>}
      <button className="button primary" disabled={busy}>{busy ? "Please wait…" : tab === 'register' ? "Create account and continue" : tab === 'recover' ? "Change password" : "Enter the laboratory"}</button></form><button className="button ghost" onClick={() => { setTab('recover'); setPassword(''); setError('') }}>Use your recovery code</button></>}
      {error && <p role="alert" className="error">{error}</p>}<p className="field-hint">Your login uses an HttpOnly session cookie. Passwords and AI credentials are never included in model prompts.</p></section></main></div>
}
