import { type UseMutationResult, useMutation, useQuery } from "@tanstack/react-query";
import {
  BoxSelect,
  ExternalLink,
  Hand,
  LoaderCircle,
  Maximize,
  MousePointer2,
  Network,
  Play,
  RotateCcw,
  Search,
  ZoomIn,
} from "lucide-react";
import { useCallback, useMemo, useState } from "react";

import { Card } from "../../components/Card";
import { EmptyState } from "../../components/EmptyState";
import { FailureState } from "../../components/FailureState";
import { PageIntro } from "../../components/PageIntro";
import { ApiError } from "../../services/projects";
import { getGraph, getGraphNode, runCypherQuery } from "../../services/graph";
import type { CypherResult, GraphData, GraphNodeDetail } from "../../types/graph";
import { GraphCanvas } from "./GraphCanvas";
import { colorForType, filterGraph } from "./graphUtils";

const PROJECT_STORAGE_KEY = "knowledge-graph-builder.project-id";
const defaultQuery = "MATCH (n:KnowledgeAsset)\nWHERE n.project_id = $project_id\nRETURN n.name AS name, n.asset_type AS type, n.confidence AS confidence\nLIMIT 50";
const templates = [
  { label: "All nodes", query: defaultQuery },
  { label: "Supplier relationships", query: "MATCH (n:KnowledgeAsset)-[r]-(m:KnowledgeAsset)\nWHERE n.project_id = $project_id AND n.asset_type = 'Supplier'\nRETURN n.name AS supplier, type(r) AS relationship, m.name AS connected_asset\nLIMIT 50" },
  { label: "Low confidence", query: "MATCH (n:KnowledgeAsset)\nWHERE n.project_id = $project_id AND n.confidence < 0.85\nRETURN n.name AS name, n.asset_type AS type, n.confidence AS confidence\nLIMIT 50" },
];

