export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface BriefSummary {
  id: string
  title: string
  status: string
  created_at: string
  subject_name: string
  subject_type: string
  subject_industry: string | null
  pipeline_stages: Record<string, string>
}

export interface BriefDetail {
  id: string
  title: string
  status: string
  created_at: string
  brief_dict: Record<string, any>
  pipeline_stages: Record<string, string>
}

export interface ArtifactInfo {
  filename: string
  label: string
  size: number
}

export interface PipelineStageStatus {
  stage: string
  status: string
  started_at?: string
  completed_at?: string
  error_message?: string
}

export interface GeoMetrics {
  total_queries: number
  mentioned_count: number
  visibility: number
  avg_rank: number
  rank_1_count: number
  sov: number
  sentiment_positive: number
  sentiment_negative: number
  sentiment_neutral: number
  competitor_metrics: { name: string; mention_count: number; sov: number }[]
  persona_metrics: { persona_name: string; visibility: number; avg_rank: number }[]
}

export interface PromptInfo {
  name: string
  label: string
}

export interface PromptContent {
  name: string
  content: string
  char_count: number
}

export interface Settings {
  api_key_set: boolean
  api_key_preview: string
  model: string
  data_dir: string
  selectors: Record<string, string>
}

// WebSocket event types
export type InterviewEvent =
  | { type: 'history'; messages: ChatMessage[]; interview_done: boolean; brief_dict: Record<string, any> | null }
  | { type: 'opening'; content: string }
  | { type: 'token'; content: string }
  | { type: 'complete'; content: string }
  | { type: 'interview_complete'; brief_dict: Record<string, any> }
  | { type: 'error'; message: string }

export type PipelineEvent =
  | { type: 'log'; line: string }
  | { type: 'stage_complete'; stage: string; data: any }
  | { type: 'stage_result'; stage: string; data: any }
  | { type: 'status'; running: boolean; stage: string | null }
