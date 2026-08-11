import type { SourceAsset } from "./build";

export type RunStatus = "queued" | "running" | "completed" | "failed" | "canceled";

export interface PlanStep {
  specialist: "source_analyst" | "knowledge_engineer" | "graph_modeller" | "quality_reviewer";
  tool: string;
  reason: string;
}

export interface ExecutionPlan {
  source_modalities: Array<"structured" | "unstructured">;
  graph_levels: string[];
  steps: PlanStep[];
  plan_source: "deep_agent" | "deterministic_fallback";
}

export interface Run {
  id: string;
  project_id: string;
  status: RunStatus;
  current_stage: string;
  plan: ExecutionPlan | null;
  package_id: string | null;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface AgentEvent {
  id: string;
  run_id: string;
  sequence: number;
  timestamp: string;
  stage: string;
  status: "queued" | "running" | "completed" | "warning" | "failed" | "canceled";
  title: string;
  message: string;
  event_type: "stage" | "tool" | "replan" | "quality" | "run";
}

export interface AssetPackageSummary {
  package_id: string;
  project_id: string;
  run_id: string;
  entity_count: number;
  relationship_count: number;
  concept_count: number;
  fact_count: number;
  event_count: number;
  quality_score: number;
  created_at: string;
}

export interface RunArtifact {
  id: string;
  run_id: string;
  stage: string;
  artifact_type: string;
  name: string;
  status: "temporary" | "completed" | "failed";
  record_count: number;
  parent_ids: string[];
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface RunQueueItem {
  run: Run;
  project_name: string;
  source_count: number;
  event_count: number;
  artifact_count: number;
  package: AssetPackageSummary | null;
}

export interface RunLineageEdge {
  parent_id: string;
  child_id: string;
  relationship: string;
}

export interface RunDetail {
  item: RunQueueItem;
  sources: SourceAsset[];
  events: AgentEvent[];
  temporary_assets: RunArtifact[];
  lineage: RunLineageEdge[];
}
