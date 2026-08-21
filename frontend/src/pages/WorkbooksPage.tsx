import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, FileSpreadsheet, Search, Upload, FileWarning } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { ErrorState, LoadingState } from '../components/common/States'
import { SummaryCard } from '../components/common/SummaryCard'
import { WorkbookTable } from '../components/common/WorkbookTable'
import type { RunStatus } from '../types'

type Filter = 'all' | 'completed' | 'needs_review' | 'processing' | 'failed'
const processing: RunStatus[] = ['queued', 'profiling', 'planning', 'extracting', 'interpreting', 'validating', 'packaging']

export function WorkbooksPage() {
  const navigate = useNavigate(); const queryClient = useQueryClient()
  const [search, setSearch] = useState(''); const [filter, setFilter] = useState<Filter>('all')
  const query = useQuery({ queryKey: ['workbooks'], queryFn: () => api.listWorkbooks() })
  const archive = useMutation({ mutationFn: api.archiveWorkbook, onSuccess: () => queryClient.invalidateQueries({ queryKey: ['workbooks'] }) })
  const data = useMemo(() => query.data || [], [query.data])
  const filtered = useMemo(() => data.filter((item) => item.display_name.toLowerCase().includes(search.toLowerCase()) && (filter === 'all' || filter === 'processing' ? filter === 'all' || processing.includes(item.latest_status) : item.latest_status === filter)), [data, search, filter])
  const count = (status: RunStatus) => data.filter((item) => item.latest_status === status).length
  return <div>
    <div className="page-heading"><div><h1>My Workbooks</h1><p>Manage uploaded Excel workbooks and continue from previous runs.</p></div><button className="primary-button" onClick={() => navigate('/')}><Upload size={19} />Upload Workbook</button></div>
    <section className="card filter-card"><label className="search-box"><Search /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search workbooks" aria-label="Search workbooks" /></label><div className="filter-pills">{(['all', 'completed', 'needs_review', 'processing', 'failed'] as Filter[]).map((value) => <button key={value} className={filter === value ? 'active' : ''} onClick={() => setFilter(value)}>{value.replace('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())}</button>)}</div></section>
    <div className="summary-grid"><SummaryCard icon={FileSpreadsheet} label="Total Workbooks" value={data.length} /><SummaryCard icon={FileWarning} label="Needs Review" value={count('needs_review')} tone="amber" /><SummaryCard icon={CheckCircle2} label="Completed" value={count('completed')} /></div>
    <section className="card library-card"><h2>Workbook Library</h2>{query.isLoading ? <LoadingState /> : query.error ? <ErrorState error={query.error} /> : <WorkbookTable workbooks={filtered} onArchive={(id) => archive.mutate(id)} />}</section>
  </div>
}
