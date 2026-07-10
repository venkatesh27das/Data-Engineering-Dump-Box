"""Azure Data Factory action boundary with allowlisting and dry-run support."""

from uuid import uuid4


class AzureDataFactoryClient:
    def __init__(self, approved_pipelines: set[str], enabled: bool = False) -> None:
        self.approved_pipelines = approved_pipelines
        self.enabled = enabled
        self._runs: dict[str, str] = {}

    async def validate_pipeline_exists(self, pipeline_name: str) -> bool:
        return pipeline_name in self.approved_pipelines and self.enabled

    async def validate_linked_service_reference(self, _reference: str) -> bool:
        return self.enabled

    async def trigger_pipeline_run(
        self, pipeline_name: str, parameters: dict[str, object], idempotency_key: str, dry_run: bool
    ) -> str:
        if pipeline_name not in self.approved_pipelines:
            raise PermissionError("ADF pipeline is not approved")
        if idempotency_key in self._runs:
            return self._runs[idempotency_key]
        if not dry_run and not self.enabled:
            raise RuntimeError("ADF integration is disabled")
        run_id = f"ADF-{'DRY-' if dry_run else ''}{uuid4().hex[:10]}"
        self._runs[idempotency_key] = run_id
        return run_id

    async def get_pipeline_run_status(self, run_id: str) -> str:
        return "SUCCEEDED" if run_id.startswith("ADF-DRY-") else "RUNNING"

    async def cancel_pipeline_run(self, run_id: str) -> None:
        if not run_id:
            raise ValueError("run_id is required")

    async def wait_for_completion(self, run_id: str, timeout_seconds: int = 300) -> str:
        return await self.get_pipeline_run_status(run_id)
