# Runbook

For a quality-gate failure, investigate first and retain its correlation ID. Check evidence and parser history. If recovery is appropriate, obtain an external change/review reference and call recover with approver identity. Confirm the new Databricks run ID, compare before/after assessment, and escalate after retry exhaustion. Quarantine corrupt content; reject unsupported formats; never modify raw input.

If a dependency is unavailable, do not retry indefinitely. Preserve the operation as failed/escalated with the last safe state and correlation ID. Inspect structured application logs and the MLflow trace without copying source content into tickets.
