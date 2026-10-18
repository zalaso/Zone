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
    } catch (e) { setError(e instanceof Error ? e.message : 'Accesso non disponibile.') }
    finally { setBusy(false); setPassword(''); setKey(''); setRecovery('') }
  }
  return <div className="public-access"><header className="workspace-topbar"><a className="wordmark" href="#">zone<span>Il laboratorio, con la tua AI.</span></a><span>Open source · i tuoi modelli, i tuoi esperimenti</span></header><main className="access-layout"><section className="access-story"><p className="workspace-status">Un universo. Nessuna legge svelata.</p><h1>Fai domande.<br />Progetta esperimenti.<br />Mostra le prove.</h1><p>Zone è un laboratorio virtuale: imposti come parte una particella e osservi dove va. La legge del mondo è nascosta; il tuo obiettivo è scoprirne il comportamento con esperimenti e previsioni.</p><details className="landing-demo"><summary>Guarda un esempio, senza account o AI</summary><p>Esempio illustrativo con dati dimostrativi, non misure di un mondo segreto. Premi Riproduci per seguire i campioni.</p><ExperimentStage experiment={null} label="Esempio illustrativo · dati dimostrativi" points={[{ t: 0, x: 0, y: 0 }, { t: .25, x: .5, y: .75 }, { t: .5, x: 1, y: 1 }, { t: .75, x: 1.5, y: .75 }, { t: 1, x: 2, y: 0 }]} /></details><div className="experiment-visual" aria-label="Schema del ciclo: richiesta, conferma, misura, ipotesi"><span>Proponi le condizioni</span><span>La tua conferma</span><span>Osserva le misure</span><span>Confronta la previsione</span></div><p>Puoi iniziare manualmente, senza conoscere formule. Per guidare un’AI userai il tuo account del provider. Zone non fornisce credito per le chiamate.</p><p className="access-footnote">API personali · ChatGPT con connettore locale · Ollama<br />L’AI non può autorizzare i propri esperimenti.</p></section>
    <section className="panel access-form"><h2>{issued ? 'Conserva il recupero' : tab === 'register' ? 'Crea il tuo laboratorio' : tab === 'recover' ? 'Recupera l’account' : 'Bentornato in Zone'}</h2>
      {issued ? <><p>Questo codice viene mostrato una sola volta. Conservalo nel tuo password manager: permette di cambiare la password e revoca le sessioni e disconnette le AI precedenti.</p><label>Codice di recupero<input readOnly type="text" value={issued} /></label><button className="button primary" onClick={() => { setIssued(''); if (pending) onLogin(pending.account, pending.csrf); else setTab('password') }}>Ho conservato il codice</button></> : <><div className="auth-tabs" aria-label="Accesso">{registrationOpen && <button className="button secondary" aria-pressed={tab === 'register'} onClick={() => setTab('register')}>Crea account</button>}<button className="button secondary" aria-pressed={tab === 'password'} onClick={() => setTab('password')}>Accedi</button><button className="button ghost" aria-pressed={tab === 'key'} onClick={() => setTab('key')}>Ho un invito</button></div>
      <form onSubmit={e => { e.preventDefault(); void submit() }}>{tab === 'key' ? <label>Chiave di accesso<input type="password" value={key} onChange={e => setKey(e.target.value)} required autoComplete="off" /></label> : <><label>Nome utente<input value={handle} onChange={e => setHandle(e.target.value)} required pattern="[a-z][a-z0-9_-]{2,47}" autoComplete="username" /></label>{tab === 'recover' && <label>Codice di recupero<input type="password" value={recovery} onChange={e => setRecovery(e.target.value)} required autoComplete="off" /></label>}<label>{tab === 'recover' ? 'Nuova password' : 'Password'}<input type="password" value={password} onChange={e => setPassword(e.target.value)} required minLength={12} maxLength={256} autoComplete={tab === 'password' ? 'current-password' : 'new-password'} /></label><p className="field-hint">Nome utente: 3–48 caratteri minuscoli, numeri, _ o -, iniziando con una lettera. Password: almeno 12 caratteri. Nessuna chiave AI richiesta per creare l’account.</p></>}
      <button className="button primary" disabled={busy}>{busy ? 'Attendi…' : tab === 'register' ? 'Crea account e continua' : tab === 'recover' ? 'Cambia password' : 'Entra nel laboratorio'}</button></form><button className="button ghost" onClick={() => { setTab('recover'); setPassword(''); setError('') }}>Recupera con il tuo codice</button></>}
      {error && <p role="alert" className="error">{error}</p>}<p className="field-hint">Cookie di sessione HttpOnly. Password e credenziali AI non vengono incluse nei prompt.</p></section></main></div>
}
