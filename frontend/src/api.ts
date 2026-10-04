import type { AgentInfo, LabEvent, Match, Scores, SessionStatus, WorldManifest } from './types'

export class ApiError extends Error {
  constructor(message: string, readonly status: number) { super(message) }
}

export async function request<T>(path: string, method = 'GET', body?: unknown, token?: string, extraHeaders: Record<string, string> = {}): Promise<T> {
  const headers: Record<string, string> = { ...extraHeaders }
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (token) headers['X-Zone-Token'] = token
  let response: Response
  try {
    response = await fetch(`/v1${path}`, {
      method, headers, body: body === undefined ? undefined : JSON.stringify(body),
      cache: 'no-store', credentials: 'omit',
    })
  } catch {
    throw new ApiError('Il backend locale non risponde. Controlla che sia avviato.', 0)
  }
  if (!response.ok) {
    let detail = `Richiesta non riuscita (${response.status}).`
    try {
      const data = await response.json() as { detail?: string }
      if (typeof data.detail === 'string') detail = data.detail
    } catch { /* Use the status message. */ }
    throw new ApiError(detail, response.status)
  }
  return response.json() as Promise<T>
}

export const api = {
  worlds: async () => (await request<{ worlds: WorldManifest[] }>('/worlds')).worlds,
  modes: () => request<{ modes: string[]; agent: AgentInfo }>('/modes'),
  daily: () => request<{ day: string; timezone: string; world: WorldManifest }>('/worlds/daily'),
  build: (law: unknown, budget: number, token: string) => request<{ world: WorldManifest }>('/worlds/build', 'POST', { law, budget }, token),
  generate: (level: number, budget: number, token: string) => request<{ world: WorldManifest }>('/worlds/generate', 'POST', { level, budget }, token),
  create: (world_id: string, token: string, mode = 'scientist') => request<SessionStatus & { agent_token: string | null }>('/sessions', 'POST', { world_id, mode }, token),
  createMatch: (world_id: string, token: string) => request<Match & { human_agent_token: string }>('/matches', 'POST', { world_id }, token),
  match: (id: string) => request<Match>(`/matches/${encodeURIComponent(id)}`),
  step: (id: string, version: number, token: string) => request<SessionStatus>(`/sessions/${encodeURIComponent(id)}/agent/step`, 'POST', { expected_version: version }, token),
  status: (id: string) => request<SessionStatus>(`/sessions/${encodeURIComponent(id)}`),
  events: async (id: string) => {
    const events: LabEvent[] = []
    let after = 0
    for (;;) {
      const page = await request<{ events: LabEvent[]; next_after: number }>(`/sessions/${encodeURIComponent(id)}/events?after=${after}`)
      events.push(...page.events)
      if (!page.events.length || page.events.length < 100) return events
      if (page.next_after <= after) throw new ApiError('Cursore del replay non valido.', 0)
      after = page.next_after
    }
  },
  message: (id: string, version: number, message: unknown, token: string) =>
    request<SessionStatus>(`/sessions/${encodeURIComponent(id)}/messages`, 'POST', { expected_version: version, message }, token),
  run: (id: string, version: number, request_id: string, token: string) =>
    request<SessionStatus>(`/sessions/${encodeURIComponent(id)}/run`, 'POST', { expected_version: version, request_id }, token),
  stop: (id: string, version: number, reason: string, token: string) =>
    request<SessionStatus>(`/sessions/${encodeURIComponent(id)}/stop`, 'POST', { expected_version: version, reason }, token),
  submit: (id: string, version: number, submission: unknown, token: string) =>
    request<SessionStatus>(`/sessions/${encodeURIComponent(id)}/submission`, 'POST', { expected_version: version, submission }, token),
  score: (id: string, version: number, token: string) =>
    request<SessionStatus>(`/sessions/${encodeURIComponent(id)}/score`, 'POST', { expected_version: version }, token),
  result: async (id: string) => (await request<{ scores: Scores }>(`/sessions/${encodeURIComponent(id)}/result`)).scores,
  reveal: (id: string, version: number, token: string) =>
    request<{ world: unknown; audit: unknown }>(`/sessions/${encodeURIComponent(id)}/reveal`, 'POST', { expected_version: version, confirm: 'reveal' }, token),
}
