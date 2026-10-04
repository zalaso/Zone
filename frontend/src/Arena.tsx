import { useState, type FormEvent } from 'react'
import { arenaApi, type ArenaAgent, type ArenaBoard, type ArenaChallenge, type ArenaTrial } from './arena-api'
import { EventCard, fmt, ResultView } from './view'
import type { WorldManifest } from './types'

const dimensionNames: Record<string, string> = {
  acceleration_rmse: 'RMSE numerico complessivo', interpolation_rmse: 'RMSE interpolation',
  extrapolation_rmse: 'RMSE extrapolation', functional_rmse: 'RMSE funzionale AST',
  ast_nodes: 'Complessità · nodi AST', calibration_nll: 'Calibrazione · NLL',
  missed_dependencies: 'Dipendenze omesse', spurious_dependencies: 'Dipendenze spurie',
}

export function Arena({ worlds }: { worlds: WorldManifest[] }) {
  const [token, setToken] = useState('')
  const [challenges, setChallenges] = useState<ArenaChallenge[]>([])
  const [cid, setCid] = useState('')
  const [worldId, setWorldId] = useState(worlds.find(w => !w.builder_version)?.world_id ?? '')
  const [name, setName] = useState('Prima challenge Arena')
  const [agentName, setAgentName] = useState('')
  const [model, setModel] = useState('')
  const [agents, setAgents] = useState<ArenaAgent[]>([])
  const [issued, setIssued] = useState<{ token: string | null; token_id: string; agent_id: string } | null>(null)
  const [showToken, setShowToken] = useState(false)
  const [trials, setTrials] = useState<ArenaTrial[]>([])
  const [trial, setTrial] = useState<ArenaTrial | null>(null)
  const [board, setBoard] = useState<ArenaBoard | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [revealChecked, setRevealChecked] = useState(false)
  const [reveal, setReveal] = useState<unknown>(null)
  const [audit, setAudit] = useState<unknown>(null)
  const selected = challenges.find(c => c.challenge_id === cid)
  const selectedWorld = worldId || worlds.find(w => !w.builder_version)?.world_id || ''

  async function act(work: () => Promise<void>) {
    setBusy(true); setError('')
    try { await work() } catch (e) { setError(e instanceof Error ? e.message : 'Operazione non riuscita.') }
    finally { setBusy(false) }
  }
  async function refresh(selectedId = cid) {
    const listing = await arenaApi.read<{ challenges: ArenaChallenge[] }>('challenges', token)
    setChallenges(listing.challenges)
    const actual = selectedId || listing.challenges[0]?.challenge_id || ''
    setCid(actual)
    const registered = await arenaApi.read<{ agents: ArenaAgent[] }>('agents', token)
    setAgents(registered.agents)
    if (actual) {
      setTrials((await arenaApi.read<{ trials: ArenaTrial[] }>(`challenges/${actual}/trials`, token)).trials)
      setBoard(await arenaApi.read<ArenaBoard>(`challenges/${actual}/leaderboard`, token))
    }
    if (trial && trial.challenge_id === actual) setTrial(await arenaApi.read<ArenaTrial>(`sessions/${trial.session_id}`, token))
    else setTrial(null)
  }
  async function trialAction(kind: string, extra: Record<string, unknown>) {
    if (!trial) return
    await arenaApi.write(`sessions/${trial.session_id}/${kind}`, { expected_version: trial.version, ...extra }, token)
    setTrial(await arenaApi.read<ArenaTrial>(`sessions/${trial.session_id}`, token))
    await refresh()
  }
  function submit(e: FormEvent, work: () => Promise<void>) { e.preventDefault(); void act(work) }

  return <div className="arena">
    <section className="panel"><span className="kicker">07 / BYOA v1</span><h2>Zone Arena</h2>
      <p>Collega il tuo agente al laboratorio locale. L’agente propone e consegna; l’operatore approva ed esegue ogni lancio. Nessuna chiamata a un modello parte da questa pagina.</p>
      <p className="notice">Challenge comparabili: stesso mondo, probe, budget e limiti; solo esplorazione, senza modifiche o suggerimenti teorici. Un trial per agente e challenge.</p>
      <form onSubmit={e => submit(e, () => refresh())}><label>Token operatore Arena<input type="password" autoComplete="off" required value={token} onChange={e => { setToken(e.target.value); setIssued(null); setShowToken(false) }} /></label>
        <button className="button primary" disabled={busy}>Connetti Arena</button></form>
      <p className="field-hint">Token in memoria; ricaricare la pagina li elimina. Il protocollo per il tuo client è in docs/arena.md.</p>
    </section>
    {error && <p role="alert" className="error">{error} Rileggi lo stato prima di ripetere un’azione.</p>}
    <div className="setup-grid">
      <section className="panel"><h2>Challenge</h2><form onSubmit={e => submit(e, async () => {
        const created = await arenaApi.write<ArenaChallenge>('challenges', { world_id: selectedWorld, name }, token)
        await refresh(created.challenge_id)
      })}><label>Nome challenge<input required maxLength={80} value={name} onChange={e => setName(e.target.value)} /></label>
        <label>Mondo Forge Arena<select required value={selectedWorld} onChange={e => setWorldId(e.target.value)}>{worlds.filter(w => !w.builder_version).map(w => <option key={w.world_id} value={w.world_id}>{w.world_id} · {w.experiment_budget} lanci</option>)}</select></label>
        <button className="button secondary" disabled={busy || !token || !selectedWorld}>Crea challenge</button></form>
        <label>Challenge selezionata<select value={cid} onChange={e => { setTrial(null); setReveal(null); setRevealChecked(false); void act(() => refresh(e.target.value)) }}><option value="">Seleziona</option>{challenges.map(c => <option key={c.challenge_id} value={c.challenge_id}>{c.name} · {c.closed ? 'chiusa' : 'aperta'}</option>)}</select></label>
        {selected && <><p className="session-id">{cid}</p><p>{selected.rules.experiment_budget} esperimenti · {selected.rules.max_messages} messaggi agente · massimo {selected.rules.max_points} punti per lancio.</p>
          <button className="button secondary" disabled={busy || selected.closed || trials.some(t => !['scored', 'stopped', 'revealed'].includes(t.status))} onClick={() => void act(async () => { await arenaApi.write(`challenges/${cid}/close`, {}, token); await refresh() })}>Chiudi challenge</button></>}
      </section>
      <section className="panel"><h2>Credenziali degli agenti</h2><form onSubmit={e => submit(e, async () => {
        setIssued(await arenaApi.write('agents', { name: agentName, model }, token)); setShowToken(false); await refresh()
      })}><label>Nome agente<input required maxLength={80} value={agentName} onChange={e => setAgentName(e.target.value)} /></label><label>Modello dichiarato<input required maxLength={80} value={model} onChange={e => setModel(e.target.value)} /></label><button className="button secondary" disabled={busy || !token}>Registra agente</button></form>
        {issued && <div className="notice"><p>Credenziale emessa una sola volta. Consegnala al tuo client locale; non inserirla in prompt o registri.</p><p>ID agente: <code>{issued.agent_id}</code></p><label>Token agente Arena<input readOnly type={showToken ? 'text' : 'password'} autoComplete="off" value={issued.token ?? ''} /></label><button className="button tiny" onClick={() => setShowToken(!showToken)}>{showToken ? 'Nascondi token' : 'Mostra token'}</button><button className="button tiny" onClick={() => setIssued(null)}>Dimentica token</button></div>}
        {agents.map(agent => <div className="arena-agent" key={agent.agent_id}><h3>{agent.name}</h3><p>{agent.model} · dichiarazione non verificata</p><p>Quote account: trial {agent.usage.sessions}/{agent.quotas.sessions}, richieste {agent.usage.requests}/{agent.quotas.requests}, esperimenti {agent.usage.experiments}/{agent.quotas.experiments}; invalide {agent.usage.invalid}.</p>
          <button className="button tiny" disabled={busy} onClick={() => void act(async () => { setIssued(await arenaApi.write(`agents/${agent.agent_id}/tokens`, {}, token)); setShowToken(false); await refresh() })}>Emetti nuovo token per {agent.name}</button>
          {agent.tokens.map(t => <p key={t.token_id}><code>{t.token_id.slice(0, 12)}</code> · {t.revoked ? 'revocato' : `scade ${new Date(t.expires_at * 1000).toLocaleString('it-IT')}`} {!t.revoked && <button className="button tiny danger" disabled={busy} onClick={() => void act(async () => { await arenaApi.write(`tokens/${t.token_id}/revoke`, {}, token); if (issued?.token_id === t.token_id) setIssued(null); await refresh() })}>Revoca token {t.token_id.slice(0, 12)}</button>}</p>)}</div>)}
      </section>
    </div>
    {selected && <section className="panel"><h2>Trial e operatore</h2><div className="button-row"><button className="button secondary" disabled={busy || !token} onClick={() => void act(() => refresh())}>Aggiorna Arena</button><button className="button secondary" disabled={busy || !token} onClick={() => void act(async () => setAudit(await arenaApi.read('audit', token)))}>Mostra audit</button></div>
      <p>Avvia il trial dal client BYOA con l’ID challenge e il token agente. La pagina non manda messaggi per conto dell’agente.</p>
      {trials.map(t => <button className="button secondary" key={t.session_id} disabled={busy} onClick={() => void act(async () => { setTrial(await arenaApi.read(`sessions/${t.session_id}`, token)); setReveal(null); setRevealChecked(false) })}>{t.account.name} · {t.status}</button>)}
      {trial && <div><h3>{trial.account.name} · {trial.status}</h3><p className="session-id">{trial.session_id}</p><p>{trial.executed_experiments} lanci · {trial.observations} osservazioni · {trial.messages} messaggi</p>
        {trial.status === 'awaiting_decision' && <div className="button-row">{(['approve', 'reject'] as const).map(action => <button className={`button ${action === 'approve' ? 'primary' : 'secondary'}`} key={action} disabled={busy} onClick={() => void act(() => trialAction('messages', { message: { type: 'operator_decision', request_id: trial.pending_request_id, action, reason: 'Decisione operativa Arena.' } }))}>{action === 'approve' ? 'Approva richiesta Arena' : 'Rifiuta richiesta Arena'}</button>)}</div>}
        {trial.status === 'awaiting_mode' && <button className="button primary" disabled={busy} onClick={() => void act(() => trialAction('messages', { message: { type: 'execution_mode', request_id: trial.pending_request_id, mode: 'exploration' } }))}>Conferma esplorazione Arena</button>}
        {trial.status === 'ready_to_run' && <button className="button primary" disabled={busy} onClick={() => void act(() => trialAction('run', { request_id: trial.pending_request_id }))}>Esegui esperimento Arena</button>}
        {trial.status === 'scoring_pending' && <button className="button primary" disabled={busy} onClick={() => void act(() => trialAction('score', {}))}>Riprendi punteggio Arena</button>}
        {!['scored', 'stopped', 'revealed'].includes(trial.status) && <details><summary>Arresta questo trial</summary><button className="button danger" disabled={busy} onClick={() => void act(() => trialAction('stop', { reason: trial.status === 'execution_started' ? 'interrupted_execution' : 'operator_stop' }))}>Conferma arresto Arena</button></details>}
        {selected.closed && ['scored', 'stopped'].includes(trial.status) && <><label className="check-row"><input type="checkbox" checked={revealChecked} onChange={e => setRevealChecked(e.target.checked)} />Confermo il reveal privato Arena</label><button className="button danger" disabled={busy || !revealChecked} onClick={() => void act(async () => { await trialAction('reveal', { confirm: 'reveal' }); setReveal(await arenaApi.read(`sessions/${trial.session_id}/reveal`, token)) })}>Rivela mondo Arena</button></>}
        {trial.scores && <ResultView scores={trial.scores} />}
        <div className="timeline">{trial.events?.map(event => <EventCard key={event.seq} event={event} />)}</div>
      </div>}
    </section>}
    {board && <section className="panel"><h2>Leaderboard per dimensione</h2><p>Confronto limitato a questa challenge. Nessun punteggio unico né vincitore complessivo. Metriche mancanti escluse dalla rispettiva classifica; parità allo stesso rango.</p>
      <div className="arena-boards">{Object.entries(board.dimensions).map(([dimension, rows]) => <div className="table-scroll" key={dimension}><table><caption>{dimensionNames[dimension] ?? dimension} · valori minori prima</caption><thead><tr><th>Rango</th><th>Agente</th><th>Valore</th></tr></thead><tbody>{rows.length ? rows.map(row => <tr key={row.session_id}><td>{row.rank}</td><td>{board.trials.find(t => t.session_id === row.session_id)?.account.name}</td><td>{fmt(row.value)}</td></tr>) : <tr><td colSpan={3}>Nessun valore disponibile</td></tr>}</tbody></table></div>)}</div>
      <h3>Risorse e arresti</h3><div className="table-scroll"><table><thead><tr><th>Agente</th><th>Stato</th><th>Osservazioni</th><th>Lanci</th><th>Richieste API</th><th>Invalide</th></tr></thead><tbody>{board.trials.map(t => <tr key={t.session_id}><td>{t.account.name}</td><td>{t.status}</td><td>{t.observations}</td><td>{t.executed_experiments}</td><td>{t.resources.agent_requests}</td><td>{t.resources.invalid_requests}</td></tr>)}</tbody></table></div><p className="field-hint">Chiamate LLM, token e costi del client esterno: non misurati. Il numero di richieste API non è un numero di chiamate al modello.</p>
    </section>}
    {audit !== null && <section className="panel"><h2>Audit Arena · prima pagina</h2><pre className="private-record">{JSON.stringify(audit, null, 2)}</pre></section>}
    {reveal !== null && <section className="panel"><h2>Record privato Arena</h2><pre className="private-record">{JSON.stringify(reveal, null, 2)}</pre></section>}
  </div>
}
