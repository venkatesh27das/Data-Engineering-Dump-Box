import { request } from "./projects";
import type { Publication, PublicationStatus } from "../types/publication";

export function getPublicationStatus(projectId: string, signal?: AbortSignal): Promise<PublicationStatus> {
  return request<PublicationStatus>(`/api/v1/projects/${projectId}/publish/status`, { signal });
}

export function publishToNeo4j(projectId: string): Promise<Publication> {
  return request<Publication>(`/api/v1/projects/${projectId}/publish/neo4j`, { method: "POST" });
}
