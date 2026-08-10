import { request } from "./projects";
import type { AgentEvent, Run } from "../types/runs";

export function startRun(projectId: string): Promise<Run> {
  return request<Run>(`/api/v1/projects/${projectId}/runs`, { method: "POST" });
}

export function getRun(projectId: string, runId: string, signal?: AbortSignal): Promise<Run> {
  return request<Run>(`/api/v1/projects/${projectId}/runs/${runId}`, { signal });
}

export function getRunEvents(projectId: string, runId: string, signal?: AbortSignal): Promise<AgentEvent[]> {
  return request<AgentEvent[]>(`/api/v1/projects/${projectId}/runs/${runId}/events`, { signal });
}
