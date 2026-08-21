import { useQuery } from '@tanstack/react-query'
import { ChartColumn, ClipboardList, Download, FileSpreadsheet, GitBranch, Image, Link2, RefreshCw, Table2 } from 'lucide-react'
import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../api/client'
import { ErrorState, LoadingState } from '../components/common/States'
import { StatusPill } from '../components/common/StatusPill'
import { formatDate } from '../utils/format'

export function WorkbookDetailPage() {
  const { workbookId = '' } = useParams(); const navigate = useNavigate(); const [tab, setTab] = useState('Overview')
  const workbook = useQuery({ queryKey: ['workbook', workbookId], queryFn: () => api.getWorkbook(workbookId) })
  const runs = useQuery({ queryKey: ['runs', workbookId], queryFn: () => api.listWorkbookRuns(workbookId) })
  const latestRun = workbook.data?.latest_run_id || ''; const assets = useQuery({ queryKey: ['assets', latestRun], queryFn: () => api.listAssets(latestRun), enabled: !!latestRun }); const reviews = useQuery({ queryKey: ['reviews', latestRun], queryFn: () => api.listReviewItems(latestRun), enabled: !!latestRun })
  if (workbook.isLoading) return <LoadingState />; if (workbook.error) return <ErrorState error={workbook.error} />; if (!workbook.data) return null
  const data = workbook.data
  return <div className="detail-page"><div className="page-heading"><div><button className="back-button" onClick={() => navigate('/workbooks')}>← My Workbooks</button><h1>{data.display_name}</h1><p>Last processed {formatDate(data.updated_at)}</p></div><div className="heading-actions"><StatusPill status={data.latest_status} />{data.latest_run_id && <><a className="primary-button" href={api.packageUrl(data.latest_run_id)}><Download />Download Package</a><button className="secondary-button" onClick={() => navigate(`/runs/${data.latest_run_id}`)}><RefreshCw />Reprocess</button></>}</div></div>
    <nav className="detail-tabs">{['Overview', 'Output Assets', 'Review', 'Runs'].map((item) => <button key={item} className={tab === item ? 'active' : ''} onClick={() => setTab(item)}>{item}</button>)}</nav>
    {tab === 'Overview' && <div className="overview-grid"><section className="card overview-understanding"><span>Workbook understanding</span><h2>{data.description || `A ${data.purpose.toLowerCase()} workbook containing structured Excel knowledge.`}</h2><p>The latest run inspected the workbook deterministically and retained source locations for every generated asset. Formula values were not recalculated.</p><div className="flow"><span>Source Data</span>→<span>Structure</span>→<span>Knowledge Assets</span>→<span>Quality Review</span></div></section><section className="card facts-card"><h2>Key facts</h2><dl><dt>Purpose</dt><dd>{data.purpose}</dd><dt>File type</dt><dd>{data.file_type.toUpperCase()}</dd><dt>File size</dt><dd>{Math.ceil(data.file_size_bytes / 1024)} KB</dd><dt>Confidence</dt><dd>{data.latest_confidence == null ? '--' : `${Math.round(data.latest_confidence * 100)}%`}</dd></dl></section></div>}
    {tab === 'Output Assets' && <section className="card library-card"><h2>Output Assets</h2><div className="asset-groups">{[
      { types: ['table'], label: 'Normalized datasets', icon: Table2 },
      { types: ['semantic'], label: 'Semantic and embedding units', icon: FileSpreadsheet },
      { types: ['relationship', 'entity'], label: 'Entities and relationships', icon: GitBranch },
      { types: ['image'], label: 'Images and OCR', icon: Image },
      { types: ['chart', 'pivot'], label: 'Charts and pivots', icon: ChartColumn },
      { types: ['form', 'conditional_format', 'data_validation'], label: 'Forms and workbook rules', icon: ClipboardList },
      { types: ['connection', 'query', 'external_link'], label: 'Connections and queries', icon: Link2 },
    ].map(({ types, label, icon: Icon }) => <div key={label}><Icon /><div><strong>{label}</strong><span>{(assets.data || []).filter((asset) => types.some((type) => asset.asset_type.includes(type))).length} assets</span></div></div>)}</div></section>}
    {tab === 'Review' && <section className="card library-card"><h2>Review items</h2>{(reviews.data || []).map((item) => <article className="review-row" key={item.id}><div><strong>{item.title}</strong><p>{item.description}</p></div><span>{Math.round(item.confidence * 100)}% confidence</span></article>)}</section>}
    {tab === 'Runs' && <section className="card library-card"><h2>Workbook runs</h2>{(runs.data || []).map((run) => <button className="run-list-row" key={run.id} onClick={() => navigate(`/runs/${run.id}`)}><span>Run {String(run.run_number).padStart(3, '0')}</span><span>{run.trigger_type.replace('_', ' ')}</span><StatusPill status={run.status} /></button>)}</section>}
  </div>
}
