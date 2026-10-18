import { useState, type FormEvent } from 'react'
import { api } from './api'
import { ResultView } from './view'
import type { ActivityKind } from './LabVisuals'
import type { AgentInfo, Match, WorldManifest } from './types'

export const modes = [
  ['scientist', 'Scientist', "Lead the investigation yourself: experiments, hypotheses and predictions, with a complete history."],
  ['human_vs_ai', 'Human vs AI', "Same world, budget and test states. Submit your answer first, then watch the agent. Histories stay separate."],
  ['watch_agent', 'Watch an Agent', "The agent proposes and explains. You approve, choose exploration or verification, and run every experiment."],
  ['world_of_day', 'World of the Day', "A persistent world for each UTC day. Investigate manually, as in Scientist."],
  ['build_universe', 'Build a Universe', "Generate a world or author a restricted AST law. The server validates it before making it available."],
] as const

export function AgentDescription({ agent }: { agent: AgentInfo }) {
  const plan = agent.provider === 'chatgpt'
  return <p className="field-hint"><strong>{plan ? "Real model · personal ChatGPT plan" : agent.real_model ? "Real model provider" : "Numerical offline baseline · not an LLM"}</strong><br />{agent.settings.max_calls} calls · {agent.settings.max_turns} turns. {plan ? "Each step, including corrections, uses your plan allowance. No API fallback. Check Usage and disable extra credits. Provider preview limitations apply; generated token limits are not supported." : agent.real_model ? "Each requested step can use your API allowance, including correction attempts." : "No credentials or provider calls."}</p>
}

export function UniverseBuilder({ token, busy, action, ready }: { token: string; busy: boolean;
  action: (work: () => Promise<unknown>, success: string, kind?: ActivityKind) => Promise<void>; ready: (world: WorldManifest) => void }) {
  const [kind, setKind] = useState('generate')
  const [building, setBuilding] = useState(false)
  const [created, setCreated] = useState<WorldManifest | null>(null)
  const [level, setLevel] = useState(1)
  const [budget, setBudget] = useState(3)
  const [law, setLaw] = useState('{\n  "level": 1,\n  "ax": {"op": "const", "value": 1},\n  "ay": {"op": "const", "value": -4}\n}')
  function submit(event: FormEvent) {
    event.preventDefault()
    setBuilding(true); setCreated(null)
    void action(async () => {
      let result: { world: WorldManifest }
      if (kind === 'generate') result = await api.generate(level, budget, token)
      else {
        let value: unknown
        try { value = JSON.parse(law) } catch { throw new Error("Invalid AST JSON. Check the text before submitting.") }
        result = await api.build(value, budget, token)
      }
      ready(result.world); setCreated(result.world)
    }, "World validated and selected. You can start an investigation.", 'world').finally(() => setBuilding(false))
  }
  return <section className="panel"><div className="panel-heading"><span className="kicker">World Forge</span><h2>Build a universe</h2></div><p>The generator creates a hidden law and validates the world before saving it. Level describes structural complexity; start with level 1. The experiment budget limits the number of runs in each investigation.</p><div className={`forge-visual ${building ? "is-building" : ""}`} aria-hidden="true"><span /><span /><span /><i /></div>{created && <p className="world-ready" role="status">World accepted. It is selected in New investigation. You can now start exploring.</p>}<form onSubmit={submit}>
    <label>Creation method<select value={kind} onChange={e => setKind(e.target.value)}><option value="generate">World Forge generator</option><option value="author">Advanced: author an AST law</option></select></label>
    {kind === 'generate' ? <label>Level<select value={level} onChange={e => setLevel(Number(e.target.value))}>{[1, 2, 3, 4, 5].map(n => <option key={n}>{n}</option>)}</select></label> : <label>World AST<textarea required maxLength={32000} rows={7} value={law} onChange={e => setLaw(e.target.value)} spellCheck={false} /></label>}
    <p className="field-hint">Levels 1–5 add structural complexity, not guaranteed difficulty. If writing an AST, use only allowed nodes. Do not paste Python code or LaTeX formulas.</p><details className="technical-notes"><summary>Writing an AST (advanced)</summary><p>Each law contains level, ax and ay. A const node has op and value (−100 to 100); a var node has op and name (x, y, vx or vy). add, sub and mul take two nodes in args. Level 1 allows constants only: change the example values to start.</p><p>Advanced operations include protected div, abs, sin, cos, tanh, norm, normalize and pow with an integer exponent from 0 to 3. The server checks arity, level, a maximum of 64 nodes and depth 12. Use the generator to investigate without already knowing the law.</p></details><label>Experiment budget<select value={budget} onChange={e => setBudget(Number(e.target.value))}>{[1, 2, 3, 4].map(n => <option key={n}>{n}</option>)}</select></label>
    <button className="button secondary" disabled={busy || !token}>Validate and create world</button></form><p className="field-hint">Numerical checks are bounded heuristics; no arbitrary code is executed. If you author the law, you know the answer, so the world is excluded from Human vs AI. The generator uses a private random seed.</p></section>
}

export function MatchView({ match, current, busy, change }: { match: Match; current: string; busy: boolean;
  change: (id: string) => Promise<void> }) {
  const humanFrozen = ['scoring_pending', 'scored', 'revealed'].includes(match.human.status)
  const humanStopped = match.human.status === 'stopped'
  return <section className="panel match-panel" aria-label={"Human and agent comparison"}><span className="kicker">Human vs AI · separate histories</span><h2>Compare on the same world</h2>
    <details className="technical-notes"><summary>Comparison identifier</summary><code>{match.match_id}</code></details><p>{match.rules.experiment_budget} experiments each · up to {match.rules.max_points} samples per experiment · {match.rules.max_turns} messages each. Exploration only, without changes or theoretical hints.</p>
    <div className="button-row"><button className="button secondary" disabled={busy || current === match.human_session_id} onClick={() => void change(match.human_session_id)}>Your investigation</button><button className="button secondary" disabled={busy || (!humanFrozen && !humanStopped) || current === match.agent_session_id} onClick={() => void change(match.agent_session_id)}>Agent investigation</button></div>
    <p className="field-hint">{match.complete ? "Comparison complete. Both answers are locked. Metrics stay separate." : humanStopped ? "Your investigation was stopped. Open the agent investigation to stop it too. Both must be closed before revealing the world." : humanFrozen ? "Your answer is locked. Continue with the agent. Results appear after both participants submit." : "Investigate and submit your own answer first. The agent will not receive your messages or answer."}</p>
    {match.complete && <div className="comparison-grid">{(['human', 'agent'] as const).map(side => <div key={side}><h3>{side === 'human' ? "You" : "Agent"}</h3><p>{match[side].observations} observations · {match[side].messages} messages{side === 'agent' ? ` · ${match.agent.agent?.calls ?? 0} calls · ${match.agent.agent?.invalid_responses ?? 0} invalid replies` : ''}</p>{match[side].scores && <ResultView scores={match[side].scores} />}</div>)}</div>}
  </section>
}
