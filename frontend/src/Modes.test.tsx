import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { AgentDescription, MatchView, UniverseBuilder } from './Modes'
import type { AgentInfo, Match } from './types'

const agent: AgentInfo = { provider: 'offline_baseline', model: 'offline-affine-v1', real_model: false,
  settings: { max_calls: 20, max_turns: 15, max_points: 9, max_corrections: 2, timeout: 30 } }
const fake = vi.hoisted(() => ({ build: vi.fn(), generate: vi.fn() }))
vi.mock('./api', () => ({ api: { build: fake.build, generate: fake.generate } }))
beforeEach(() => { fake.build.mockReset(); fake.generate.mockReset() })

describe('modalità pubbliche locali', () => {
  it('identifica esplicitamente la baseline simulata e il costo del provider reale', () => {
    const { rerender } = render(<AgentDescription agent={agent} />)
    expect(screen.getByText(/non è un LLM/)).toBeInTheDocument()
    expect(screen.getByText(/Nessuna credenziale/)).toBeInTheDocument()
    rerender(<AgentDescription agent={{ ...agent, provider: 'openai', real_model: true }} />)
    expect(screen.getByText('Provider reale')).toBeInTheDocument()
    expect(screen.getByText(/tentativi di correzione/)).toBeInTheDocument()
  })

  it('blocca il passaggio all’agente fino al freeze umano, poi apre la sessione separata', () => {
    const change = vi.fn(async () => {})
    const match = { match_id: 'm', human_session_id: 'h', agent_session_id: 'a', complete: false,
      rules: { experiment_budget: 3, max_points: 9, max_turns: 15 }, human: { status: 'discovering' }, agent: { status: 'discovering' } } as Match
    const { rerender } = render(<MatchView match={match} current="h" busy={false} change={change} />)
    expect(screen.getByRole('button', { name: 'Indagine agente' })).toBeDisabled()
    rerender(<MatchView match={{ ...match, human: { ...match.human, status: 'scoring_pending' } }} current="h" busy={false} change={change} />)
    fireEvent.click(screen.getByRole('button', { name: 'Indagine agente' }))
    expect(change).toHaveBeenCalledWith('a')
    expect(screen.getByText(/Risposta umana congelata/)).toBeInTheDocument()
    rerender(<MatchView match={{ ...match, human: { ...match.human, status: 'stopped' } }} current="h" busy={false} change={change} />)
    expect(screen.getByRole('button', { name: 'Indagine agente' })).toBeEnabled()
    expect(screen.getByText(/arrestare anche quella/)).toBeInTheDocument()
  })

  it('registra soltanto il mondo restituito dopo la validazione del server', async () => {
    const world = { world_id: 'w1234567890abcdef', experiment_budget: 3 }
    fake.generate.mockResolvedValue({ world })
    const ready = vi.fn()
    const action = vi.fn(async (work: () => Promise<unknown>) => { await work() })
    render(<UniverseBuilder token="operator-test" busy={false} action={action} ready={ready} />)
    fireEvent.click(screen.getByRole('button', { name: 'Valida e registra mondo' }))
    await waitFor(() => expect(ready).toHaveBeenCalledWith(world))
    expect(fake.generate).toHaveBeenCalledWith(1, 3, 'operator-test')
    fireEvent.change(screen.getByLabelText('Metodo del costruttore'), { target: { value: 'author' } })
    fake.build.mockResolvedValue({ world })
    fireEvent.click(screen.getByRole('button', { name: 'Valida e registra mondo' }))
    await waitFor(() => expect(fake.build).toHaveBeenCalled())
    expect(screen.getByText(/escluso da Human vs AI/)).toBeInTheDocument()
  })
})
