export type PublicationState = "running" | "completed" | "failed";

export interface Publication {
  id: string;
  project_id: string;
  package_id: string;
  status: PublicationState;
  nodes_published: number;
  relationships_published: number;
  assets_skipped: number;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface PublicationStatus {
  configured: boolean;
  connected: boolean;
  latest: Publication | null;
  history: Publication[];
}
