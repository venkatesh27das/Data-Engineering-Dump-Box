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

export interface AssetContent {
  asset: Asset
  content_kind: 'image' | 'table' | 'json'
  record: Record<string, unknown> | null
  record_source: string | null
  preview_rows: Record<string, unknown>[]
  preview_columns: string[]
  lineage: LineageEdge[]
  preview_available: boolean
  preview_file: string | null
  data_file: string | null
}

export interface RunEvent {
  event_id: string
  run_id: string
  timestamp: string
  stage: string
  status: string
  progress_percent: number
  message: string
  details: Record<string, unknown>
}

export interface TraceStage {
  stage: string
  status: string
  progress_percent: number
  message: string
  started_at: string
  duration_seconds: number | null
  event_count: number
  details: Record<string, unknown>
}

export interface LineageEdge {
  edge_id?: string
  source_id?: string
  source_name?: string
  relationship_type?: string
  target_id?: string
  target_name?: string
  relationship_description?: string
  evidence?: string[]
  confidence?: number
  provenance?: Record<string, unknown>
  [key: string]: unknown
}

export interface RunTrace {
  run_id: string
  status: RunStatus
  current_stage: string
  progress_percent: number
  error_message: string | null
  events: RunEvent[]
  stages: TraceStage[]
  processing_plan: {
    workbook_archetype?: string
    steps?: string[]
    excluded_steps?: string[]
    reasoning_summary?: string
    agent_runtime?: Record<string, unknown>
    applied_directives?: Record<string, unknown>[]
  }
  lineage: {
    technical: LineageEdge[]
    business: LineageEdge[]
    technical_count: number
    business_count: number
  }
  asset_counts: Record<string, number>
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
