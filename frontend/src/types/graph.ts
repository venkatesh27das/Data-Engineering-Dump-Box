export interface GraphNodeData {
  id: string;
  label: string;
  type: string;
  confidence: number | null;
  sources: string[];
  search_text: string;
}

export interface GraphEdgeData {
  id: string;
  source: string;
  target: string;
  label: string;
  confidence: number | null;
  search_text: string;
}

export interface GraphData {
  nodes: Array<{ data: GraphNodeData }>;
  edges: Array<{ data: GraphEdgeData }>;
  counts: { nodes: number; relationships: number; node_types: number; relationship_types: number };
}

export interface NodeRelationship {
  id: string;
  type: string;
  direction: "incoming" | "outgoing";
  other_node_id: string;
  other_node_label: string;
  confidence: number | null;
}

export interface GraphNodeDetail {
  id: string;
  name: string;
  type: string;
  labels: string[];
  confidence: number | null;
  description: string | null;
  sources: string[];
  properties: Record<string, unknown>;
  evidence: Array<Record<string, unknown>>;
  relationships: NodeRelationship[];
}

export interface CypherResult {
  rows: Array<Record<string, unknown>>;
  row_count: number;
}
