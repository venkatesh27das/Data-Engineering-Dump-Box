export function formatDate(value: string | null) {
  if (!value) return '--'
  const date = new Date(value)
  const today = new Date()
  const sameDay = date.toDateString() === today.toDateString()
  const yesterday = new Date(today)
  yesterday.setDate(today.getDate() - 1)
  const prefix = sameDay
    ? 'Today'
    : date.toDateString() === yesterday.toDateString()
      ? 'Yesterday'
      : date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
  return `${prefix}, ${date.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })}`
}

