import { request } from "./projects";
import type { CypherResult, GraphData, GraphNodeDetail } from "../types/graph";

export function getGraph(projectId: string, signal?: AbortSignal): Promise<GraphData> {
  return request<GraphData>(`/api/v1/projects/${projectId}/graph`, { signal });
}

export function getGraphNode(projectId: string, nodeId: string, signal?: AbortSignal): Promise<GraphNodeDetail> {
  return request<GraphNodeDetail>(`/api/v1/projects/${projectId}/graph/node/${encodeURIComponent(nodeId)}`, { signal });
}

export function runCypherQuery(projectId: string, query: string): Promise<CypherResult> {
  return request<CypherResult>(`/api/v1/projects/${projectId}/graph/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, parameters: {} }),
  });
}
