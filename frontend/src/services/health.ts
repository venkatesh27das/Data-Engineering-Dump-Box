import type { HealthResponse } from "../types/health";

export async function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  const response = await fetch("/api/v1/health", { signal });

  if (!response.ok) {
    throw new Error("The API health check failed.");
  }

  return response.json() as Promise<HealthResponse>;
}
