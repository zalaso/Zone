export type Experiment = {
  initial_position: { x: number; y: number }
  initial_velocity: { x: number; y: number }
  duration: number
  observation_interval: number
}

export type LabEvent = {
  seq: number
  actor: 'agent' | 'operator' | 'apparatus'
  message: Record<string, unknown> & { type: string }
}

export type SessionStatus = {
  session_id: string
  version: number
  status: string
  executed_experiments: number
  remaining_experiments: number
  pending_request_id: string | null
  pending_question_id: string | null
  running_request_id: string | null
  challenge_available: boolean
  result_available: boolean
  revealed: boolean
  mode?: string
  participant?: 'human' | 'agent'
  managed_agent?: boolean
  match_id?: string | null
  agent?: AgentInfo | null
}

export type AgentInfo = {
  provider: string
  model: string
  real_model: boolean
  settings: { max_calls: number; max_turns: number; max_corrections: number; max_points: number; timeout: number }
  calls?: number
  turns?: number
  invalid_responses?: number
}

export type Match = {
  match_id: string
  human_session_id: string
  agent_session_id: string
  complete: boolean
  rules: { experiment_budget: number; max_points: number; max_turns: number }
  human: SessionStatus & { scores: Scores | null; observations: number; messages: number }
  agent: SessionStatus & { scores: Scores | null; observations: number; messages: number }
}

export type WorldManifest = {
  world_id: string
  level?: number
  experiment_budget: number
  integrity?: { state: string; split: string | null }
  [key: string]: unknown
}

export type Probe = {
  probe_id: string
  category: 'interpolation' | 'extrapolation'
  x: number
  y: number
  vx: number
  vy: number
}

export type Scores = Record<string, unknown>
