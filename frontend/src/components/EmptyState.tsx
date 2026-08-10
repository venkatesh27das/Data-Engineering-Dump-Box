import type { LucideIcon } from "lucide-react";

interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  description: string;
  compact?: boolean;
}
export function EmptyState({ icon: Icon, title, description, compact = false }: EmptyStateProps) {
  return (
    <div className={`empty-state ${compact ? "empty-state-compact" : ""}`}>
      <div className="empty-state-icon">
        <Icon aria-hidden="true" size={compact ? 18 : 22} strokeWidth={1.8} />
      </div>
      <h3>{title}</h3>
      <p>{description}</p>
    </div>
  );
}
