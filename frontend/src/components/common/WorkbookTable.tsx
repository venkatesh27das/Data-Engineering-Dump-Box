import { MoreVertical } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import type { Workbook } from '../../types'
import { formatDate } from '../../utils/format'
import { BrandMark } from './BrandMark'
import { EmptyState } from './States'
import { StatusPill } from './StatusPill'

export function WorkbookTable({ workbooks, compact = false, onArchive }: { workbooks: Workbook[]; compact?: boolean; onArchive?: (id: string) => void }) {
  const navigate = useNavigate()
  const [menu, setMenu] = useState<string | null>(null)
  if (!workbooks.length) return <EmptyState title="No workbooks found" message="Upload a workbook or change the current filters." />
  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead><tr><th>Workbook</th><th>Purpose</th><th>Last Run</th><th>Status</th><th>Confidence</th>{!compact && <th>Actions</th>}</tr></thead>
        <tbody>{workbooks.map((workbook) => (
          <tr key={workbook.id} onClick={() => navigate(`/workbooks/${workbook.id}`)}>
            <td><span className="file-cell"><BrandMark small /><b>{workbook.display_name}</b></span></td>
            <td>{workbook.purpose}</td><td>{formatDate(workbook.updated_at)}</td>
            <td><StatusPill status={workbook.latest_status} /></td>
            <td>{workbook.latest_confidence == null ? '--' : `${Math.round(workbook.latest_confidence * 100)}%`}</td>
            {!compact && <td className="action-cell"><button className="icon-button" aria-label={`Actions for ${workbook.display_name}`} onClick={(event) => { event.stopPropagation(); setMenu(menu === workbook.id ? null : workbook.id) }}><MoreVertical size={19} /></button>{menu === workbook.id && <div className="action-menu"><button onClick={() => navigate(`/workbooks/${workbook.id}`)}>Open</button><button onClick={() => navigate(`/runs?workbook=${workbook.id}`)}>View runs</button>{onArchive && <button onClick={(event) => { event.stopPropagation(); onArchive(workbook.id); setMenu(null) }}>Archive</button>}</div>}</td>}
          </tr>
        ))}</tbody>
      </table>
    </div>
  )
}
