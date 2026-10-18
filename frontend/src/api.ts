import type { AgentInfo, LabEvent, Match, Scores, SessionStatus, WorldManifest } from './types'

export class ApiError extends Error {
  constructor(message: string, readonly status: number) { super(message) }
}

let accountMode = false
let csrfToken: string | undefined
export function accountTransport(enabled: boolean, csrf?: string) {
  accountMode = enabled; csrfToken = csrf
}

// Backend protocol messages remain unchanged. Display only reviewed English copy,
// never an arbitrary exception, provider reply or validation payload.
export function errorMessage(status: number, detail?: string): string {
  const known: Record<string, string> = {
    'Connessione disconnessa; nessun fallback. Crea una nuova sessione con un’altra AI.': 'This AI connection is disconnected. Start a new investigation with another connection. There is no automatic fallback.',
    'Archivio API non configurato dal gestore. Usa il connettore locale.': 'Server-side API storage is unavailable. Use the local connector.',
    'Massimo dieci connessioni attive.': 'You have reached the limit of ten active connections. Disconnect one before adding another.',
    'Registrazione non ancora aperta. Usa un invito.': 'Registration is closed on this installation. Use an invitation.',
    'Accesso con password non abilitato.': 'Password sign-in is disabled on this installation. Use an access key.',
    'Recupero autonomo non abilitato.': 'Self-service recovery is disabled. Contact the installation owner.',
    'Chiamata agente non riuscita; nessun esperimento eseguito. Riprova esplicitamente.': 'The model request failed. No experiment was run. Check the history before explicitly requesting another step.',
    'Errore agente; nessun esperimento eseguito.': 'The agent could not complete this step. No experiment was run. Check the history.',
    'Limite iniziale di venti mondi personali raggiunto.': 'You have reached the initial limit of twenty personal worlds. Choose an existing world.',
  }
  if (detail && known[detail]) return known[detail]
  return ({ 400: 'Check your input and try again.', 401: 'Sign in again or check your access credentials.',
    403: 'This action is not allowed for your account or installation. Check access and configuration.',
    404: 'This item is unavailable. Refresh the list or check your selection.',
    409: 'The state has changed or this item already exists. Refresh before taking another action.',
    413: 'The submitted content is too large. Shorten it and try again.',
    422: 'Check the required fields and allowed ranges. Experiment duration must match its measurement interval.',
    429: 'A usage or request limit was reached. Check Account for remaining usage and wait before trying again.',
    503: 'This service is temporarily unavailable. Check the investigation history before explicitly retrying.' } as Record<number, string>)[status]
    ?? 'The request could not be completed. Check the server status and refresh before trying again.'
}

export async function request<T>(path: string, method = 'GET', body?: unknown, token?: string, extraHeaders: Record<string, string> = {}): Promise<T> {
  const headers: Record<string, string> = { ...extraHeaders }
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (token && (!accountMode || path.startsWith('/arena/'))) headers['X-Zone-Token'] = token
  if (accountMode && csrfToken && method !== 'GET' && method !== 'HEAD') headers['X-Zone-CSRF'] = csrfToken
  let response: Response
  try {
    response = await fetch(`/v1${path}`, {
      method, headers, body: body === undefined ? undefined : JSON.stringify(body),
      cache: 'no-store', credentials: accountMode ? 'same-origin' : 'omit',
    })
  } catch {
    throw new ApiError("Zone is not responding. Check that the local server is running.", 0)
  }
  if (!response.ok) {
    if (accountMode && response.status === 401) window.dispatchEvent(new Event('zone-auth-expired'))
    let detail: string | undefined
    try {
      const data = await response.json() as { detail?: string }
      if (typeof data.detail === 'string') detail = data.detail
    } catch { /* Use the status message. */ }
    throw new ApiError(errorMessage(response.status, detail), response.status)
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
      if (page.next_after <= after) throw new ApiError("The history could not be loaded. Refresh the investigation.", 0)
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