export function GraphExplorerPage() {
  const projectId = new URLSearchParams(window.location.search).get("projectId") ?? localStorage.getItem(PROJECT_STORAGE_KEY);
  const [search, setSearch] = useState("");
  const [nodeType, setNodeType] = useState("");
  const [relationshipType, setRelationshipType] = useState("");
  const [depth, setDepth] = useState(2);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [query, setQuery] = useState(defaultQuery);

  const graphQuery = useQuery({ queryKey: ["graph", projectId], queryFn: ({ signal }) => getGraph(projectId!, signal), enabled: Boolean(projectId), retry: false });
  const nodeQuery = useQuery({ queryKey: ["graph-node", projectId, selectedId], queryFn: ({ signal }) => getGraphNode(projectId!, selectedId!, signal), enabled: Boolean(projectId && selectedId), retry: false });
  const cypherMutation = useMutation({ mutationFn: () => runCypherQuery(projectId!, query) });
  const selectNode = useCallback((nodeId: string | null) => setSelectedId(nodeId), []);

  const graph = graphQuery.data;
  const nodeTypes = useMemo(() => [...new Set(graph?.nodes.map((node) => node.data.type) ?? [])].sort(), [graph]);
  const relationshipTypes = useMemo(() => [...new Set(graph?.edges.map((edge) => edge.data.label) ?? [])].sort(), [graph]);
  const filtered = useMemo(() => graph ? filterGraph(graph, search, nodeType, relationshipType, selectedId, depth) : null, [depth, graph, nodeType, relationshipType, search, selectedId]);
  const legend = useMemo(() => nodeTypes.map((type) => ({ type, count: graph?.nodes.filter((node) => node.data.type === type).length ?? 0 })), [graph, nodeTypes]);
  const clearFilters = () => { setSearch(""); setNodeType(""); setRelationshipType(""); setDepth(2); };

  return (
    <div className="page graph-page">
      <PageIntro action={<a className="secondary-button" href="https://console.neo4j.io/" rel="noreferrer" target="_blank">Open in Neo4j Browser <ExternalLink aria-hidden="true" size={14} /></a>} description="Explore and visualize your knowledge graph published in Neo4j Aura." title="Graph Explorer" />

      <div className="graph-toolbar" aria-label="Graph filters">
        <label className="graph-search"><Search aria-hidden="true" size={16} /><input aria-label="Search graph" onChange={(event) => setSearch(event.target.value)} placeholder="Search nodes, relationships, properties..." value={search} /></label>
        <select aria-label="Node types" onChange={(event) => setNodeType(event.target.value)} value={nodeType}><option value="">Node Types (All)</option>{nodeTypes.map((type) => <option key={type}>{type}</option>)}</select>
        <select aria-label="Relationship types" onChange={(event) => setRelationshipType(event.target.value)} value={relationshipType}><option value="">Relationship Types (All)</option>{relationshipTypes.map((type) => <option key={type}>{type}</option>)}</select>
        <label className="depth-control"><span>Depth</span><select aria-label="Traversal depth" onChange={(event) => setDepth(Number(event.target.value))} value={depth}><option value={1}>1 Hop</option><option value={2}>2 Hops</option><option value={3}>3 Hops</option></select></label>
        <button className="clear-filter-button" onClick={clearFilters} type="button"><RotateCcw size={13} />Clear Filters</button>
      </div>

      {!projectId ? <Card><EmptyState description="Build and publish a project before opening the graph explorer." icon={Network} title="No active project" /></Card> : null}
      {graphQuery.isLoading ? <Card><EmptyState compact description="Loading published nodes and relationships from Neo4j Aura…" icon={LoaderCircle} title="Loading graph" /></Card> : null}
      {graphQuery.error ? <Card><FailureState description={graphQuery.error instanceof ApiError ? graphQuery.error.message : "The published graph could not be loaded."} onRetry={() => void graphQuery.refetch()} title="Graph unavailable" /></Card> : null}
      {filtered ? (
        <>
          <div className="graph-shell-grid explorer-grid">
            <div className="graph-side-stack">
              <Card title="Graph Overview"><GraphOverview graph={filtered} /></Card>
              <Card title="Legend"><div className="graph-legend">{legend.map((item) => <div key={item.type}><i style={{ background: colorForType(item.type) }} /><span>{item.type}</span><strong>{item.count}</strong></div>)}</div></Card>
              <Card title="Controls"><div className="graph-control-guide"><span><Hand size={13} />Drag <small>Pan</small></span><span><ZoomIn size={13} />Scroll <small>Zoom</small></span><span><MousePointer2 size={13} />Click <small>Select node</small></span><span><BoxSelect size={13} />Shift + Drag <small>Box select</small></span><button onClick={() => window.dispatchEvent(new Event("knowledge-graph-fit"))} type="button"><Maximize size={13} />Reset View</button></div></Card>
            </div>
            <Card className="graph-canvas explorer-canvas">
              {filtered.nodes.length ? <GraphCanvas graph={filtered} onSelect={selectNode} selectedId={selectedId} /> : <EmptyState description="Adjust filters or publish approved assets to Neo4j." icon={Search} title="No graph elements match" />}
            </Card>
            <Card className="node-detail-card" title="Node Details">
              {nodeQuery.isLoading ? <EmptyState compact description="Loading node properties and provenance…" icon={LoaderCircle} title="Loading node" /> : null}
              {nodeQuery.isError ? <FailureState compact description="The selected node details could not be loaded." onRetry={() => void nodeQuery.refetch()} title="Node unavailable" /> : null}
              {nodeQuery.data ? <NodeDetails node={nodeQuery.data} onSelect={selectNode} /> : null}
              {!selectedId && !nodeQuery.isLoading && !nodeQuery.isError ? <EmptyState compact description="Select a graph node to inspect its properties, relationships, and provenance." icon={Search} title="No node selected" /> : null}
            </Card>
          </div>
          <CypherPanel isConfigured={Boolean(projectId)} mutation={cypherMutation} onQueryChange={setQuery} query={query} />
        </>
      ) : null}
    </div>
  );
}

function GraphOverview({ graph }: { graph: GraphData }) {
  return <div className="overview-grid"><div><strong>{graph.counts.nodes.toLocaleString()}</strong><small>Nodes</small></div><div><strong>{graph.counts.relationships.toLocaleString()}</strong><small>Relationships</small></div><div><strong>{graph.counts.node_types}</strong><small>Node Types</small></div><div><strong>{graph.counts.relationship_types}</strong><small>Relationship Types</small></div></div>;
}

