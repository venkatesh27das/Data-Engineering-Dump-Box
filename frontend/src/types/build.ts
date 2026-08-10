export type ProcessingMode = "auto" | "structured" | "unstructured" | "hybrid";
export type GraphDepth = "metadata" | "entity_relationships" | "semantic" | "contextual";
export type SourceCategory = "structured" | "unstructured";

export interface ProjectDraft {
  name: string;
  knowledge_objective: string;
  processing_mode: ProcessingMode;
  graph_depth: GraphDepth;
  review_low_confidence: boolean;
  max_tokens: number;
}

export interface Project extends ProjectDraft {
  id: string;
  created_at: string;
  updated_at: string;
}

export interface SourceAsset {
  id: string;
  project_id: string;
  filename: string;
  original_filename: string;
  category: SourceCategory;
  extension: string;
  mime_type: string;
  size_bytes: number;
  storage_path: string;
  status: string;
  summary: string;
  created_at: string;
}
