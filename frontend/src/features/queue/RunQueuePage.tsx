import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  Ban,
  Boxes,
  CheckCircle2,
  ChevronRight,
  Clock3,
  GitBranch,
  ListTodo,
  LoaderCircle,
  RefreshCw,
  Trash2,
  XCircle,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { Card } from "../../components/Card";
import { EmptyState } from "../../components/EmptyState";
import { FailureState } from "../../components/FailureState";
import { PageIntro } from "../../components/PageIntro";
import { cancelRun, deleteRun, getRunDetail, listRuns } from "../../services/runs";
import type { AgentEvent, RunArtifact, RunQueueItem, RunStatus } from "../../types/runs";

type DetailTab = "progress" | "assets" | "lineage";

const terminalStatuses: RunStatus[] = ["completed", "failed", "canceled"];

function isActive(status: RunStatus): boolean {
  return status === "queued" || status === "running";
}

function words(value: string): string {
  return value.replaceAll("_", " ");
}

function formatDate(value: string | null): string {
  if (!value) return "—";
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

function formatDuration(start: string | null, end: string | null): string {
  if (!start) return "Not started";
  const milliseconds = Math.max(0, new Date(end ?? Date.now()).getTime() - new Date(start).getTime());
  const seconds = Math.floor(milliseconds / 1000);
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  return `${minutes}m ${seconds % 60}s`;
}

function StatusIcon({ status, size = 16 }: { status: RunStatus | AgentEvent["status"]; size?: number }) {
  if (status === "queued" || status === "running") return <LoaderCircle aria-hidden="true" className={status === "running" ? "spin" : ""} size={size} />;
  if (status === "completed") return <CheckCircle2 aria-hidden="true" size={size} />;
  if (status === "canceled") return <Ban aria-hidden="true" size={size} />;
  return <XCircle aria-hidden="true" size={size} />;
}

function Metric({ label, value, tone, icon: Icon }: { label: string; value: number; tone: string; icon: typeof Activity }) {
  return (
    <Card className="queue-metric">
      <span className={`metric-icon ${tone}`}><Icon aria-hidden="true" size={19} /></span>
      <div><strong>{value}</strong><small>{label}</small></div>
    </Card>
  );
}

export function RunQueuePage() {
  const { runId } = useParams<{ runId?: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<DetailTab>("progress");

  const queueQuery = useQuery({
    queryKey: ["run-queue"],
    queryFn: ({ signal }) => listRuns(signal),
    refetchInterval: (query) => query.state.data?.some((item) => isActive(item.run.status)) ? 1_000 : 10_000,
  });

  const selectedId = runId ?? queueQuery.data?.[0]?.run.id;
  const detailQuery = useQuery({
    queryKey: ["run-detail", selectedId],
    queryFn: ({ signal }) => getRunDetail(selectedId!, signal),
    enabled: Boolean(selectedId),
    refetchInterval: (query) => query.state.data && isActive(query.state.data.item.run.status) ? 1_000 : false,
  });

  useEffect(() => {
    if (!runId && selectedId) navigate(`/queue/${selectedId}`, { replace: true });
  }, [navigate, runId, selectedId]);

  const refresh = async () => {
    await Promise.all([queueQuery.refetch(), selectedId ? detailQuery.refetch() : Promise.resolve()]);
  };

  const cancelMutation = useMutation({
    mutationFn: cancelRun,
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["run-queue"] }),
        queryClient.invalidateQueries({ queryKey: ["run-detail", selectedId] }),
      ]);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteRun,
    onSuccess: async () => {
      const remaining = (queueQuery.data ?? []).filter((item) => item.run.id !== selectedId);
      await queryClient.invalidateQueries({ queryKey: ["run-queue"] });
      navigate(remaining[0] ? `/queue/${remaining[0].run.id}` : "/queue", { replace: true });
    },
  });

  const metrics = useMemo(() => {
    const items = queueQuery.data ?? [];
    return {
      queued: items.filter((item) => item.run.status === "queued").length,
      running: items.filter((item) => item.run.status === "running").length,
      completed: items.filter((item) => item.run.status === "completed").length,
      stopped: items.filter((item) => item.run.status === "failed" || item.run.status === "canceled").length,
    };
  }, [queueQuery.data]);

  const handleDelete = () => {
    if (!selectedId) return;
    const confirmed = window.confirm("Delete this process, its event history, intermediate records, and generated local package? This cannot be undone.");
    if (confirmed) deleteMutation.mutate(selectedId);
  };

  return (
    <div className="page">
      <PageIntro
        action={<button className="secondary-button" disabled={queueQuery.isFetching} onClick={() => void refresh()} type="button"><RefreshCw className={queueQuery.isFetching ? "spin" : ""} size={14} />Refresh</button>}
        description="Monitor background generation, inspect intermediate assets and trace data lineage."
        title="Run Queue"
      />

      <div className="queue-metrics">
        <Metric icon={Clock3} label="Queued" tone="metric-orange" value={metrics.queued} />
        <Metric icon={Activity} label="Running" tone="metric-blue" value={metrics.running} />
        <Metric icon={CheckCircle2} label="Completed" tone="metric-green" value={metrics.completed} />
        <Metric icon={XCircle} label="Failed / canceled" tone="metric-pink" value={metrics.stopped} />
      </div>

      {queueQuery.isError ? <Card><FailureState description="The run queue could not be loaded. Check the backend connection and retry." onRetry={() => void queueQuery.refetch()} title="Queue unavailable" /></Card> : null}

      {!queueQuery.isError ? (
        <div className="queue-shell-grid">
          <Card className="queue-process-card" title="Processes" trailing={<span className="asset-count">{queueQuery.data?.length ?? 0} total</span>}>
            {queueQuery.isLoading ? <div className="queue-loading"><LoaderCircle className="spin" size={18} />Loading processes…</div> : null}
            {!queueQuery.isLoading && queueQuery.data?.length === 0 ? <EmptyState compact description="Generate graph assets from Build to create the first background process." icon={ListTodo} title="Queue is empty" /> : null}
            <div className="queue-list">
              {queueQuery.data?.map((item) => <QueueRow active={item.run.id === selectedId} item={item} key={item.run.id} onSelect={() => navigate(`/queue/${item.run.id}`)} />)}
            </div>
          </Card>

          <Card className="queue-detail-card" title="Process details" trailing={detailQuery.data ? <StatusBadge status={detailQuery.data.item.run.status} /> : undefined}>
            {!selectedId ? <EmptyState compact description="Select a process to inspect its progress and outputs." icon={Activity} title="No process selected" /> : null}
            {selectedId && detailQuery.isLoading ? <div className="queue-loading"><LoaderCircle className="spin" size={18} />Loading process details…</div> : null}
            {selectedId && detailQuery.isError ? <FailureState compact description="This process may have been deleted or its details are temporarily unavailable." onRetry={() => void detailQuery.refetch()} title="Process unavailable" /> : null}
            {detailQuery.data ? (
              <ProcessDetail
                cancelError={cancelMutation.error instanceof Error ? cancelMutation.error.message : null}
                deleteError={deleteMutation.error instanceof Error ? deleteMutation.error.message : null}
                deleting={deleteMutation.isPending}
                onCancel={() => cancelMutation.mutate(detailQuery.data.item.run.id)}
                onDelete={handleDelete}
                canceling={cancelMutation.isPending}
                setTab={setTab}
                tab={tab}
                detail={detailQuery.data}
              />
            ) : null}
          </Card>
        </div>
      ) : null}
    </div>
  );
}

