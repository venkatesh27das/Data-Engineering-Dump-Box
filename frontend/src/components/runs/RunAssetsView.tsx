import { useQuery } from '@tanstack/react-query'
import {
  ChartColumn,
  Database,
  Download,
  Eye,
  FileJson,
  FileText,
  Image,
  Link2,
  Network,
  Search,
  Table2,
} from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { api } from '../../api/client'
import { EmptyState, ErrorState, LoadingState } from '../common/States'
import type { Asset } from '../../types'

const assetIcons = {
  table: Table2,
  semantic_unit: FileText,
  semantic_summary: FileText,
  entity_candidate: Network,
  relationship: Network,
  relationship_candidate: Network,
  image: Image,
  chart: ChartColumn,
  connection: Database,
  query: Link2,
}

export function RunAssetsView({ assets, loading }: { assets: Asset[]; loading: boolean }) {
  const [search, setSearch] = useState('')
  const [assetType, setAssetType] = useState('all')
  const [sheet, setSheet] = useState('all')
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const types = useMemo(() => [...new Set(assets.map((asset) => asset.asset_type))].sort(), [assets])
  const sheets = useMemo(
    () => [...new Set(assets.map((asset) => asset.source_sheet).filter(Boolean) as string[])].sort(),
    [assets],
  )
  const filtered = useMemo(() => {
    const term = search.trim().toLocaleLowerCase()
    return assets.filter((asset) => {
      const matchesTerm = !term || `${asset.title} ${asset.summary} ${asset.asset_type}`.toLocaleLowerCase().includes(term)
      return matchesTerm && (assetType === 'all' || asset.asset_type === assetType) && (sheet === 'all' || asset.source_sheet === sheet)
    })
  }, [assets, assetType, search, sheet])

  useEffect(() => {
    if (!filtered.length) setSelectedId(null)
    else if (!selectedId || !filtered.some((asset) => asset.id === selectedId)) setSelectedId(filtered[0].id)
  }, [filtered, selectedId])

  const selected = filtered.find((asset) => asset.id === selectedId) || null
  const content = useQuery({
    queryKey: ['asset-content', selectedId],
    queryFn: () => api.getAssetContent(selectedId || ''),
    enabled: Boolean(selectedId),
  })

  if (loading) return <LoadingState label="Loading output assets…" />

  return <section className="run-subview">
    <div className="subview-heading">
      <div><h2>Output Assets</h2><p>Inspect the normalized content, source provenance, and asset-level lineage created by this run.</p></div>
      <span className="count-badge">{assets.length} assets</span>
    </div>
    <div className="asset-toolbar card">
      <label className="asset-search"><Search size={17} /><span className="sr-only">Search assets</span><input aria-label="Search assets" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search assets…" /></label>
      <label><span>Type</span><select value={assetType} onChange={(event) => setAssetType(event.target.value)}><option value="all">All types</option>{types.map((type) => <option key={type} value={type}>{humanize(type)}</option>)}</select></label>
      <label><span>Sheet</span><select value={sheet} onChange={(event) => setSheet(event.target.value)}><option value="all">All sheets</option>{sheets.map((name) => <option key={name} value={name}>{name}</option>)}</select></label>
    </div>
    {!filtered.length ? <div className="card"><EmptyState title="No matching assets" message="Adjust the search or filters to see other generated outputs." /></div> : <div className="asset-explorer">
      <div className="asset-list card" aria-label="Generated assets">
        <div className="asset-list-heading"><strong>{filtered.length} results</strong><span>Select an asset to inspect it</span></div>
        {filtered.map((asset) => <AssetListItem key={asset.id} asset={asset} active={asset.id === selectedId} onClick={() => setSelectedId(asset.id)} />)}
      </div>
      <div className="asset-detail card">
        {!selected ? <EmptyState title="Select an asset" message="Choose an output asset to view its content and provenance." /> : content.isLoading ? <LoadingState label="Opening asset…" /> : content.error ? <ErrorState error={content.error} /> : content.data ? <AssetDetail asset={selected} content={content.data} /> : null}
      </div>
    </div>}
  </section>
}

function AssetListItem({ asset, active, onClick }: { asset: Asset; active: boolean; onClick: () => void }) {
  const Icon = assetIcons[asset.asset_type as keyof typeof assetIcons] || FileJson
  return <button className={`asset-list-item ${active ? 'active' : ''}`} onClick={onClick}>
    <span className="asset-type-icon"><Icon size={17} /></span>
    <span className="asset-list-copy"><strong>{asset.title}</strong><small>{humanize(asset.asset_type)}{asset.source_sheet ? ` · ${asset.source_sheet}` : ''}</small></span>
    <span className="asset-confidence">{Math.round(asset.confidence * 100)}%</span>
  </button>
}

function AssetDetail({ asset, content }: { asset: Asset; content: Awaited<ReturnType<typeof api.getAssetContent>> }) {
  return <>
    <div className="asset-detail-head">
      <div><span className="asset-type-label">{humanize(asset.asset_type)}</span><h2>{asset.title}</h2></div>
      <div className="asset-actions">{content.preview_available && <a className="secondary-button" href={api.assetPreviewUrl(asset.id)} target="_blank" rel="noreferrer"><Eye size={16} />Open image</a>}<a className="secondary-button" href={api.assetDownloadUrl(asset.id)}><Download size={16} />Download</a></div>
    </div>
    <p className="asset-summary">{asset.summary}</p>
    <div className="asset-provenance">
      <div><span>Source sheet</span><strong>{asset.source_sheet || 'Workbook level'}</strong></div>
      <div><span>Source range</span><strong>{asset.source_range || 'Not applicable'}</strong></div>
      <div><span>Confidence</span><strong>{Math.round(asset.confidence * 100)}%</strong></div>
      <div><span>Review</span><strong>{humanize(asset.review_status)}</strong></div>
    </div>
    {content.content_kind === 'image' && <div className="visual-preview"><img src={api.assetPreviewUrl(asset.id)} alt={`Preview of ${asset.title}`} /></div>}
    {content.preview_rows.length > 0 && <AssetTable columns={content.preview_columns} rows={content.preview_rows} />}
    {content.record && <details className="asset-json" open={content.content_kind === 'json'}><summary>Structured metadata {content.record_source && <span>{content.record_source}</span>}</summary><pre>{JSON.stringify(content.record, null, 2)}</pre></details>}
    {content.lineage.length > 0 && <div className="asset-lineage"><h3>Related lineage</h3>{content.lineage.slice(0, 8).map((edge, index) => <div key={edge.edge_id || index}><strong>{shortId(String(edge.source_id || edge.source_name || 'Source'))}</strong><span>{humanize(String(edge.relationship_type || 'related to'))}</span><strong>{shortId(String(edge.target_id || edge.target_name || 'Target'))}</strong></div>)}</div>}
  </>
}

function AssetTable({ columns, rows }: { columns: string[]; rows: Record<string, unknown>[] }) {
  return <div className="asset-table-section"><h3>Normalized data preview</h3><div className="table-wrap"><table className="data-table asset-preview-table"><thead><tr>{columns.map((column) => <th key={column}>{humanize(column)}</th>)}</tr></thead><tbody>{rows.map((row, index) => <tr key={index}>{columns.map((column) => <td key={column}>{displayValue(row[column])}</td>)}</tr>)}</tbody></table></div><small>Showing the first {rows.length} normalized records.</small></div>
}

function displayValue(value: unknown) {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

function humanize(value: string) {
  return value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function shortId(value: string) {
  const parts = value.split('.')
  return parts.length > 2 ? parts.slice(-2).join('.') : value
}
