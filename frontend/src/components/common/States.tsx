import { LoaderCircle } from 'lucide-react'

export function LoadingState({ label = 'Loading…' }: { label?: string }) {
  return <div className="state-message"><LoaderCircle className="spin" size={20} />{label}</div>
}

export function EmptyState({ title, message }: { title: string; message: string }) {
  return <div className="empty-state"><strong>{title}</strong><span>{message}</span></div>
}

export function ErrorState({ error }: { error: Error }) {
  return <div className="error-state" role="alert">{error.message}</div>
}

