import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BadgeCheck,
  Boxes,
  ChevronLeft,
  ChevronRight,
  CircleAlert,
  FileSearch,
  Lightbulb,
  Network,
  ScanSearch,
  Search,
  Send,
  Sparkles,
  ThumbsDown,
  Users,
} from "lucide-react";
import { useEffect, useState } from "react";

import { Card } from "../../components/Card";
import { EmptyState } from "../../components/EmptyState";
import { FailureState } from "../../components/FailureState";
import { PageIntro } from "../../components/PageIntro";
import { ApiError } from "../../services/projects";
import { getAssetOverview, listAssets, reviewAsset } from "../../services/assets";
import { getPublicationStatus, publishToNeo4j } from "../../services/publication";
import type { AssetFilters, AssetKind, AssetView } from "../../types/assets";

const PROJECT_STORAGE_KEY = "knowledge-graph-builder.project-id";
const tabs: Array<{ id: AssetKind; label: string }> = [
  { id: "entities", label: "Entities" }, { id: "relationships", label: "Relationships" },
  { id: "concepts", label: "Concepts" }, { id: "facts", label: "Facts" }, { id: "events", label: "Events" },
];
const emptyFilters: AssetFilters = { search: "", assetType: "", source: "", minimumConfidence: "", reviewStatus: "" };

function percent(value: number): string { return `${Math.round(value * 100)}%`; }
function titleCase(value: string): string { return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase()); }

