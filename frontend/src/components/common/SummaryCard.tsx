import type { LucideIcon } from 'lucide-react'

export function SummaryCard({ icon: Icon, label, value, tone = 'green' }: { icon: LucideIcon; label: string; value: number | string; tone?: 'green' | 'amber' }) {
  return <div className="summary-card"><div className={`summary-icon summary-icon--${tone}`}><Icon /></div><div><span>{label}</span><strong>{value}</strong></div></div>
}

