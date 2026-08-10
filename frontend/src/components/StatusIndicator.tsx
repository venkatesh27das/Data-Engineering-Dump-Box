import type { IntegrationStatus } from "../types/health";

interface StatusIndicatorProps {
  label: string;
  status?: IntegrationStatus;
  isLoading?: boolean;
  isError?: boolean;
}

const statusLabels: Record<IntegrationStatus, string> = {
  connected: "Connected",
  disconnected: "Disconnected",
  not_configured: "Not configured",
  configuration_pending: "Check pending",
};

export function StatusIndicator({
  label,
  status,
  isLoading = false,
  isError = false,
}: StatusIndicatorProps) {
  const state = isError ? "unavailable" : isLoading || !status ? "checking" : status;
  const text = isError
    ? "API unavailable"
    : isLoading || !status
      ? "Checking"
      : statusLabels[status];

  return (
    <div className="status-indicator" data-status={state}>
      <span aria-hidden="true" className="status-dot" />
      <span className="font-semibold text-ink">{label}</span>
      <span className="text-muted">{text}</span>
    </div>
  );
}
