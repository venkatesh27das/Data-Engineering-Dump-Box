export type RunStatus = "queued" | "running" | "completed" | "failed";

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
  status: "queued" | "running" | "completed" | "warning" | "failed";
  title: string;
  message: string;
  event_type: "stage" | "tool" | "replan" | "quality" | "run";
}
