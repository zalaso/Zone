import { useEffect, useState, type FormEvent } from 'react'
import { request } from './api'

type Connection = { id: string; label: string; provider: string; model: string; transport: string; enabled: number; last_seen: number | null }
type Catalog = { connections: Connection[]; selected: string | null; api_enabled: boolean }
const names: Record<string, string> = { openai: 'OpenAI API', anthropic: 'Anthropic API', gemini: 'Gemini API', chatgpt: 'ChatGPT', ollama: 'Ollama locale' }

export function Connections() {
  const [catalog, setCatalog] = useState<Catalog | null>(null)
  const [provider, setProvider] = useState('openai')
  const [transport, setTransport] = useState('api')
  const [label, setLabel] = useState('')
  const [model, setModel] = useState('')
  const [key, setKey] = useState('')
  const [issued, setIssued] = useState('')
  const [issuedProvider, setIssuedProvider] = useState('')
  const [issuedModel, setIssuedModel] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function load() { setCatalog(await request<Catalog>('/my/connections')) }
  useEffect(() => { void load().catch(e => setError(e.message)) }, [])
  async function act(work: () => Promise<void>) {
    setBusy(true); setError('')
    try { await work(); await load(); window.dispatchEvent(new Event('zone-connections-changed')) }
    catch (e) { setError(e instanceof Error ? e.message : 'Connessione non disponibile.') }
    finally { setBusy(false); setKey('') }
  }
  function choose(value: string) { setProvider(value); setKey(''); setTransport(['chatgpt', 'ollama'].includes(value) ? 'connector' : 'api') }
  function submit(event: FormEvent) {
    event.preventDefault()
    void act(async () => {
      const data = await request<{ id: string; connector_key: string | null }>('/my/connections', 'POST', {
        label: label || names[provider], provider, model, transport, ...(transport === 'api' ? { api_key: key } : {}),
      })
      setIssued(data.connector_key ?? ''); setIssuedProvider(provider); setIssuedModel(model)
      setLabel(''); setModel('')
    })
  }
  return <section className="connection-page"><div className="page-heading"><h1>La tua AI, il tuo laboratorio.</h1><p>Collega un modello personale. Nessuna chiamata parte quando salvi una connessione.</p></div>
    <div className="connection-layout"><section className="panel"><h2>Aggiungi una connessione</h2><p>Scegli come vuoi usare l’AI. API: serve una chiave del provider e un eventuale credito. ChatGPT: serve il piano personale e un connettore sul PC. Ollama: serve un modello già installato sul PC.</p>
      <div className="provider-tabs" aria-label="Tipo di AI">{Object.entries(names).map(([id, name]) => <button key={id} className="button secondary" aria-pressed={provider === id} onClick={() => choose(id)}>{name}</button>)}</div>
      <form onSubmit={submit}><label>Nome della connessione<input value={label} onChange={e => setLabel(e.target.value)} maxLength={80} placeholder="Per esempio: modello per le indagini" /></label>
        <p className="field-hint">L’ID modello è il nome esatto disponibile nel provider, non il tuo nome utente. Copialo dal pannello del provider o, per Ollama, dall’elenco dei modelli installati. Non viene scelto un modello costoso automaticamente.</p><label>ID modello<input value={model} onChange={e => setModel(e.target.value)} maxLength={128} required placeholder="Scegli un modello disponibile nel tuo account" /></label>
        {!['chatgpt', 'ollama'].includes(provider) && <label>Dove usare la chiave<select value={transport} onChange={e => { setTransport(e.target.value); setKey('') }}><option value="api" disabled={!catalog?.api_enabled}>Sul server, in archivio cifrato</option><option value="connector">Sul mio computer, con il connettore</option></select></label>}
        {transport === 'api' ? <><label>Chiave API personale<input type="password" autoComplete="off" required minLength={8} maxLength={4096} value={key} onChange={e => setKey(e.target.value)} /></label><p className="field-hint">La chiave viene trasmessa al server e cifrata separatamente dai registri. Le chiamate consumano il tuo credito API.</p>{catalog && !catalog.api_enabled && <p className="notice">Il gestore deve configurare l’archivio cifrato. Puoi già scegliere il connettore locale.</p>}</> : <p className="notice">Il connettore gira sul tuo computer e raggiunge Zone in uscita. {provider === 'chatgpt' ? 'Sign in with ChatGPT avviene nel browser locale; i token del piano restano sul tuo computer.' : provider === 'ollama' ? 'Ollama deve essere già avviato e il modello installato. Non serve esporre una porta su Internet.' : 'La chiave viene letta dalla variabile d’ambiente del provider sul tuo computer.'}</p>}
        <button className="button primary" disabled={busy || transport === 'api' && !catalog?.api_enabled}>{provider === 'chatgpt' ? 'Prepara Sign in with ChatGPT' : 'Salva connessione'}</button>
      </form>
    </section><aside className="connection-notes"><h2>Come funziona</h2><ol><li>Collega il provider e scegli il modello.</li><li>Se usi il connettore, avvialo sul tuo computer.</li><li>Crea una nuova indagine e premi Avanza agente.</li></ol><details><summary>Che cos’è il connettore locale?</summary><p>È un piccolo programma Zone che tieni aperto sul tuo computer. Riceve le richieste dal sito e le passa al tuo modello. Serve per ChatGPT e Ollama; può anche tenere le chiavi API sul PC. Non devi aprire porte in rete. Chiudendo il programma, il sito non può raggiungere quel modello.</p><p>Il comando mostrato dopo la creazione va eseguito nel terminale della tua installazione Zone. È un passaggio tecnico necessario nell’anteprima; creare un account Zone non collega automaticamente ChatGPT.</p></details><p>Approvazione, previsione e lancio rimangono azioni distinte. Una connessione diversa si applica alle nuove sessioni.</p><p>ChatGPT sul sito pubblico usa il connettore locale. L’uso diretto del piano sul server per tutti richiede l’adesione del gestore al percorso OpenAI per app ospitate.</p><a href="https://developers.openai.com/siwc/token-sharing-open-source" target="_blank" rel="noreferrer">Requisiti ufficiali ChatGPT ↗</a></aside></div>
    {issued && <section className="panel notice"><h2>Avvia il connettore</h2><p>Installa Zone sul tuo computer con l’extra del provider, poi esegui questo comando. La chiave verrà richiesta con input nascosto.</p><pre>{`python -m hidden_lab connector --origin ${window.location.origin} --provider ${issuedProvider} --model ${issuedModel} --allow-inference${issuedProvider === 'chatgpt' ? ' --login' : ''}${window.location.protocol === 'http:' ? ' --local-http' : ''}`}</pre><label>Chiave del connettore, mostrata una sola volta<input type="password" readOnly value={issued} autoComplete="off" /></label><button className="button secondary" onClick={() => void navigator.clipboard.writeText(issued).catch(() => setError('Copia non disponibile: seleziona la chiave nel campo.'))}>Copia chiave</button><button className="button secondary" onClick={() => setIssued('')}>Ho conservato la chiave</button><p>Vale 30 giorni, solo per questa connessione. Chiudendo la pagina viene dimenticata: se la perdi, disconnetti e ricrea il collegamento.</p></section>}
    <section className="panel"><div className="section-heading"><h2>Connessioni personali</h2><button className="button tiny" disabled={busy} onClick={() => void act(load)}>Aggiorna stato</button></div>
      {!catalog ? <p role="status">Caricamento connessioni…</p> : <><p>{catalog.selected ? 'La connessione selezionata sarà usata nelle nuove indagini AI.' : 'Nessuna AI selezionata: resta disponibile la baseline offline, chiaramente indicata.'}</p><ul className="connection-list">{catalog.connections.filter(c => c.enabled).map(c => <li key={c.id}><div><strong>{c.label}</strong><span>{names[c.provider]} · {c.model}</span><small>{c.transport === 'api' ? 'API personale · credenziale salvata, inferenza ancora da verificare' : c.last_seen && Date.now() / 1000 - c.last_seen < 15 ? 'Connettore online' : 'Connettore da avviare'}</small></div><div className="button-row"><button className="button secondary" disabled={busy || catalog.selected === c.id} onClick={() => void act(async () => { await request('/my/connections/select', 'POST', { connection_id: c.id }) })}>{catalog.selected === c.id ? 'Selezionata' : 'Usa nelle nuove sessioni'}</button><button className="button danger" disabled={busy} onClick={() => void act(async () => { await request(`/my/connections/${c.id}`, 'DELETE') })}>Disconnetti</button></div></li>)}</ul><button className="button ghost" disabled={busy || !catalog.selected} onClick={() => void act(async () => { await request('/my/connections/select', 'POST', { connection_id: null }) })}>Usa baseline offline</button></>}
    </section>{error && <p role="alert" className="error">{error}</p>}
  </section>
}
