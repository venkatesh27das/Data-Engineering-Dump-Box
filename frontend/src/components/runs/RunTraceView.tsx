import { useQuery } from '@tanstack/react-query'
import { Check, ChevronRight, Circle, Clock3, GitBranch, ListTree, Network, Workflow, XCircle } from 'lucide-react'
import { useState } from 'react'
import { api } from '../../api/client'
import { ErrorState, LoadingState } from '../common/States'
import type { LineageEdge, RunStatus, TraceStage } from '../../types'

const terminal: RunStatus[] = ['completed', 'needs_review', 'failed', 'cancelled']

export function RunTraceView({ runId, status }: { runId: string; status: RunStatus }) {
  const [lineageMode, setLineageMode] = useState<'technical' | 'business'>('technical')
  const trace = useQuery({
    queryKey: ['run-trace', runId],
    queryFn: () => api.getRunTrace(runId),
    refetchInterval: terminal.includes(status) ? false : 1500,
  })
  if (trace.isLoading) return <LoadingState label="Loading processing trace…" />
  if (trace.error) return <ErrorState error={trace.error} />
  if (!trace.data) return null

  const data = trace.data
  const edges = data.lineage[lineageMode]
  const agentStage = data.stages.find((stage) => stage.stage === 'interpreting')
  const agents = asRecord(agentStage?.details.agents)
  return <section className="run-subview">
    <div className="subview-heading">
      <div><h2>Processing Trace</h2><p>An audit trail of the stages, local agents, outputs, and dependencies created during this run.</p></div>
      <span className="count-badge">{data.events.length} events</span>
    </div>
    <div className="trace-summary-grid">
      <TraceSummary icon={Workflow} label="Processing path" value={humanize(data.processing_plan.workbook_archetype || 'Deterministic')} />
      <TraceSummary icon={ListTree} label="Completed stages" value={`${data.stages.filter((stage) => stage.stage !== 'failed' && stage.stage !== 'cancelled').length}`} />
      <TraceSummary icon={Network} label="Lineage edges" value={`${data.lineage.technical_count + data.lineage.business_count}`} />
      <TraceSummary icon={GitBranch} label="Indexed asset types" value={`${Object.keys(data.asset_counts).length}`} />
    </div>
    <div className="trace-layout">
      <section className="card trace-timeline-card">
        <div className="section-title-row"><div><h2>Stage timeline</h2><p>{data.processing_plan.reasoning_summary || 'The workbook followed the recorded local processing path.'}</p></div></div>
        <div className="trace-timeline">{data.stages.map((stage) => <TraceStageRow key={stage.stage} stage={stage} />)}</div>
      </section>
      <aside className="card agent-trace-card">
        <h2>Local agent activity</h2>
        {Object.keys(agents).length ? <div className="agent-activity-list">{Object.entries(agents).map(([name, result]) => <div key={name}><span className="agent-status-dot" /><div><strong>{humanize(name)}</strong><small>{displayDetail(result)}</small></div></div>)}</div> : <p>No specialist-agent detail was recorded for this run.</p>}
        <div className="trace-runtime"><span>Runtime</span><strong>{humanize(String(data.processing_plan.agent_runtime?.framework || agentStage?.details.framework || 'Local deterministic pipeline'))}</strong></div>
        {(data.processing_plan.excluded_steps || []).length > 0 && <div className="trace-safety"><strong>Safety exclusions</strong>{data.processing_plan.excluded_steps?.map((step) => <span key={step}>{humanize(step)}</span>)}</div>}
      </aside>
    </div>
    <section className="card lineage-card">
      <div className="section-title-row"><div><h2>Lineage explorer</h2><p>Trace how workbook structures and normalized assets relate to one another.</p></div><div className="lineage-toggle"><button className={lineageMode === 'technical' ? 'active' : ''} onClick={() => setLineageMode('technical')}>Technical <span>{data.lineage.technical_count}</span></button><button className={lineageMode === 'business' ? 'active' : ''} onClick={() => setLineageMode('business')}>Business <span>{data.lineage.business_count}</span></button></div></div>
      {edges.length ? <div className="lineage-list">{edges.slice(0, 100).map((edge, index) => <LineageRow key={edge.edge_id || index} edge={edge} />)}</div> : <div className="lineage-empty"><GitBranch /><strong>No {lineageMode} lineage was generated</strong><span>This run did not produce edges in this lineage layer.</span></div>}
    </section>
    <details className="card event-log"><summary><span><Clock3 size={17} />Technical event log</span><small>{data.events.length} recorded events</small></summary><div>{data.events.map((event) => <article key={event.event_id}><time>{new Date(event.timestamp).toLocaleTimeString()}</time><div><strong>{event.message}</strong><span>{humanize(event.stage)} · {event.progress_percent}%</span>{Object.keys(event.details).length > 0 && <pre>{JSON.stringify(event.details, null, 2)}</pre>}</div></article>)}</div></details>
  </section>
}

function TraceSummary({ icon: Icon, label, value }: { icon: typeof Workflow; label: string; value: string }) {
  return <div className="card trace-summary"><span><Icon size={18} /></span><div><small>{label}</small><strong>{value}</strong></div></div>
}

function TraceStageRow({ stage }: { stage: TraceStage }) {
  const failed = stage.stage === 'failed' || stage.status === 'failed'
  const pending = stage.status === 'queued'
  const Icon = failed ? XCircle : pending ? Circle : Check
  return <div className={`trace-stage ${failed ? 'failed' : ''}`}>
    <span className="trace-stage-icon"><Icon size={16} /></span>
    <div className="trace-stage-copy"><div><strong>{humanize(stage.stage)}</strong>{stage.duration_seconds !== null && <small>{formatDuration(stage.duration_seconds)}</small>}</div><p>{stage.message}</p>{Object.keys(stage.details).length > 0 && <div className="stage-detail-chips">{Object.entries(stage.details).filter(([, value]) => typeof value !== 'object').slice(0, 6).map(([key, value]) => <span key={key}>{humanize(key)}: <b>{String(value)}</b></span>)}</div>}</div>
  </div>
}

function LineageRow({ edge }: { edge: LineageEdge }) {
  const source = String(edge.source_name || edge.source_id || 'Source')
  const target = String(edge.target_name || edge.target_id || 'Target')
  return <article className="lineage-row">
    <div className="lineage-node"><small>Source</small><strong>{shortId(source)}</strong></div>
    <div className="lineage-relation"><span>{humanize(String(edge.relationship_type || 'related to'))}</span><ChevronRight size={17} /></div>
    <div className="lineage-node"><small>Target</small><strong>{shortId(target)}</strong></div>
    <div className="lineage-evidence"><span>{edge.confidence !== undefined ? `${Math.round(edge.confidence * 100)}% confidence` : 'Recorded edge'}</span>{edge.evidence?.length ? <small>{edge.evidence.map(humanize).join(', ')}</small> : null}</div>
  </article>
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}

function displayDetail(value: unknown) {
  if (typeof value === 'string') return humanize(value)
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  return 'Completed'
}

function humanize(value: string) {
  return value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function shortId(value: string) {
  const parts = value.split('.')
  return parts.length > 3 ? `…${parts.slice(-3).join('.')}` : value
}

function formatDuration(value: number) {
  value = Math.max(0, value)
  if (value < 1) return `${Math.round(value * 1000)} ms`
  if (value < 60) return `${value.toFixed(1)} sec`
  return `${Math.floor(value / 60)}m ${Math.round(value % 60)}s`
}
