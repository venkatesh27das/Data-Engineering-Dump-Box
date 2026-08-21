export type RunStatus = 'queued' | 'profiling' | 'planning' | 'extracting' | 'interpreting' | 'validating' | 'packaging' | 'needs_review' | 'completed' | 'failed' | 'cancelled'

export interface Workbook {
  id: string
  original_filename: string
  display_name: string
  file_type: string
  file_size_bytes: number
  purpose: string
  description: string
  created_at: string
  updated_at: string
  latest_run_id: string | null
  latest_status: RunStatus
  latest_confidence: number | null
  is_archived: boolean
}

export interface ProcessingRun {
  id: string
  workbook_id: string
  workbook_name: string
  purpose: string
  parent_run_id: string | null
  run_number: number
  trigger_type: string
  scope: string
  status: RunStatus
  current_stage: string
  progress_percent: number
  started_at: string | null
  completed_at: string | null
  duration_seconds: number | null
  overall_confidence: number | null
  output_unit_count: number | null
  error_message: string | null
}

export interface Asset {
  id: string
  asset_type: string
  title: string
  summary: string
  source_sheet: string | null
  source_range: string | null
  confidence: number
  review_status: string
}

export interface ReviewItem {
  id: string
  title: string
  description: string
  evidence: string
  suggested_action: string
  confidence: number
  severity: string
  status: string
}

export interface ModelStatus {
  reachable: boolean
  available_models: string[]
  reasoning_model: string
  vision_model: string
  embedding_model: string
  capability_check: string
  framework?: string
  roles: Record<string, {
    model: string
    selection: string
    enabled: boolean
    available: boolean
    status: string
  }>
  checks?: Record<string, {
    status: string
    model: string
    dimensions?: number
    structured_output?: boolean
    note?: string
    error?: string
  }>
}
