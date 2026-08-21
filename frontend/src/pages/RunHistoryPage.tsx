import { useQuery } from '@tanstack/react-query'
import { BarChart3, ChevronLeft, ChevronRight, MoreVertical, RefreshCw, Search, AlertCircle } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import { BrandMark } from '../components/common/BrandMark'
import { ErrorState, LoadingState } from '../components/common/States'
import { StatusPill } from '../components/common/StatusPill'
import { SummaryCard } from '../components/common/SummaryCard'
import type { ProcessingRun, RunStatus } from '../types'
import { formatDate } from '../utils/format'

type Filter = 'all' | 'completed' | 'needs_review' | 'processing' | 'failed'
const active: RunStatus[] = ['queued', 'profiling', 'planning', 'extracting', 'interpreting', 'validating', 'packaging']

export function RunHistoryPage() {
  const navigate = useNavigate(); const [params] = useSearchParams(); const workbookId = params.get('workbook') || ''
  const query = useQuery({ queryKey: ['runs', workbookId], queryFn: () => workbookId ? api.listWorkbookRuns(workbookId) : api.listRuns() })
  const [search, setSearch] = useState(''); const [filter, setFilter] = useState<Filter>('all'); const [selectedId, setSelectedId] = useState<string | null>(null)
  const runs = useMemo(() => query.data || [], [query.data]); const filtered = useMemo(() => runs.filter((run) => (`${run.id} ${run.workbook_name}`).toLowerCase().includes(search.toLowerCase()) && (filter === 'all' || filter === 'processing' ? filter === 'all' || active.includes(run.status) : run.status === filter)), [runs, search, filter]); const selected = runs.find((run) => run.id === selectedId) || filtered[0]
  return <section className="card history-shell"><div className="section-heading"><h1>Run History</h1><p>Track processing runs, review outcomes and restart workbook analysis when needed.</p></div>
    <div className="history-filters"><label className="search-box"><Search /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search runs or workbooks" /></label><div className="filter-pills">{(['all', 'completed', 'needs_review', 'processing', 'failed'] as Filter[]).map((value) => <button key={value} className={filter === value ? 'active' : ''} onClick={() => setFilter(value)}>{value.replace('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())}</button>)}</div><select aria-label="Sort runs"><option>Newest first</option><option>Oldest first</option></select></div>
    <div className="history-layout"><div className="history-main"><div className="summary-grid"><SummaryCard icon={BarChart3} label="Total Runs" value={runs.length} /><SummaryCard icon={RefreshCw} label="Active" value={runs.filter((run) => active.includes(run.status)).length} /><SummaryCard icon={AlertCircle} label="Needs Review" value={runs.filter((run) => run.status === 'needs_review').length} tone="amber" /></div><section className="inner-card"><h2>Recent Runs</h2>{query.isLoading ? <LoadingState /> : query.error ? <ErrorState error={query.error} /> : <RunTable runs={filtered} selected={selected?.id} onSelect={setSelectedId} onOpen={(id) => navigate(`/runs/${id}`)} />}<div className="pagination"><span>Showing 1 to {Math.min(filtered.length, 6)} of {filtered.length} runs</span><div><button disabled><ChevronLeft /></button><button className="current">1</button><button disabled={filtered.length < 7}><ChevronRight /></button></div></div></section></div>{selected && <SelectedRun run={selected} onOpen={() => navigate(`/runs/${selected.id}`)} />}</div>
  </section>
}

function RunTable({ runs, selected, onSelect, onOpen }: { runs: ProcessingRun[]; selected?: string; onSelect: (id: string) => void; onOpen: (id: string) => void }) { return <div className="table-wrap"><table className="data-table run-table"><thead><tr><th>Run ID</th><th>Workbook</th><th>Started</th><th>Duration</th><th>Status</th><th>Output</th><th>Actions</th></tr></thead><tbody>{runs.slice(0, 8).map((run) => <tr key={run.id} className={run.id === selected ? 'selected-row' : ''} onClick={() => onSelect(run.id)}><td>{`Run ${String(run.run_number).padStart(3, '0')}`}</td><td><span className="file-cell"><BrandMark small /><b>{run.workbook_name}</b></span></td><td>{formatDate(run.started_at)}</td><td>{formatDuration(run)}</td><td><StatusPill status={run.status} /></td><td>{run.output_unit_count == null ? '--' : `${run.output_unit_count.toLocaleString()} units`}</td><td><button className="icon-button" onClick={(event) => { event.stopPropagation(); onOpen(run.id) }}><MoreVertical /></button></td></tr>)}</tbody></table></div> }

function SelectedRun({ run, onOpen }: { run: ProcessingRun; onOpen: () => void }) { return <aside className="selected-run"><h2>Selected Run</h2><span className="run-badge">Run {String(run.run_number).padStart(3, '0')}</span><RunField label="Workbook"><span className="file-cell"><BrandMark small />{run.workbook_name}</span></RunField><RunField label="Purpose">{run.purpose}</RunField><RunField label="Status"><StatusPill status={run.status} /></RunField><RunField label="Confidence">{run.overall_confidence == null ? '--' : `${Math.round(run.overall_confidence * 100)}%`}</RunField><RunField label="Output">{run.output_unit_count?.toLocaleString() || '--'} units</RunField><div className="selected-actions"><button className="primary-button" onClick={onOpen}>View Output</button><button className="secondary-button" onClick={onOpen}><RefreshCw />Re-run</button></div></aside> }
function RunField({ label, children }: { label: string; children: React.ReactNode }) { return <div className="run-field"><span>{label}</span><div>{children}</div></div> }
function formatDuration(run: ProcessingRun) { if (active.includes(run.status)) return 'In progress'; if (!run.duration_seconds) return '--'; const minutes = Math.floor(run.duration_seconds / 60); return `${minutes}m ${Math.round(run.duration_seconds % 60)}s` }
