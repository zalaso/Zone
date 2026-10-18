import { afterEach, expect, it } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { EventCard, fmt, referenceName, statusName } from './view'
import { PublicExperiment } from './LabVisuals'
import { errorMessage } from './api'
import type { LabEvent } from './types'

afterEach(cleanup)
const events: LabEvent[] = [
  { seq: 1, actor: 'agent', message: { type: 'experiment_request', request_id: 'opaque-experiment-012345abcdef', purpose: 'Measure motion.' } },
  { seq: 2, actor: 'agent', message: { type: 'hypothesis', hypothesis_id: 'opaque-hypothesis-012345abcdef', statement: 'Constant acceleration is plausible.', evidence: ['opaque-experiment-012345abcdef'] } },
  { seq: 3, actor: 'agent', message: { type: 'conclusion', final_hypothesis_id: 'opaque-hypothesis-012345abcdef', evidence: ['opaque-experiment-012345abcdef'], summary: 'More evidence is needed.', limits: ['One experiment.'], alternatives: [] } },
]

it('uses stable readable references across public history, without rendering opaque IDs', () => {
  const { container } = render(<>{events.map(event => <EventCard key={event.seq} event={event} events={events} />)}<PublicExperiment events={events} /></>)
  expect(container.textContent).toContain('Hypothesis 1 · Evidence: Experiment 1')
  expect(container.textContent).toContain('Final hypothesis: Hypothesis 1')
  expect(container.textContent).not.toContain('opaque-')
  expect(referenceName(events.slice(0, 1), 'hypothesis', 'opaque-hypothesis-012345abcdef')).toBe('Earlier hypothesis')
})

it('preserves small measurements and formats finite numbers in English', () => {
  expect(fmt(0.25)).toBe('0.25')
  expect(fmt(1 / 3)).toBe('0.3333')
  expect(fmt(0.000000125)).toBe('1.25E-7')
  expect(fmt(-0)).toBe('0')
  for (const value of [NaN, Infinity, undefined, 'raw']) expect(fmt(value)).toBe('—')
})

it('turns internal stop states into an actionable explanation', () => {
  render(<EventCard event={{ seq: 1, actor: 'apparatus', message: { type: 'investigation_stopped', reason: 'provider_error' } }} />)
  expect(screen.getByText('The model provider could not complete the request.')).toBeInTheDocument()
  expect(screen.queryByText('provider_error')).not.toBeInTheDocument()
  expect(statusName('awaiting_prediction')).toBe('Prediction needed')
})

it('shows reviewed English errors without exposing arbitrary backend or provider details', () => {
  expect(errorMessage(503, 'Chiamata agente non riuscita; nessun esperimento eseguito. Riprova esplicitamente.')).toContain('No experiment was run')
  expect(errorMessage(422, 'PRIVATE_EXCEPTION_SENTINEL')).not.toContain('SENTINEL')
  expect(errorMessage(429, 'Quota account esaurita: model_calls')).toContain('usage or request limit')
})