function StatusBadge({ status }: { status: RunStatus }) {
  return <span className={`queue-status queue-status-${status}`}><StatusIcon size={13} status={status} />{status}</span>;
}

function QueueRow({ item, active, onSelect }: { item: RunQueueItem; active: boolean; onSelect: () => void }) {
  return (
    <button aria-current={active ? "true" : undefined} className={`queue-row ${active ? "queue-row-active" : ""}`} onClick={onSelect} type="button">
      <span className={`queue-row-icon queue-status-${item.run.status}`}><StatusIcon status={item.run.status} /></span>
      <span className="queue-row-copy">
        <strong>{item.project_name}</strong>
        <small>{words(item.run.current_stage)} • {formatDate(item.run.created_at)}</small>
        <span>{item.source_count} sources · {item.artifact_count} outputs · {formatDuration(item.run.started_at, item.run.completed_at)}</span>
      </span>
      <span className="queue-row-end"><StatusBadge status={item.run.status} /><ChevronRight aria-hidden="true" size={14} /></span>
    </button>
  );
}

function ProcessDetail({ detail, tab, setTab, onCancel, onDelete, canceling, deleting, cancelError, deleteError }: {
  detail: Awaited<ReturnType<typeof getRunDetail>>;
  tab: DetailTab;
  setTab: (tab: DetailTab) => void;
  onCancel: () => void;
  onDelete: () => void;
  canceling: boolean;
  deleting: boolean;
  cancelError: string | null;
  deleteError: string | null;
}) {
  const { item } = detail;
  const labels = new Map<string, string>([
    ...detail.sources.map((source) => [source.id, source.filename] as const),
    ...detail.temporary_assets.map((asset) => [asset.id, asset.name] as const),
  ]);

  return (
    <div>
      <div className="queue-detail-summary">
        <div className="queue-detail-heading">
          <div><strong>{item.project_name}</strong><small>Process {item.run.id.slice(0, 8)}</small></div>
          <div className="queue-actions">
            {isActive(item.run.status) ? <button className="stop-button" disabled={canceling} onClick={onCancel} type="button">{canceling ? <LoaderCircle className="spin" size={14} /> : <Ban size={14} />}Stop process</button> : null}
            {terminalStatuses.includes(item.run.status) ? <button className="danger-button" disabled={deleting} onClick={onDelete} type="button">{deleting ? <LoaderCircle className="spin" size={14} /> : <Trash2 size={14} />}Delete</button> : null}
          </div>
        </div>
        <dl className="queue-facts">
          <div><dt>Current stage</dt><dd>{words(item.run.current_stage)}</dd></div>
          <div><dt>Started</dt><dd>{formatDate(item.run.started_at)}</dd></div>
          <div><dt>Duration</dt><dd>{formatDuration(item.run.started_at, item.run.completed_at)}</dd></div>
          <div><dt>Sources</dt><dd>{item.source_count}</dd></div>
          <div><dt>Intermediate outputs</dt><dd>{item.artifact_count}</dd></div>
          <div><dt>Agent events</dt><dd>{item.event_count}</dd></div>
        </dl>
        {item.run.error_message ? <p className="queue-process-error">{item.run.error_message}</p> : null}
        {cancelError || deleteError ? <p className="queue-process-error">{cancelError ?? deleteError}</p> : null}
      </div>

      <div className="queue-tabs" role="tablist">
        <button aria-selected={tab === "progress"} className={tab === "progress" ? "active" : ""} onClick={() => setTab("progress")} role="tab" type="button"><Activity size={14} />Progress <span>{detail.events.length}</span></button>
        <button aria-selected={tab === "assets"} className={tab === "assets" ? "active" : ""} onClick={() => setTab("assets")} role="tab" type="button"><Boxes size={14} />Temporary assets <span>{detail.temporary_assets.length}</span></button>
        <button aria-selected={tab === "lineage"} className={tab === "lineage" ? "active" : ""} onClick={() => setTab("lineage")} role="tab" type="button"><GitBranch size={14} />Lineage <span>{detail.lineage.length}</span></button>
      </div>

      <div className="queue-tab-content">
        {tab === "progress" ? <ProgressPanel events={detail.events} /> : null}
        {tab === "assets" ? <ArtifactsPanel artifacts={detail.temporary_assets} /> : null}
        {tab === "lineage" ? <LineagePanel detail={detail} labels={labels} /> : null}
      </div>

      <p className="queue-delete-note">Deleting removes this run's local package, temporary records, lineage and event history. Graph data already published to Neo4j is not removed.</p>
    </div>
  );
}

