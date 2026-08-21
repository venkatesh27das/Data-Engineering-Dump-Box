import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ChartColumn, Check, Circle, ClipboardList, Download, FileJson, Image, Link2, Network, RefreshCw, Table2, X, XCircle } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../api/client'
import { ErrorState, LoadingState } from '../components/common/States'
import { StatusPill } from '../components/common/StatusPill'
import type { RunStatus } from '../types'

const terminal: RunStatus[] = ['completed', 'needs_review', 'failed', 'cancelled']
const stages = [
  ['profiling', 'Workbook inspected'], ['planning', 'Sheets and regions identified'], ['extracting', 'Analyzing formulas and relationships'],
  ['interpreting', 'Processing images, charts, and semantics'], ['validating', 'Validating normalized knowledge assets'], ['packaging', 'Creating downloadable package'],
]

export function RunDetailPage() {
  const { runId = '' } = useParams(); const navigate = useNavigate(); const queryClient = useQueryClient(); const [drawer, setDrawer] = useState(false)
  const run = useQuery({ queryKey: ['run', runId], queryFn: () => api.getRun(runId), refetchInterval: (query) => terminal.includes(query.state.data?.status as RunStatus) ? false : 1500 })
  const assets = useQuery({ queryKey: ['assets', runId], queryFn: () => api.listAssets(runId), enabled: terminal.includes(run.data?.status as RunStatus) })
  const reviews = useQuery({ queryKey: ['reviews', runId], queryFn: () => api.listReviewItems(runId), enabled: run.data?.status === 'needs_review' || run.data?.status === 'completed' })
  const runStatus = run.data?.status
  useEffect(() => { if (!runStatus || terminal.includes(runStatus)) return; const source = new EventSource(api.eventUrl(runId)); source.onmessage = () => queryClient.invalidateQueries({ queryKey: ['run', runId] }); source.onerror = () => source.close(); return () => source.close() }, [runStatus, runId, queryClient])
  if (run.isLoading) return <LoadingState label="Loading run…" />; if (run.error) return <ErrorState error={run.error} />; if (!run.data) return null
  const data = run.data; const currentIndex = Math.max(0, stages.findIndex(([id]) => id === data.current_stage)); const isRunning = !terminal.includes(data.status)
  return <div className="detail-page"><div className="page-heading"><div><button className="back-button" onClick={() => navigate('/runs')}>← Run History</button><h1>{data.workbook_name}</h1><p>Run {String(data.run_number).padStart(3, '0')} · {data.purpose}</p></div><div className="heading-actions"><StatusPill status={data.status} />{terminal.includes(data.status) && <><a className="primary-button" href={api.packageUrl(data.id)}><Download />Download Package</a><button className="secondary-button" onClick={() => setDrawer(true)}><RefreshCw />Reprocess</button></>}</div></div>
    {isRunning ? <section className="card processing-card"><div className="processing-head"><div><span>Workbook Intelligence Agent</span><h2>{data.current_stage.replace('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())}</h2><p>{activityText(data.current_stage)}</p></div><strong>{data.progress_percent}%</strong></div><div className="progress-track"><i style={{ width: `${data.progress_percent}%` }} /></div><div className="stage-list">{stages.map(([id, label], index) => <div key={id} className={index < currentIndex ? 'done' : index === currentIndex ? 'current' : ''}>{index < currentIndex ? <Check /> : index === currentIndex ? <span className="pulse-dot" /> : <Circle />}<span>{label}</span></div>)}</div><CancelButton runId={runId} /></section> : <CompletedOutput runId={runId} assets={assets.data || []} reviews={reviews.data || []} status={data.status} />}
    {drawer && <ReprocessDrawer runId={runId} onClose={() => setDrawer(false)} />}
  </div>
}

function CompletedOutput({ runId, assets, reviews, status }: { runId: string; assets: Awaited<ReturnType<typeof api.listAssets>>; reviews: Awaited<ReturnType<typeof api.listReviewItems>>; status: RunStatus }) {
  const queryClient = useQueryClient(); const resolve = useMutation({ mutationFn: ({ id, action }: { id: string; action: string }) => api.resolveReview(id, action), onSuccess: () => queryClient.invalidateQueries({ queryKey: ['reviews', runId] }) })
  const groups = [
    { types: ['table'], label: 'Normalized datasets', icon: Table2 },
    { types: ['semantic_unit'], label: 'Semantic & embedding units', icon: FileJson },
    { types: ['relationship', 'entity'], label: 'Entities & relationships', icon: Network },
    { types: ['image'], label: 'Images and OCR', icon: Image },
    { types: ['chart', 'pivot'], label: 'Charts and pivots', icon: ChartColumn },
    { types: ['form', 'conditional_format', 'data_validation'], label: 'Forms and rules', icon: ClipboardList },
    { types: ['connection', 'query', 'external_link'], label: 'Connections and queries', icon: Link2 },
  ]
  return <><section className={`completion-banner completion-banner--${status === 'failed' ? 'failed' : 'success'}`}>{status === 'failed' ? <XCircle /> : <Check />}<div><h2>{status === 'needs_review' ? 'Analysis completed with review items' : status === 'failed' ? 'Analysis could not be completed' : 'Workbook knowledge package is ready'}</h2><p>{assets.length} indexed assets · {reviews.filter((item) => item.status === 'open').length} open review items</p></div></section><div className="output-grid"><section className="card"><h2>Output Assets</h2><div className="asset-groups">{groups.map(({ types, label, icon: Icon }) => { const count = assets.filter((asset) => types.some((type) => asset.asset_type.includes(type))).length; return <div key={label}><Icon /><div><strong>{label}</strong><span>{count} assets</span></div></div> })}</div></section><section className="card"><h2>Review Queue</h2>{reviews.filter((item) => item.status === 'open').length ? <div className="review-list">{reviews.filter((item) => item.status === 'open').slice(0, 3).map((item) => <article key={item.id}><span className={`severity severity--${item.severity}`}>{item.severity}</span><h3>{item.title}</h3><p>{item.description}</p><small>{item.evidence}</small><div><button onClick={() => resolve.mutate({ id: item.id, action: 'confirm' })}>Confirm</button><button onClick={() => resolve.mutate({ id: item.id, action: 'ignore' })}>Ignore</button></div></article>)}</div> : <div className="empty-state"><Check /><strong>Nothing needs your attention</strong></div>}</section></div></>
}

function CancelButton({ runId }: { runId: string }) { const queryClient = useQueryClient(); const cancel = useMutation({ mutationFn: () => api.cancelRun(runId), onSuccess: () => queryClient.invalidateQueries({ queryKey: ['run', runId] }) }); return <button className="danger-text-button" onClick={() => cancel.mutate()}><X />Cancel processing</button> }
function ReprocessDrawer({ runId, onClose }: { runId: string; onClose: () => void }) { const navigate = useNavigate(); const [text, setText] = useState(''); const mutation = useMutation({ mutationFn: () => api.reprocess(runId, text), onSuccess: (run) => navigate(`/runs/${run.id}`) }); return <div className="drawer-backdrop" onMouseDown={onClose}><aside className="drawer" onMouseDown={(event) => event.stopPropagation()}><button className="drawer-close" onClick={onClose}><X /></button><h2>Reprocess workbook</h2><p>Tell the agent what should change. Approved assets are preserved by default.</p><label>Feedback<textarea value={text} onChange={(event) => setText(event.target.value)} placeholder="For example: Treat row 3 on Forecast as the header and ignore rows 1–2." /></label><label>Apply feedback to<select><option>Impacted assets</option><option>Entire workbook</option><option>Selected sheets</option></select></label><label className="check-label"><input type="checkbox" defaultChecked />Preserve confirmed mappings</label><label className="check-label"><input type="checkbox" defaultChecked />Preserve approved structures</label><label className="check-label"><input type="checkbox" defaultChecked />Reprocess only impacted assets</label>{mutation.error && <div className="inline-error">{mutation.error.message}</div>}<button className="primary-button drawer-submit" disabled={!text.trim() || mutation.isPending} onClick={() => mutation.mutate()}>{mutation.isPending ? 'Starting…' : 'Start Reprocessing'}</button></aside></div> }
function activityText(stage: string) { const text: Record<string, string> = { queued: 'Waiting for the local processing worker', profiling: 'Inspecting workbook structure and safety metadata', planning: 'Selecting the deterministic processing path', extracting: 'Reading sheets, tables, formulas, charts, and images', interpreting: 'Creating contextual semantic units and relationships', validating: 'Checking provenance, consistency, and confidence', packaging: 'Writing the canonical knowledge package' }; return text[stage] || 'Working on your workbook' }
