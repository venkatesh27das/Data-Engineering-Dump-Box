export type IntegrationStatus =
  | "connected"
  | "disconnected"
  | "not_configured"
  | "configuration_pending";

export interface HealthResponse {
  api: "ok";
  model_provider?: IntegrationStatus;
  model_provider_name?: string;
  lmstudio: IntegrationStatus;
  neo4j: IntegrationStatus;
}
