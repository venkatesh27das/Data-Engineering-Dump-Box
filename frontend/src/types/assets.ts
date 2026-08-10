export type AssetKind = "entities" | "relationships" | "concepts" | "facts" | "events";
export type ReviewStatus = "pending" | "approved" | "review" | "needs_attention" | "rejected";

export interface EvidenceReference {
  source_id: string;
  source_name: string;
  page: number | null;
  section: string | null;
  chunk_id: string | null;
  table: string | null;
  column: string | null;
  excerpt: string | null;
}

export interface AssetView {
  id: string;
  kind: AssetKind;
  name: string;
  asset_type: string;
  confidence: number;
  review_status: ReviewStatus;
  evidence: EvidenceReference[];
  aliases: string[];
  attributes: Record<string, string | number | boolean | null>;
  source_entity_id: string | null;
  target_entity_id: string | null;
}

export interface AssetPage {
  kind: AssetKind;
  items: AssetView[];
  total: number;
  page: number;
  page_size: number;
  available_types: string[];
  available_sources: string[];
}

export interface AssetOverview {
  package: {
    package_id: string;
    project_id: string;
    run_id: string;
    entity_count: number;
    relationship_count: number;
    concept_count: number;
    fact_count: number;
    event_count: number;
    quality_score: number;
    created_at: string;
  };
  quality: {
    overall_score: number;
    evidence_coverage: number;
    average_confidence: number;
    consistency: number;
    completeness: number;
    duplicate_rate: number;
    unresolved_references: number;
    disposition: string;
    issues: Array<{ id: string; severity: string; code: string; message: string }>;
  };
}

export interface AssetFilters {
  search: string;
  assetType: string;
  source: string;
  minimumConfidence: string;
  reviewStatus: string;
}
