import type { RunStatus } from '../../types'

const labels: Record<RunStatus, string> = {
  queued: 'Queued', profiling: 'Processing', planning: 'Processing', extracting: 'Processing',
  interpreting: 'Processing', validating: 'Processing', packaging: 'Processing',
  needs_review: 'Needs Review', completed: 'Completed', failed: 'Failed', cancelled: 'Cancelled',
}

export function StatusPill({ status }: { status: RunStatus }) {
  const kind = status === 'completed' ? 'success' : status === 'needs_review' ? 'warning' : status === 'failed' || status === 'cancelled' ? 'danger' : status === 'queued' ? 'neutral' : 'active'
  return <span className={`status-pill status-pill--${kind}`}>{labels[status]}</span>
}

