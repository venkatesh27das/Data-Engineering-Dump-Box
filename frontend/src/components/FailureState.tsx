import { CircleAlert, RotateCcw } from "lucide-react";

type FailureStateProps = {
  title: string;
  description: string;
  compact?: boolean;
  onRetry?: () => void;
};

export function FailureState({ title, description, compact = false, onRetry }: FailureStateProps) {
  return (
    <div className={`empty-state failure-state ${compact ? "empty-state-compact" : ""}`} role="alert">
      <div className="empty-state-icon"><CircleAlert aria-hidden="true" size={23} /></div>
      <h3>{title}</h3>
      <p>{description}</p>
      {onRetry ? <button className="failure-retry" onClick={onRetry} type="button"><RotateCcw aria-hidden="true" size={14} />Try again</button> : null}
    </div>
  );
}
