import { request } from "./projects";
import type { AgentEvent, Run, RunDetail, RunQueueItem } from "../types/runs";

export function startRun(projectId: string): Promise<Run> {
  return request<Run>(`/api/v1/projects/${projectId}/runs`, { method: "POST" });
}

export function getRun(projectId: string, runId: string, signal?: AbortSignal): Promise<Run> {
  return request<Run>(`/api/v1/projects/${projectId}/runs/${runId}`, { signal });
}

export function getRunEvents(projectId: string, runId: string, signal?: AbortSignal): Promise<AgentEvent[]> {
  return request<AgentEvent[]>(`/api/v1/projects/${projectId}/runs/${runId}/events`, { signal });
}

export function listRuns(signal?: AbortSignal): Promise<RunQueueItem[]> {
  return request<RunQueueItem[]>("/api/v1/runs", { signal });
}

export function getRunDetail(runId: string, signal?: AbortSignal): Promise<RunDetail> {
  return request<RunDetail>(`/api/v1/runs/${runId}`, { signal });
}

export function cancelRun(runId: string): Promise<RunQueueItem> {
  return request<RunQueueItem>(`/api/v1/runs/${runId}/cancel`, { method: "POST" });
}

export function deleteRun(runId: string): Promise<void> {
  return request<void>(`/api/v1/runs/${runId}`, { method: "DELETE" });
}
