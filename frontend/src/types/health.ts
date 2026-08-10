export type IntegrationStatus =
  | "connected"
  | "disconnected"
  | "not_configured"
  | "configuration_pending";

export interface HealthResponse {
  api: "ok";
  lmstudio: IntegrationStatus;
  neo4j: IntegrationStatus;
}
