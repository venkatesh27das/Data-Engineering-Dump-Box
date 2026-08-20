import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  BrainCircuit,
  CheckCircle2,
  Database,
  FileText,
  ListTodo,
  LoaderCircle,
  Rocket,
  RotateCcw,
  Save,
  SlidersHorizontal,
  Trash2,
} from "lucide-react";
import { ChangeEvent, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { Card } from "../../components/Card";
import { EmptyState } from "../../components/EmptyState";
import { PageIntro } from "../../components/PageIntro";
import { createProject, deleteSource, getProject, listSources, updateProject, uploadSource } from "../../services/projects";
import { listRuns, startRun } from "../../services/runs";
import type { GraphDepth, ProcessingMode, Project, ProjectDraft, SourceAsset } from "../../types/build";
import type { RunQueueItem } from "../../types/runs";

const DEFAULT_OBJECTIVE = "Understand suppliers, contracts, products and obligations";

const initialConfig = {
  processingMode: "auto" as ProcessingMode,
  graphDepth: "entity_relationships" as GraphDepth,
  reviewLowConfidence: true,
  maxTokens: 2048,
};

function projectName(objective: string): string {
  const trimmed = objective.trim();
  return trimmed.length > 120 ? `${trimmed.slice(0, 117)}...` : trimmed;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function words(value: string): string {
  return value.replaceAll("_", " ");
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

export function BuildPage() {
  const queryClient = useQueryClient();
  const structuredInput = useRef<HTMLInputElement>(null);
  const unstructuredInput = useRef<HTMLInputElement>(null);
  const [objective, setObjective] = useState(DEFAULT_OBJECTIVE);
  const [processingMode, setProcessingMode] = useState<ProcessingMode>(initialConfig.processingMode);
  const [graphDepth, setGraphDepth] = useState<GraphDepth>(initialConfig.graphDepth);
  const [reviewLowConfidence, setReviewLowConfidence] = useState(initialConfig.reviewLowConfidence);
  const [maxTokens, setMaxTokens] = useState(initialConfig.maxTokens);
  const [projectId, setProjectId] = useState<string | null>(() => localStorage.getItem("knowledge-graph-builder.project-id"));
  const [savedProject, setSavedProject] = useState<Project | null>(null);
  const [sources, setSources] = useState<SourceAsset[]>([]);
  const [busy, setBusy] = useState<"save" | "upload" | "run" | null>(null);
  const [notice, setNotice] = useState<{ tone: "success" | "error"; message: string } | null>(null);

  const latestRunsQuery = useQuery({
    queryKey: ["run-queue"],
    queryFn: ({ signal }) => listRuns(signal),
    refetchInterval: 10_000,
  });
  const latestRun = latestRunsQuery.data?.[0];

  useEffect(() => {
    const storedProjectId = localStorage.getItem("knowledge-graph-builder.project-id");
    if (!storedProjectId) return;
    let active = true;
    Promise.all([getProject(storedProjectId), listSources(storedProjectId)])
      .then(([project, storedSources]) => {
        if (!active) return;
        setProjectId(project.id);
        setSavedProject(project);
        setObjective(project.knowledge_objective);
        setProcessingMode(project.processing_mode);
        setGraphDepth(project.graph_depth);
        setReviewLowConfidence(project.review_low_confidence);
        setMaxTokens(project.max_tokens);
        setSources(storedSources);
      })
      .catch(() => {
        if (!active) return;
        localStorage.removeItem("knowledge-graph-builder.project-id");
        localStorage.removeItem("knowledge-graph-builder.run-id");
        setProjectId(null);
        setSavedProject(null);
        setSources([]);
      });
    return () => { active = false; };
  }, []);

  const draft = (): ProjectDraft => ({
    name: projectName(objective),
    knowledge_objective: objective.trim(),
    processing_mode: processingMode,
    graph_depth: graphDepth,
    review_low_confidence: reviewLowConfidence,
    max_tokens: maxTokens,
  });

  const ensureProject = async (): Promise<string> => {
    if (!objective.trim()) throw new Error("Enter a knowledge objective before saving or uploading sources.");
    if (projectId) {
      const project = await updateProject(projectId, draft());
      setSavedProject(project);
      return projectId;
    }
    const project = await createProject(draft());
    setProjectId(project.id);
    setSavedProject(project);
    localStorage.setItem("knowledge-graph-builder.project-id", project.id);
    return project.id;
  };

  const saveDraft = async () => {
    setBusy("save");
    setNotice(null);
    try {
      await ensureProject();
      setNotice({ tone: "success", message: "Draft configuration saved." });
    } catch (error) {
      setNotice({ tone: "error", message: error instanceof Error ? error.message : "The draft could not be saved." });
    } finally {
      setBusy(null);
    }
  };

  const handleFiles = async (event: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files ?? []);
    event.target.value = "";
    if (!files.length) return;
    setBusy("upload");
    setNotice(null);
    try {
      const id = await ensureProject();
      const uploaded: SourceAsset[] = [];
      for (const file of files) uploaded.push(await uploadSource(id, file));
      setSources((current) => [...uploaded, ...current]);
      setNotice({ tone: "success", message: `${uploaded.length} source${uploaded.length === 1 ? "" : "s"} uploaded and ready for analysis.` });
    } catch (error) {
      setNotice({ tone: "error", message: error instanceof Error ? error.message : "The source upload failed." });
    } finally {
      setBusy(null);
    }
  };

  const removeSource = async (sourceId: string) => {
    if (!projectId) return;
    setNotice(null);
    try {
      await deleteSource(projectId, sourceId);
      setSources((current) => current.filter((source) => source.id !== sourceId));
    } catch (error) {
      setNotice({ tone: "error", message: error instanceof Error ? error.message : "The source could not be removed." });
    }
  };

  const launchRun = async () => {
    if (!sources.length) {
      setNotice({ tone: "error", message: "Upload at least one source before starting a run." });
      return;
    }
    setBusy("run");
    setNotice(null);
    try {
      const id = await ensureProject();
      const run = await startRun(id);
      localStorage.setItem("knowledge-graph-builder.run-id", run.id);
      await queryClient.invalidateQueries({ queryKey: ["run-queue"] });
      setNotice({ tone: "success", message: "Your run is queued. Monitor its progress in Run Queue." });
      setBusy(null);
    } catch (error) {
      setNotice({ tone: "error", message: error instanceof Error ? error.message : "The run could not be started." });
      setBusy(null);
    }
  };

  const reset = () => {
    setObjective(savedProject?.knowledge_objective ?? DEFAULT_OBJECTIVE);
    setProcessingMode(savedProject?.processing_mode ?? initialConfig.processingMode);
    setGraphDepth(savedProject?.graph_depth ?? initialConfig.graphDepth);
    setReviewLowConfidence(savedProject?.review_low_confidence ?? initialConfig.reviewLowConfidence);
    setMaxTokens(savedProject?.max_tokens ?? initialConfig.maxTokens);
    setNotice(sources.length ? { tone: "success", message: "Unsaved changes were reset. Uploaded sources were preserved." } : null);
  };

  return (
    <div className="page build-page-redesign">
      <PageIntro
        description={<>Define your objective, upload sources, configure the run, and launch. Monitor progress in <Link to="/queue">Run Queue</Link>.</>}
        title="Build"
      />

      <div className="build-launch-grid">
        <div className="build-form-stack">
          <Card className="build-step-card">
            <StepHeading number="1" title="Define Knowledge Objective" />
            <div className="objective-field build-objective-field">
              <textarea
                aria-label="Knowledge objective"
                maxLength={2000}
                onChange={(event) => setObjective(event.target.value)}
                placeholder="What should the graph help you understand?"
                value={objective}
              />
              <div><span>This helps the agent determine what to extract and how to model your knowledge.</span><small>{objective.length} / 2000</small></div>
            </div>
          </Card>

          <Card className="build-step-card">
            <StepHeading number="2" title="Upload Sources" />
            <div className="upload-grid build-upload-grid">
              <button className="upload-card upload-structured build-upload-card" disabled={busy !== null} onClick={() => structuredInput.current?.click()} type="button">
                <Database aria-hidden="true" size={25} />
                <strong>Structured Data</strong><span>Upload schema / SQL / JSON / CSV</span><b>{busy === "upload" ? "Uploading..." : "Upload Files"}</b><small>.sql, .json, .csv</small>
              </button>
              <button className="upload-card upload-unstructured build-upload-card" disabled={busy !== null} onClick={() => unstructuredInput.current?.click()} type="button">
                <FileText aria-hidden="true" size={25} />
                <strong>Unstructured Data</strong><span>Upload documents / PDF / DOCX / images</span><b>{busy === "upload" ? "Uploading..." : "Upload Files"}</b><small>.pdf, .docx, .png, .jpg</small>
              </button>
              <input accept=".sql,.json,.csv" hidden multiple onChange={handleFiles} ref={structuredInput} type="file" />
              <input accept=".pdf,.docx,.png,.jpg,.jpeg" hidden multiple onChange={handleFiles} ref={unstructuredInput} type="file" />
            </div>
            <strong className="uploaded-files-heading">Uploaded files ({sources.length})</strong>
            {!sources.length ? <div className="source-empty">No sources uploaded yet.</div> : (
              <ul className="source-list">
                {sources.map((source) => (
                  <li className="source-row build-source-row" key={source.id}>
                    <span className={`source-file-icon source-${source.category}`}>{source.category === "structured" ? <Database size={15} /> : <FileText size={15} />}</span>
                    <span className="source-row-copy"><strong>{source.original_filename}</strong><small>{formatBytes(source.size_bytes)} · {source.summary}</small></span>
                    <span className={`source-category source-category-${source.category}`}>{source.category}</span>
                    <button aria-label={`Remove ${source.original_filename}`} className="icon-button" disabled={busy !== null} onClick={() => void removeSource(source.id)} type="button"><Trash2 size={14} /></button>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <Card className="build-step-card build-config-card">
            <StepHeading number="3" title="Configure Run" />
            <div className="config-grid build-config-grid">
              <label><span>Processing mode</span><select aria-label="Processing mode" onChange={(event) => setProcessingMode(event.target.value as ProcessingMode)} value={processingMode}><option value="auto">Auto detect</option><option value="structured">Structured</option><option value="unstructured">Unstructured</option><option value="hybrid">Hybrid</option></select></label>
              <label><span>Graph depth</span><select aria-label="Graph depth" onChange={(event) => setGraphDepth(event.target.value as GraphDepth)} value={graphDepth}><option value="metadata">Metadata</option><option value="entity_relationships">Entity relationships</option><option value="semantic">Semantic</option><option value="contextual">Contextual</option></select></label>
              <label><span>Review low confidence</span><button aria-pressed={reviewLowConfidence} className={`toggle ${reviewLowConfidence ? "toggle-on" : ""}`} onClick={() => setReviewLowConfidence((value) => !value)} type="button"><i /></button></label>
              <label><span>Max tokens</span><input aria-label="Maximum tokens" max={131072} min={512} onChange={(event) => setMaxTokens(Number(event.target.value))} step={512} type="number" value={maxTokens} /></label>
            </div>
            <details className="advanced-options"><summary>About these options</summary><p>Auto detects source modalities. Graph depth controls how much semantic and contextual structure the run attempts to extract.</p></details>
          </Card>
        </div>

        <div className="build-launch-stack">
          <Card className="ready-launch-card">
            <div className="ready-launch-heading"><Rocket aria-hidden="true" size={22} /><div><h2>Ready to launch</h2><p>Review the configuration before sending this work to the background queue.</p></div></div>
            <dl className="launch-review-list">
              <div><dt><BrainCircuit size={13} />Objective</dt><dd>{objective.trim() || "Not defined"}</dd></div>
              <div><dt><Database size={13} />Sources</dt><dd>{sources.length} uploaded</dd></div>
              <div><dt><SlidersHorizontal size={13} />Mode</dt><dd>{words(processingMode)}</dd></div>
              <div><dt><SlidersHorizontal size={13} />Graph depth</dt><dd>{words(graphDepth)}</dd></div>
            </dl>
            <div className="launch-actions">
              <button className="start-run-button" disabled={busy !== null || !objective.trim() || !sources.length} onClick={() => void launchRun()} type="button">{busy === "run" ? <LoaderCircle className="spin" size={15} /> : <Rocket size={15} />}Start Run</button>
              <button className="launch-secondary-button" disabled={busy !== null} onClick={() => void saveDraft()} type="button">{busy === "save" ? <LoaderCircle className="spin" size={14} /> : <Save size={14} />}Save Draft</button>
              <button className="launch-secondary-button" disabled={busy !== null} onClick={reset} type="button"><RotateCcw size={14} />Reset</button>
            </div>
            {notice ? <p className={`inline-notice notice-${notice.tone}`}>{notice.tone === "success" ? <CheckCircle2 size={13} /> : null}{notice.message}</p> : null}
          </Card>

          <LatestRunCard isLoading={latestRunsQuery.isLoading} run={latestRun} />
        </div>
      </div>
    </div>
  );
}

function StepHeading({ number, title }: { number: string; title: string }) {
  return <div className="build-step-heading"><span>{number}</span><h2>{title}</h2></div>;
}

function LatestRunCard({ run, isLoading }: { run?: RunQueueItem; isLoading: boolean }) {
  return (
    <Card className="latest-run-card" title="Latest process" trailing={<Link className="latest-runs-link" to="/queue">View all <ArrowRight size={12} /></Link>}>
      {isLoading ? <div className="source-loading"><LoaderCircle className="spin" size={15} />Loading latest process...</div> : null}
      {!isLoading && !run ? <EmptyState compact description="Your most recent background run will appear here." icon={ListTodo} title="No processes yet" /> : null}
      {run ? (
        <>
          <Link className="latest-run-row" to={`/queue/${run.run.id}`}>
            <span className={`latest-run-icon latest-run-${run.run.status}`}><ListTodo size={17} /><small>{run.run.status}</small></span>
            <span className="latest-run-copy"><strong>{run.project_name}</strong><small>{run.run.id.slice(0, 8)} · {formatDate(run.run.created_at)}</small></span>
            <span className="latest-run-meta"><small>Stage</small><strong>{words(run.run.current_stage)}</strong></span>
            <span className="latest-run-meta"><small>Sources</small><strong>{run.source_count}</strong></span>
            <span className="latest-run-meta"><small>Outputs</small><strong>{run.artifact_count}</strong></span>
            <ArrowRight size={14} />
          </Link>
          <p className={`latest-run-notice latest-run-notice-${run.run.status}`}>This process is {run.run.status}. Open Run Queue to inspect its progress, events, outputs, and lineage.</p>
          <Link className="open-queue-button" to={`/queue/${run.run.id}`}>Open process details <ArrowRight size={13} /></Link>
        </>
      ) : null}
    </Card>
  );
}
