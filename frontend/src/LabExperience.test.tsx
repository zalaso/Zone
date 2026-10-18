import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, act } from '@testing-library/react'
import { Activity, ExperimentStage, experimentScene, PublicExperiment } from './LabVisuals'
import { ScientificText } from './ScientificText'
import { HelpCenter, ModeGuide } from './Guide'
import { Profile } from './Profile'
import type { LabEvent } from './types'
import type { Account } from './Identity'

afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals() })
const experiment = { initial_position: { x: 2, y: 1 }, initial_velocity: { x: 3, y: 0 }, duration: 1, observation_interval: .5 }
const points = [{ t: 0, x: 2, y: 1 }, { t: .5, x: 3, y: 2 }, { t: 1, x: 4, y: 1 }]
const event = (seq: number, message: LabEvent['message']): LabEvent => ({ seq, actor: 'agent', message })

it('mostra la configurazione modificata prima della previsione, senza calcolare il moto', () => {
  const events = [event(1, { type: 'experiment_request', request_id: 'e1', experiment, purpose: 'Prova' }), event(2, { type: 'operator_decision', request_id: 'e1', action: 'modify', modified_experiment: { ...experiment, duration: .5 } })]
  const scene = experimentScene(events)
  expect(scene.experiment?.duration).toBe(.5)
  expect(scene.points).toEqual([])
  const { container } = render(<PublicExperiment events={events} />)
  expect(screen.getByText(/settings include the operator/)).toBeInTheDocument()
  expect(container.querySelector('.observed-path')).toBeNull()
  expect(screen.queryByRole('button', { name: "Play measurements" })).not.toBeInTheDocument()
})

it('usa solo gli eventi nel replay, mantiene distinti previsione e misure e non legge verità private', () => {
  const events = [event(1, { type: 'experiment_request', request_id: 'e1', experiment }), event(2, { type: 'prediction', request_id: 'e1', points }), event(3, { type: 'observation', request_id: 'e1', status: 'ok', points, private_truth: 'PRIVATE_LAW_SENTINEL' })]
  expect(experimentScene(events.slice(0, 2)).points).toEqual([])
  const { container } = render(<PublicExperiment events={events} />)
  expect(container.querySelectorAll('.sample-point')).toHaveLength(3)
  expect(container.querySelector('.predicted-path')).not.toBeNull()
  expect(container.textContent).not.toContain('PRIVATE_LAW_SENTINEL')
  fireEvent.click(screen.getByLabelText(/Show preregistered prediction/))
  expect(container.querySelector('.predicted-path')).toBeNull()
  expect(container.querySelectorAll('.sample-point')).toHaveLength(3)
  const next = [...events, event(4, { type: 'experiment_request', request_id: 'e2', experiment })]
  expect(experimentScene(next).points).toEqual([])
  expect(experimentScene(next).prediction).toEqual([])
})

it('non inventa dati dopo un lancio fallito o con coordinate non finite', () => {
  const events = [event(1, { type: 'observation', request_id: 'e1', status: 'error', points: [] })]
  render(<PublicExperiment events={events} />)
  expect(screen.getByText(/No trajectory is invented/)).toBeInTheDocument()
  expect(experimentScene([event(1, { type: 'observation', request_id: 'e1', status: 'ok', points: [{ t: 0, x: Infinity, y: 0 }, ...points] })]).points).toEqual(points)
})

