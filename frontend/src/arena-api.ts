import { request } from './api'
import type { LabEvent, Scores, SessionStatus } from './types'

export type IntegrityInfo = {
  state: string; split: string | null; manifest_hash: string | null; commitment: string | null
  eligible?: boolean; flags?: string[]
}

export type ArenaChallenge = {
  challenge_id: string; world_id: string; name: string; closed: boolean
  rules: { experiment_budget: number; max_messages: number; max_points: number; execution_policy: string }
  integrity?: IntegrityInfo
}
export type ArenaAgent = {
  agent_id: string; name: string; model: string; kind: string
  quotas: { sessions: number; requests: number; experiments: number }
  usage: { sessions: number; requests: number; experiments: number; invalid: number }
  tokens: { token_id: string; expires_at: number; revoked: boolean }[]
}
export type ArenaTrial = SessionStatus & {
  challenge_id: string; agent_id: string; account: ArenaAgent; messages: number; observations: number
  scores: Scores | null; events?: LabEvent[]
  integrity?: IntegrityInfo
  resources: { agent_requests: number; invalid_requests: number; external_model_calls: null; external_cost: null }
}
export type ArenaBoard = {
  challenge: ArenaChallenge; trials: ArenaTrial[]
  comparison_scope?: string
  dimensions: Record<string, { session_id: string; value: number; rank: number }[]>
}

export const arenaApi = {
  read: <T>(path: string, token: string) => request<T>(`/arena/${path}`, 'GET', undefined, token, { 'X-Zone-Arena-Version': '1' }),
  // Callers can retain the key across a transport retry. There are no automatic retries.
  write: <T>(path: string, body: unknown, token: string, key: string = crypto.randomUUID()) =>
    request<T>(`/arena/${path}`, 'POST', body, token, { 'X-Zone-Arena-Version': '1', 'Idempotency-Key': key }),
}