export function GraphAssetsPage() {
  const queryClient = useQueryClient();
  const projectId = new URLSearchParams(window.location.search).get("projectId") ?? localStorage.getItem(PROJECT_STORAGE_KEY);
  const [kind, setKind] = useState<AssetKind>("entities");
  const [filters, setFilters] = useState<AssetFilters>(emptyFilters);
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<AssetView | null>(null);

  const overviewQuery = useQuery({
    queryKey: ["asset-overview", projectId],
    queryFn: ({ signal }) => getAssetOverview(projectId!, signal),
    enabled: Boolean(projectId),
    retry: (count, error) => !(error instanceof ApiError && error.status === 404) && count < 1,
  });
  const assetsQuery = useQuery({
    queryKey: ["assets", projectId, kind, filters, page],
    queryFn: ({ signal }) => listAssets(projectId!, kind, filters, page, signal),
    enabled: Boolean(projectId && overviewQuery.data),
    placeholderData: (previous) => previous,
  });
  const publicationQuery = useQuery({
    queryKey: ["publication-status", projectId],
    queryFn: ({ signal }) => getPublicationStatus(projectId!, signal),
    enabled: Boolean(projectId && overviewQuery.data),
  });

  useEffect(() => {
    if (selected) {
      setSelected(assetsQuery.data?.items.find((asset) => asset.id === selected.id) ?? null);
    }
  }, [assetsQuery.data, selected]);

  const reviewMutation = useMutation({
    mutationFn: ({ asset, decision }: { asset: AssetView; decision: "approve" | "review" | "reject" }) => reviewAsset(projectId!, asset.id, decision),
    onSuccess: ({ asset }) => {
      setSelected(asset);
      void queryClient.invalidateQueries({ queryKey: ["assets", projectId] });
      void queryClient.invalidateQueries({ queryKey: ["asset-overview", projectId] });
    },
  });
  const publishMutation = useMutation({
    mutationFn: () => publishToNeo4j(projectId!),
    onSuccess: (publication) => {
      queryClient.setQueryData(["publication-status", projectId], (current: typeof publicationQuery.data) => current ? { ...current, latest: publication, history: [publication, ...current.history] } : current);
    },
  });

  const updateFilter = (key: keyof AssetFilters, value: string) => { setFilters((current) => ({ ...current, [key]: value })); setPage(1); };
  const switchKind = (next: AssetKind) => { setKind(next); setFilters(emptyFilters); setPage(1); setSelected(null); };
  const overview = overviewQuery.data;
  const assetPage = assetsQuery.data;
  const totalPages = Math.max(1, Math.ceil((assetPage?.total ?? 0) / (assetPage?.page_size ?? 10)));
  const publicationStatus = publicationQuery.data;

  const metrics = [
    { label: "Entities", value: overview?.package.entity_count, icon: Users, tone: "violet" },
    { label: "Relationships", value: overview?.package.relationship_count, icon: Network, tone: "blue" },
    { label: "Concepts", value: overview?.package.concept_count, icon: Lightbulb, tone: "green" },
    { label: "Facts", value: overview?.package.fact_count, icon: FileSearch, tone: "orange" },
    { label: "Quality Score", value: overview ? percent(overview.quality.overall_score) : undefined, icon: Sparkles, tone: "pink" },
  ];

  return (
    <div className="page">
      <PageIntro description="Review, validate and publish generated knowledge assets." title="Graph Assets" />
      <div className="metric-grid">
        {metrics.map(({ label, value, icon: Icon, tone }) => <Card className="metric-card" key={label}><span className={`metric-icon metric-${tone}`}><Icon aria-hidden="true" size={20} /></span><div><strong>{value ?? "—"}</strong><small>{label}</small></div></Card>)}
      </div>

      {!projectId || (overviewQuery.error instanceof ApiError && overviewQuery.error.status === 404) ? (
        <Card><EmptyState description="Run the Knowledge Asset Builder to create your first reviewable package." icon={Boxes} title="No package generated" /></Card>
      ) : null}
      {overviewQuery.isLoading ? <Card><EmptyState compact description="Loading the latest generated package…" icon={Sparkles} title="Preparing asset review" /></Card> : null}
      {overviewQuery.isError && !(overviewQuery.error instanceof ApiError && overviewQuery.error.status === 404) ? <Card><FailureState description="The generated package could not be loaded. Check the backend and retry." onRetry={() => void overviewQuery.refetch()} title="Asset package unavailable" /></Card> : null}
      {overview ? (
        <>
          <div className="assets-shell-grid">
            <Card title="Generated Asset Review" trailing={<span className="asset-count">{assetPage?.total ?? 0} assets</span>}>
              <div className="tab-strip" role="tablist">
                {tabs.map((tab) => <button aria-selected={kind === tab.id} className={kind === tab.id ? "active" : ""} key={tab.id} onClick={() => switchKind(tab.id)} role="tab" type="button">{tab.label}</button>)}
              </div>
              <div className="asset-filters">
                <label className="asset-search"><Search size={14} /><input aria-label="Search assets" onChange={(event) => updateFilter("search", event.target.value)} placeholder="Search assets" value={filters.search} /></label>
                <select aria-label="Filter by type" onChange={(event) => updateFilter("assetType", event.target.value)} value={filters.assetType}><option value="">All types</option>{assetPage?.available_types.map((type) => <option key={type}>{type}</option>)}</select>
                <select aria-label="Filter by source" onChange={(event) => updateFilter("source", event.target.value)} value={filters.source}><option value="">All sources</option>{assetPage?.available_sources.map((source) => <option key={source}>{source}</option>)}</select>
                <select aria-label="Filter by confidence" onChange={(event) => updateFilter("minimumConfidence", event.target.value)} value={filters.minimumConfidence}><option value="">Any confidence</option><option value="0.9">90%+</option><option value="0.8">80%+</option><option value="0.6">60%+</option></select>
                <select aria-label="Filter by review status" onChange={(event) => updateFilter("reviewStatus", event.target.value)} value={filters.reviewStatus}><option value="">All statuses</option><option value="approved">Approved</option><option value="review">Review</option><option value="needs_attention">Needs attention</option><option value="pending">Pending</option><option value="rejected">Rejected</option></select>
              </div>
              <div className="asset-table-wrap">
                <table className="asset-table">
                  <thead><tr><th>Asset Name</th><th>Type</th><th>Source</th><th>Confidence</th><th>Status</th><th aria-label="Actions" /></tr></thead>
                  <tbody>
                    {assetPage?.items.map((asset) => (
                      <tr className={selected?.id === asset.id ? "selected" : ""} key={asset.id} onClick={() => setSelected(asset)}>
                        <td><strong>{asset.name}</strong><small>{asset.id}</small></td><td><span className="type-chip">{asset.asset_type}</span></td><td>{asset.evidence[0]?.source_name ?? "—"}</td><td><span className={`confidence confidence-${asset.confidence >= .9 ? "high" : asset.confidence >= .75 ? "medium" : "low"}`}>{percent(asset.confidence)}</span></td><td><span className={`review-status review-${asset.review_status}`}>{titleCase(asset.review_status)}</span></td><td><button aria-label={`Inspect ${asset.name}`} className="icon-button" onClick={() => setSelected(asset)} type="button"><ChevronRight size={15} /></button></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {assetsQuery.isLoading && !assetPage ? <div className="source-loading"><Sparkles size={15} /> Loading assets…</div> : null}
                {assetsQuery.isError ? <FailureState compact description="This asset category could not be loaded." onRetry={() => void assetsQuery.refetch()} title="Assets unavailable" /> : null}
                {!assetsQuery.isLoading && !assetsQuery.isError && assetPage?.items.length === 0 ? <EmptyState compact description="Adjust the filters or choose another asset category." icon={Search} title="No assets match filter" /> : null}
              </div>
              <div className="asset-pagination"><span>Page {page} of {totalPages}</span><div><button disabled={page <= 1} onClick={() => setPage((current) => current - 1)} type="button"><ChevronLeft size={15} /> Previous</button><button disabled={page >= totalPages} onClick={() => setPage((current) => current + 1)} type="button">Next <ChevronRight size={15} /></button></div></div>
            </Card>
            <Card title="Selected Asset">
              {selected ? <SelectedAsset asset={selected} isPending={reviewMutation.isPending} onDecision={(decision) => reviewMutation.mutate({ asset: selected, decision })} /> : <EmptyState compact description="Choose an asset to inspect confidence, attributes and source evidence." icon={ScanSearch} title="Nothing selected" />}
              {reviewMutation.isError ? <div className="query-error" role="alert">{reviewMutation.error instanceof Error ? reviewMutation.error.message : "The review decision could not be saved."}</div> : null}
            </Card>
          </div>
          <Card className="quality-card" title="Validation & Quality Summary" trailing={<span className={`quality-disposition disposition-${overview.quality.disposition.toLowerCase()}`}><CircleAlert size={13} />{titleCase(overview.quality.disposition)}</span>}>
            <div className="quality-grid">
              {[{ label: "Evidence Coverage", value: overview.quality.evidence_coverage }, { label: "Confidence Avg.", value: overview.quality.average_confidence }, { label: "Consistency", value: overview.quality.consistency }, { label: "Completeness", value: overview.quality.completeness }].map((metric) => <div key={metric.label}><span><strong>{metric.label}</strong><b>{percent(metric.value)}</b></span><i><em style={{ width: percent(metric.value) }} /></i></div>)}
              <div className="publication-control">
                <button className="publish-button" disabled={!publicationStatus?.connected || publishMutation.isPending} onClick={() => publishMutation.mutate()} title={!publicationStatus?.configured ? "Add Neo4j Aura credentials to .env" : !publicationStatus.connected ? "Neo4j Aura is not reachable" : "Safely MERGE approved assets"} type="button"><Send size={16} />{publishMutation.isPending ? "Publishing…" : "Publish Approved Assets to Neo4j"}</button>
                {!publicationStatus?.configured ? <small>Configure Neo4j Aura to enable publishing.</small> : null}
                {publicationQuery.isError ? <small className="publication-error">Publication status is unavailable. Check the Neo4j connection.</small> : null}
                {publicationStatus?.latest ? <small className={publicationStatus.latest.status === "failed" ? "publication-error" : ""}>Last publish: {publicationStatus.latest.nodes_published} nodes, {publicationStatus.latest.relationships_published} relationships • {titleCase(publicationStatus.latest.status)}</small> : null}
                {publishMutation.isError ? <small className="publication-error">{publishMutation.error instanceof Error ? publishMutation.error.message : "Publication failed."}</small> : null}
              </div>
            </div>
          </Card>
        </>
      ) : null}
    </div>
  );
}

function SelectedAsset({ asset, isPending, onDecision }: { asset: AssetView; isPending: boolean; onDecision: (decision: "approve" | "review" | "reject") => void }) {
  return (
    <div className="selected-asset">
      <div className="selected-heading"><span className="metric-icon metric-violet"><Boxes size={18} /></span><div><h3>{asset.name}</h3><p>{asset.asset_type} • {asset.id}</p></div></div>
      <dl className="asset-details"><div><dt>Confidence</dt><dd>{percent(asset.confidence)}</dd></div><div><dt>Review Status</dt><dd><span className={`review-status review-${asset.review_status}`}>{titleCase(asset.review_status)}</span></dd></div>{asset.aliases.length ? <div><dt>Aliases</dt><dd>{asset.aliases.join(", ")}</dd></div> : null}{Object.entries(asset.attributes).filter(([, value]) => value !== null && value !== "").slice(0, 5).map(([key, value]) => <div key={key}><dt>{titleCase(key)}</dt><dd>{String(value)}</dd></div>)}</dl>
      <section className="evidence-section"><h4>Evidence References <span>{asset.evidence.length}</span></h4>{asset.evidence.length ? asset.evidence.map((evidence, index) => <article key={`${evidence.source_id}-${index}`}><strong>{evidence.source_name}</strong><small>{[evidence.page ? `Page ${evidence.page}` : null, evidence.section, evidence.table ? `Table ${evidence.table}` : null, evidence.column ? `Column ${evidence.column}` : null].filter(Boolean).join(" • ") || "Source reference"}</small>{evidence.excerpt ? <blockquote>{evidence.excerpt}</blockquote> : null}</article>) : <p>No evidence attached.</p>}</section>
      <div className="review-actions"><button className="approve-button" disabled={isPending} onClick={() => onDecision("approve")} type="button"><BadgeCheck size={15} />Approve</button><button disabled={isPending} onClick={() => onDecision("review")} type="button"><CircleAlert size={15} />Send to Review</button><button className="reject-button" disabled={isPending} onClick={() => onDecision("reject")} type="button"><ThumbsDown size={15} />Reject</button></div>
    </div>
  );
}