it('il replay parte solo con un clic e si arresta sull’ultimo campione, senza richieste di rete', () => {
  vi.useFakeTimers()
  const fetcher = vi.fn(); vi.stubGlobal('fetch', fetcher)
  render(<ExperimentStage experiment={experiment} points={points} />)
  act(() => vi.advanceTimersByTime(2000))
  expect(screen.getByLabelText("Observed sample")).toHaveValue('0')
  fireEvent.click(screen.getByRole('button', { name: "Play measurements" }))
  act(() => vi.advanceTimersByTime(650))
  expect(screen.getByLabelText("Observed sample")).toHaveValue('1')
  fireEvent.click(screen.getByRole('button', { name: "Pause replay" }))
  act(() => vi.advanceTimersByTime(2000))
  expect(screen.getByLabelText("Observed sample")).toHaveValue('1')
  fireEvent.change(screen.getByLabelText("Observed sample"), { target: { value: '2' } })
  expect(screen.getByText(/t = 1 s/)).toBeInTheDocument()
  expect(fetcher).not.toHaveBeenCalled()
})

it('impagina LaTeX con MathML accessibile e lascia HTML e comandi non fidati inerti', () => {
  const { container, rerender } = render(<ScientificText text={String.raw`Ipotesi: $a_y=-\gamma v_y$. <script>alert(1)</script>`} />)
  expect(container.querySelector('math')).not.toBeNull()
  expect(container.querySelector('script')).toBeNull()
  rerender(<ScientificText text={String.raw`$$\includegraphics{https://example.invalid/x}$$ $\href{javascript:alert(1)}{x}$`} />)
  expect(container.querySelector('img')).toBeNull()
  expect(container.querySelector('a')).toBeNull()
  rerender(<ScientificText text={String.raw`$\frac{1}{$`} />)
  expect(container.textContent).toContain(String.raw`\frac{1}{`)
})

it('rende la guida ricercabile e spiega il confronto prima di impostarlo', () => {
  const { unmount } = render(<ModeGuide mode="human_vs_ai" />)
  expect(screen.getByText(/Investigate first/)).toBeInTheDocument()
  expect(screen.getByText(/only exploration/)).toBeInTheDocument()
  unmount(); render(<HelpCenter />)
  fireEvent.change(screen.getByLabelText("Find a term"), { target: { value: 'baseline' } })
  expect(screen.getByRole('definition')).toHaveTextContent('not a language model')
  fireEvent.change(screen.getByLabelText("Find a term"), { target: { value: 'inesistente' } })
  expect(screen.getByText(/No matching term/)).toBeInTheDocument()
})

it('distingue l’attesa del modello dal lancio e mostra solo il tempo trascorso', () => {
  vi.useFakeTimers(); const { rerender } = render(<Activity kind="model" />)
  expect(screen.getByText(/private reasoning is not visible/)).toBeInTheDocument()
  act(() => vi.advanceTimersByTime(2000))
  expect(screen.getByText('Time elapsed: 2 s')).toBeInTheDocument()
  rerender(<Activity kind="world" />)
  expect(screen.getByText(/not a completion percentage/)).toBeInTheDocument()
})

it('il profilo mostra quote distinte e consente di aggiornarle senza inferenza', async () => {
  const account = { account_id: 'synthetic-account', handle: 'alice', role: 'member', quotas: { sessions: 30, experiments: 100, model_calls: 50, read: 120, write: 30, run: 10 }, usage: { sessions: 2, experiments: 3, model_calls: 4 } } as Account
  let reads = 0
  const fetcher = vi.fn(async (path: string) => new Response(JSON.stringify(path.endsWith('/me') ? { account: { ...account, usage: { ...account.usage, experiments: 5 + reads++ } } } : { connections: [], selected: null })))
  vi.stubGlobal('fetch', fetcher)
  render(<Profile account={account} connect={vi.fn()} sessions={vi.fn()} />)
  await screen.findByText(/Numerical offline baseline/)
  await screen.findByText('5 of 100')
  expect(screen.getByRole('progressbar', { name: 'Limit experiments' })).toHaveAttribute('value', '5')
  fireEvent.click(screen.getByRole('button', { name: "Refresh usage" }))
  await screen.findByText('6 of 100')
  expect(fetcher.mock.calls.map(([path]) => path)).toEqual(['/v1/my/connections', '/v1/auth/me', '/v1/auth/me'])
})