type DetailTab = "overview" | "properties" | "relationships" | "evidence";
function NodeDetails({ node, onSelect }: { node: GraphNodeDetail; onSelect: (id: string) => void }) {
  const [tab, setTab] = useState<DetailTab>("overview");
  const tabs: DetailTab[] = ["overview", "properties", "relationships", "evidence"];
  return (
    <div className="node-details">
      <div className="node-detail-heading"><i style={{ borderColor: colorForType(node.type), color: colorForType(node.type) }}><Network size={17} /></i><div><h3>{node.name}</h3><p>{node.id}</p></div><span>{node.type}</span></div>
      <div className="detail-tabs">{tabs.map((item) => <button className={tab === item ? "active" : ""} key={item} onClick={() => setTab(item)} type="button">{item}</button>)}</div>
      <div className="detail-content">
        {tab === "overview" ? <><DetailRow label="Labels"><div className="detail-chips">{node.labels.map((label) => <span key={label}>{label}</span>)}</div></DetailRow><DetailRow label="Confidence"><div className="detail-confidence"><strong>{node.confidence == null ? "—" : `${Math.round(node.confidence * 100)}%`}</strong><i><em style={{ width: `${(node.confidence ?? 0) * 100}%` }} /></i></div></DetailRow><DetailRow label="Description"><p>{node.description ?? "No description supplied."}</p></DetailRow><DetailRow label="Sources"><div className="detail-chips">{node.sources.map((source) => <span key={source}>{source}</span>)}</div></DetailRow></> : null}
        {tab === "properties" ? <dl className="property-list">{Object.entries(node.properties).filter(([key, value]) => value != null && !["evidence_json", "attributes_json"].includes(key)).map(([key, value]) => <div key={key}><dt>{key.replaceAll("_", " ")}</dt><dd>{typeof value === "object" ? JSON.stringify(value) : String(value)}</dd></div>)}</dl> : null}
        {tab === "relationships" ? <div className="relationship-list">{node.relationships.map((relationship) => <button key={relationship.id} onClick={() => onSelect(relationship.other_node_id)} type="button"><i className={`direction-${relationship.direction}`} /> <span><strong>{relationship.type}</strong><small>{relationship.direction} • {relationship.other_node_label}</small></span><b>{relationship.confidence == null ? "" : `${Math.round(relationship.confidence * 100)}%`}</b></button>)}{!node.relationships.length ? <p>No relationships found.</p> : null}</div> : null}
        {tab === "evidence" ? <div className="node-evidence">{node.evidence.map((evidence, index) => <article key={index}><strong>{String(evidence.source_name ?? "Source")}</strong><small>{[evidence.page ? `Page ${evidence.page}` : null, evidence.section, evidence.table ? `Table ${evidence.table}` : null, evidence.column ? `Column ${evidence.column}` : null].filter(Boolean).join(" • ")}</small>{evidence.excerpt ? <blockquote>{String(evidence.excerpt)}</blockquote> : null}</article>)}{!node.evidence.length ? <p>No evidence references stored.</p> : null}</div> : null}
      </div>
    </div>
  );
}

function DetailRow({ label, children }: { label: string; children: React.ReactNode }) { return <section className="detail-row"><h4>{label}</h4>{children}</section>; }

function CypherPanel({ query, onQueryChange, mutation, isConfigured }: { query: string; onQueryChange: (value: string) => void; mutation: UseMutationResult<CypherResult, Error, void>; isConfigured: boolean }) {
  return (
    <div className="cypher-grid">
      <Card title="Read-only Cypher" trailing={<select aria-label="Template query" onChange={(event) => onQueryChange(templates[Number(event.target.value)].query)}><option value={0}>Template Queries</option>{templates.slice(1).map((template, index) => <option key={template.label} value={index + 1}>{template.label}</option>)}</select>}>
        <div className="cypher-editor"><textarea aria-label="Cypher query" onChange={(event) => onQueryChange(event.target.value)} spellCheck={false} value={query} /><button disabled={!isConfigured || mutation.isPending} onClick={() => mutation.mutate()} type="button">{mutation.isPending ? <LoaderCircle className="spin" size={14} /> : <Play size={14} />}Run Query</button></div>
        {mutation.isError ? <div className="query-error">{mutation.error.message}</div> : null}
      </Card>
      <Card title="Query Results" trailing={mutation.data ? <span className="asset-count">{mutation.data.row_count} rows</span> : null}>
        <div className="query-results">{mutation.data?.rows.length ? <pre>{JSON.stringify(mutation.data.rows.slice(0, 20), null, 2)}</pre> : <p>{mutation.data ? "The query completed successfully with no matching rows." : "Run a project-scoped, read-only query to inspect results."}</p>}</div>
      </Card>
    </div>
  );
}
