import type { Project, ProjectDraft, SourceAsset } from "../types/build";

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
  }
}

export async function request<T>(input: RequestInfo | URL, init?: RequestInit): Promise<T> {
  const response = await fetch(input, init);
  if (!response.ok) {
    let message = "The request could not be completed.";
    try {
      const payload = (await response.json()) as { detail?: string };
      message = payload.detail ?? message;
    } catch {
      // Keep the concise fallback message when the response is not JSON.
    }
    throw new ApiError(message, response.status);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export function createProject(draft: ProjectDraft): Promise<Project> {
  return request<Project>("/api/v1/projects", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(draft),
  });
}

export function getProject(projectId: string, signal?: AbortSignal): Promise<Project> {
  return request<Project>(`/api/v1/projects/${projectId}`, { signal });
}

export function updateProject(projectId: string, draft: ProjectDraft): Promise<Project> {
  return request<Project>(`/api/v1/projects/${projectId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(draft),
  });
}

export function listSources(projectId: string, signal?: AbortSignal): Promise<SourceAsset[]> {
  return request<SourceAsset[]>(`/api/v1/projects/${projectId}/sources`, { signal });
}

export function uploadSource(projectId: string, file: File): Promise<SourceAsset> {
  const body = new FormData();
  body.append("file", file);
  return request<SourceAsset>(`/api/v1/projects/${projectId}/sources`, {
    method: "POST",
    body,
  });
}

export function deleteSource(projectId: string, sourceId: string): Promise<void> {
  return request<void>(`/api/v1/projects/${projectId}/sources/${sourceId}`, {
    method: "DELETE",
  });
}
