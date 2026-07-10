"""Databricks Workflow client with dry-run and idempotency controls."""

from __future__ import annotations

from uuid import uuid4


class DatabricksWorkflowClient:
    def __init__(self, job_id: int | None = None, enabled: bool = False) -> None:
        self.job_id = job_id
        self.enabled = enabled
        self._runs: dict[str, str] = {}

    async def validate_job_exists(self) -> bool:
        return bool(self.job_id) if self.enabled else False

    async def trigger_sample_run(
        self, parameters: dict[str, object], idempotency_key: str, dry_run: bool
    ) -> str:
        if idempotency_key in self._runs:
            return self._runs[idempotency_key]
        if dry_run:
            run_id = f"DBX-DRY-{uuid4().hex[:10]}"
        elif not self.enabled or not self.job_id:
            raise RuntimeError("Databricks Workflow integration is disabled")
        else:  # pragma: no cover - workspace adapter integration point
            from databricks.sdk import WorkspaceClient

            response = WorkspaceClient().jobs.run_now(
                job_id=self.job_id, job_parameters={k: str(v) for k, v in parameters.items()}
            )
            run_id = str(response.run_id)
        self._runs[idempotency_key] = run_id
        return run_id

    async def get_run_status(self, run_id: str) -> str:
        return "SUCCEEDED" if run_id.startswith("DBX-DRY-") else "RUNNING"

    async def cancel_run(self, run_id: str) -> None:
        if not run_id:
            raise ValueError("run_id is required")

    async def wait_for_completion(self, run_id: str, timeout_seconds: int = 300) -> str:
        return await self.get_run_status(run_id)
