import { useEffect, useState } from 'react'
import type { Account } from './Identity'
import { request } from './api'

export function Profile({ account, connect, sessions }: { account: Account; connect: () => void; sessions: () => void }) {
  const [stats, setStats] = useState(account)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [updated, setUpdated] = useState('')
  const [connection, setConnection] = useState('Caricamento della connessione…')
  useEffect(() => {
    let alive = true
    void request<{ connections: { id: string; label: string; model: string; enabled: number }[]; selected: string | null }>('/my/connections')
      .then(data => { const chosen = data.connections.find(c => c.enabled && c.id === data.selected); if (alive) setConnection(chosen ? `${chosen.label} · ${chosen.model}` : 'Baseline numerica offline · non è un LLM') })
      .catch(() => { if (alive) setConnection('Stato non disponibile. Controlla Connessioni AI.') })
    return () => { alive = false }
  }, [])
  async function refresh() {
    setBusy(true); setError('')
    try { const data = await request<{ account: Account }>('/auth/me'); setStats(data.account); setUpdated(new Date().toLocaleTimeString('it-IT')) }
    catch (e) { setError(e instanceof Error ? e.message : 'Quote non disponibili. Riprova.') }
    finally { setBusy(false) }
  }
  useEffect(() => { void refresh() }, [account.account_id])
  return <section className="profile-page"><div className="profile-heading"><span className="profile-avatar" aria-hidden="true">{account.handle.slice(0, 2).toUpperCase()}</span><div><h1>Il tuo account</h1><p>@{account.handle} · {({ member: 'Membro del laboratorio', admin: 'Amministratore', operator: 'Operatore' })[account.role]}</p></div></div><p>Qui trovi il tuo utilizzo, il modello scelto e le informazioni per conservare l’accesso al laboratorio.</p><section className="profile-section"><div className="section-heading"><h2>Il tuo laboratorio</h2><button className="button secondary" onClick={sessions}>Apri le mie sessioni</button></div><p><strong>AI per le nuove indagini:</strong> {connection}</p><button className="button secondary" onClick={connect}>Gestisci le connessioni AI</button><p className="field-hint">Le indagini già iniziate conservano il modello scelto all’avvio. Cambiare selezione non modifica quelle sessioni.</p></section><section className="profile-section"><div className="section-heading"><h2>Quote di utilizzo</h2><button className="button secondary" disabled={busy} onClick={() => void refresh()}>{busy ? 'Aggiornamento…' : 'Aggiorna quote'}</button></div><p>Questi limiti riguardano Zone. Credito API, quota ChatGPT e risorse dei modelli locali sono gestiti separatamente dal tuo provider.</p><div className="quota-list">{([['sessions', 'Sessioni', 'Indagini avviate, compresi i trial Arena.'], ['experiments', 'Esperimenti', 'Lanci autorizzati, inclusi quelli falliti. Un rifiuto non esegue un lancio.'], ['model_calls', 'Chiamate al modello', 'Richieste al modello, comprese le correzioni. Non equivalgono al numero di esperimenti.']] as const).map(([key, name, hint]) => <div key={key}><div className="section-heading"><h3>{name}</h3><span>{stats.usage[key]} di {stats.quotas[key]}</span></div><progress aria-label={`Quota ${name.toLowerCase()}`} max={Math.max(1, stats.quotas[key])} value={Math.min(stats.usage[key], stats.quotas[key])} /><p>{hint} Residui: {Math.max(0, stats.quotas[key] - stats.usage[key])}.</p></div>)}</div>{updated && <p role="status">Quote aggiornate alle {updated}.</p>}{error && <p className="error" role="alert">{error}</p>}<details><summary>Limiti tecnici delle richieste</summary><p>Per minuto: {stats.quotas.read} letture, {stats.quotas.write} scritture e {stats.quotas.run} lanci. Superare un limite richiede di attendere; non avviare ripetizioni automatiche. Le quote totali non indicano una data di rinnovo automatico.</p></details></section><section className="profile-section"><h2>Accesso e recupero</h2><p>Conserva il codice di recupero nel tuo password manager. Non può essere riletto da questa pagina. Se lo usi dalla schermata di accesso, scegli una nuova password e ricevi un nuovo codice; le sessioni di accesso e le connessioni AI precedenti vengono revocate.</p><p>Il nome utente identifica l’account in questa installazione. Ogni installazione di Zone ha account e dati separati. La password di Zone non è quella di ChatGPT o del provider AI.</p><details><summary>Dati e sicurezza del profilo</summary><p>Password e chiavi non vengono incluse nei prompt. Le chiavi API salvate sul server sono cifrate; i token ChatGPT e le credenziali del connettore restano sul tuo computer. Il registro conserva i messaggi scientifici e le misure: evita di inserirvi dati personali.</p><p>Modifica del nome utente, recupero via email ed eliminazione autonoma dell’account non sono ancora disponibili. Per la gestione dei dati rivolgiti al gestore dell’installazione.</p><p>ID account: <code>{account.account_id}</code></p></details></section></section>
}
