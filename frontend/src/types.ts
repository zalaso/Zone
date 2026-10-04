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
}

export type WorldManifest = {
  world_id: string
  level?: number
  experiment_budget: number
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
