import { useEffect, useState, type FormEvent } from 'react'
import { request } from './api'

type Connection = { id: string; label: string; provider: string; model: string; transport: string; enabled: number; last_seen: number | null }
type Catalog = { connections: Connection[]; selected: string | null; api_enabled: boolean }
const names: Record<string, string> = { openai: 'OpenAI API', anthropic: 'Anthropic API', gemini: 'Gemini API', chatgpt: 'ChatGPT', ollama: "Local Ollama" }

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
    catch (e) { setError(e instanceof Error ? e.message : "The connection is unavailable.") }
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
  return <section className="connection-page"><div className="page-heading"><h1>Your AI. Your laboratory.</h1><p>Connect your own model. Saving a connection never starts a model call.</p></div>
    <div className="connection-layout"><section className="panel"><h2>Add a connection</h2><p>Choose how to use AI. APIs need a provider key and any required credit. ChatGPT needs an eligible personal plan and a local connector. Ollama needs a model already installed on your computer.</p>
      <div className="provider-tabs" aria-label={"AI provider"}>{Object.entries(names).map(([id, name]) => <button key={id} className="button secondary" aria-pressed={provider === id} onClick={() => choose(id)}>{name}</button>)}</div>
      <form onSubmit={submit}><label>Connection name<input value={label} onChange={e => setLabel(e.target.value)} maxLength={80} placeholder={"For example: my research model"} /></label>
        <p className="field-hint">The model ID is the exact model name, not your username. Copy it from your provider's dashboard or Ollama's installed model list. Zone never chooses an expensive model automatically.</p><label>Model ID<input value={model} onChange={e => setModel(e.target.value)} maxLength={128} required placeholder={"Choose a model available to your account"} /></label>
        {!['chatgpt', 'ollama'].includes(provider) && <label>Where to keep the key<select value={transport} onChange={e => { setTransport(e.target.value); setKey('') }}><option value="api" disabled={!catalog?.api_enabled}>On the server, encrypted</option><option value="connector">On my computer, through the connector</option></select></label>}
        {transport === 'api' ? <><label>Personal API key<input type="password" autoComplete="off" required minLength={8} maxLength={4096} value={key} onChange={e => setKey(e.target.value)} /></label><p className="field-hint">Your key is sent to the server and encrypted separately from the history. Model calls use your provider's allowance.</p>{catalog && !catalog.api_enabled && <p className="notice">The operator must enable the encrypted vault. You can use the local connector now.</p>}</> : <p className="notice">The connector runs on your computer and makes outbound requests to Zone. {provider === 'chatgpt' ? "Sign in with ChatGPT opens in your local browser. Plan tokens stay on your computer." : provider === 'ollama' ? "Start Ollama with an already installed model. You do not need to expose a port to the Internet." : "The connector reads the provider key from its environment on your computer."}</p>}
        <button className="button primary" disabled={busy || transport === 'api' && !catalog?.api_enabled}>{provider === 'chatgpt' ? "Set up Sign in with ChatGPT" : "Save connection"}</button>
      </form>
    </section><aside className="connection-notes"><h2>How it works</h2><ol><li>Connect your provider and choose a model.</li><li>If using a connector, start it on your computer.</li><li>Create a new investigation and choose Ask for next step.</li></ol><details><summary>What is the local connector?</summary><p>A small Zone program you keep running on your computer. It receives requests from the site and passes them to your model. It is used for ChatGPT and Ollama, and can also keep API keys local. No inbound port is needed. When you close it, the site can no longer reach that model.</p><p>Run the command shown after setup in your Zone installation's terminal. This connector step is required. Creating a Zone account does not automatically connect ChatGPT.</p></details><p>Approval, prediction and execution remain separate actions. Changing the selected connection applies to new investigations.</p><p>ChatGPT on a remotely hosted site uses your local connector. Direct shared server access to plan usage requires the operator to meet OpenAI's hosted-app requirements.</p><a href="https://developers.openai.com/siwc/token-sharing-open-source" target="_blank" rel="noreferrer">Official ChatGPT requirements ↗</a></aside></div>
    {issued && <section className="panel notice"><h2>Start the connector</h2><p>Install Zone on your computer with the provider extra, then run this command. The terminal asks for your connector key with hidden input.</p><pre>{`python -m hidden_lab connector --origin ${window.location.origin} --provider ${issuedProvider} --model ${issuedModel} --allow-inference${issuedProvider === 'chatgpt' ? ' --login' : ''}${window.location.protocol === 'http:' ? ' --local-http' : ''}`}</pre><label>Connector key, shown only once<input type="password" readOnly value={issued} autoComplete="off" /></label><button className="button secondary" onClick={() => void navigator.clipboard.writeText(issued).catch(() => setError("Copy unavailable. Select the key in the field."))}>Copy key</button><button className="button secondary" onClick={() => setIssued('')}>I have saved the key</button><p>Valid for 30 days and only for this connection. The page forgets it when closed. If you lose it, disconnect and set up the connection again.</p></section>}
    <section className="panel"><div className="section-heading"><h2>Your connections</h2><button className="button tiny" disabled={busy} onClick={() => void act(load)}>Refresh status</button></div>
      {!catalog ? <p role="status">Loading connections…</p> : <><p>{catalog.selected ? "New AI investigations will use the selected connection." : "No AI selected. You can still use the clearly labeled offline baseline."}</p><ul className="connection-list">{catalog.connections.filter(c => c.enabled).map(c => <li key={c.id}><div><strong>{c.label}</strong><span>{names[c.provider]} · {c.model}</span><small>{c.transport === 'api' ? "Personal API · key saved, model access not yet tested" : c.last_seen && Date.now() / 1000 - c.last_seen < 15 ? "Connector online" : "Start your connector"}</small></div><div className="button-row"><button className="button secondary" disabled={busy || catalog.selected === c.id} onClick={() => void act(async () => { await request('/my/connections/select', 'POST', { connection_id: c.id }) })}>{catalog.selected === c.id ? "Selected" : "Use for new investigations"}</button><button className="button danger" disabled={busy} onClick={() => void act(async () => { await request(`/my/connections/${c.id}`, 'DELETE') })}>Disconnect</button></div></li>)}</ul><button className="button ghost" disabled={busy || !catalog.selected} onClick={() => void act(async () => { await request('/my/connections/select', 'POST', { connection_id: null }) })}>Use offline baseline</button></>}
    </section>{error && <p role="alert" className="error">{error}</p>}
  </section>
}