function ProgressPanel({ events }: { events: AgentEvent[] }) {
  if (events.length === 0) return <EmptyState compact description="Progress events will appear after the worker starts this process." icon={Clock3} title="Waiting for events" />;
  return (
    <ol className="queue-event-list">
      {[...events].reverse().map((event) => (
        <li className={`queue-event queue-event-${event.status}`} key={event.id}>
          <span><StatusIcon status={event.status} /></span>
          <div><strong>{event.title}</strong><small>{event.message}</small></div>
          <time>{formatDate(event.timestamp)}</time>
        </li>
      ))}
    </ol>
  );
}

function ArtifactsPanel({ artifacts }: { artifacts: RunArtifact[] }) {
  if (artifacts.length === 0) return <EmptyState compact description="Normalized inputs and generated intermediate outputs will appear as processing advances." icon={Boxes} title="No intermediate assets yet" />;
  return (
    <div className="queue-artifact-table-wrap">
      <table className="queue-artifact-table">
        <thead><tr><th>Output</th><th>Type</th><th>Stage</th><th>Records</th><th>Status</th></tr></thead>
        <tbody>{artifacts.map((artifact) => <tr key={artifact.id}><td><strong>{artifact.name}</strong><small>{artifact.id.slice(0, 8)}</small></td><td>{words(artifact.artifact_type)}</td><td>{words(artifact.stage)}</td><td>{artifact.record_count}</td><td><span className={`artifact-status artifact-status-${artifact.status}`}>{artifact.status}</span></td></tr>)}</tbody>
      </table>
    </div>
  );
}

function LineagePanel({ detail, labels }: { detail: Awaited<ReturnType<typeof getRunDetail>>; labels: Map<string, string> }) {
  if (detail.lineage.length === 0) return <EmptyState compact description="Dependencies between sources and generated outputs will appear as assets are created." icon={GitBranch} title="No lineage yet" />;
  return (
    <div className="queue-lineage-list">
      {detail.lineage.map((edge, index) => (
        <div key={`${edge.parent_id}-${edge.child_id}-${index}`}>
          <span><small>FROM</small><strong>{labels.get(edge.parent_id) ?? edge.parent_id.slice(0, 8)}</strong></span>
          <i><ChevronRight size={14} /><small>{words(edge.relationship)}</small></i>
          <span><small>TO</small><strong>{labels.get(edge.child_id) ?? edge.child_id.slice(0, 8)}</strong></span>
        </div>
      ))}
    </div>
  );
}
