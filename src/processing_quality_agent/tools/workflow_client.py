from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class WorkflowRun:
    run_id: str
    status: str
    idempotency_key: str


class DatabricksWorkflowClient(Protocol):
    async def trigger_parser_run(
        self,
        *,
        document_id: str,
        source_file_uri: str,
        parser_id: str,
        parser_config: dict[str, Any],
        source_run_id: str,
        recovery_id: str,
        idempotency_key: str,
        dry_run: bool,
    ) -> WorkflowRun: ...
    async def get_run_status(self, run_id: str) -> WorkflowRun: ...
    async def cancel_run(self, run_id: str) -> WorkflowRun: ...
    async def wait_for_completion(self, run_id: str, timeout_seconds: int = 600) -> WorkflowRun: ...


class MockWorkflowClient:
    def __init__(self) -> None:
        self.runs: dict[str, WorkflowRun] = {}
        self.idempotency: dict[str, str] = {}

    async def trigger_parser_run(
        self, *, idempotency_key: str, dry_run: bool, **kwargs: Any
    ) -> WorkflowRun:
        if idempotency_key in self.idempotency:
            return self.runs[self.idempotency[idempotency_key]]
        run_id = f"dry-run-{len(self.runs) + 1}" if dry_run else f"mock-run-{len(self.runs) + 1}"
        run = WorkflowRun(run_id, "DRY_RUN" if dry_run else "RUNNING", idempotency_key)
        self.runs[run_id] = run
        self.idempotency[idempotency_key] = run_id
        return run

    async def get_run_status(self, run_id: str) -> WorkflowRun:
        run = self.runs[run_id]
        if run.status == "RUNNING":
            run = WorkflowRun(run.run_id, "SUCCEEDED", run.idempotency_key)
            self.runs[run_id] = run
        return run

    async def cancel_run(self, run_id: str) -> WorkflowRun:
        run = self.runs[run_id]
        cancelled = WorkflowRun(run.run_id, "CANCELLED", run.idempotency_key)
        self.runs[run_id] = cancelled
        return cancelled

    async def wait_for_completion(self, run_id: str, timeout_seconds: int = 600) -> WorkflowRun:
        elapsed, delay = 0.0, 0.01
        while elapsed < timeout_seconds:
            run = await self.get_run_status(run_id)
            if run.status in {"SUCCEEDED", "FAILED", "CANCELLED", "DRY_RUN"}:
                return run
            await asyncio.sleep(delay)
            elapsed += delay
            delay = min(delay * 2, 10)
        raise TimeoutError(f"workflow run {run_id} exceeded timeout")


class SDKWorkflowClient:
    """Databricks SDK adapter; workspace credentials are resolved by the SDK runtime."""

    def __init__(self, job_ids: dict[str, int]) -> None:
        from databricks.sdk import WorkspaceClient

        self.client = WorkspaceClient()
        self.job_ids = job_ids
        self._idempotency: dict[str, str] = {}

    async def trigger_parser_run(
        self,
        *,
        document_id: str,
        source_file_uri: str,
        parser_id: str,
        parser_config: dict[str, Any],
        source_run_id: str,
        recovery_id: str,
        idempotency_key: str,
        dry_run: bool,
    ) -> WorkflowRun:
        if dry_run:
            return WorkflowRun(f"dry-run-{idempotency_key[:12]}", "DRY_RUN", idempotency_key)
        if idempotency_key in self._idempotency:
            return await self.get_run_status(self._idempotency[idempotency_key])
        if parser_id not in self.job_ids:
            raise ValueError(f"no workflow job configured for parser {parser_id}")
        params = {
            "document_id": document_id,
            "source_file_uri": source_file_uri,
            "parser_id": parser_id,
            "parser_config": __import__("json").dumps(parser_config),
            "source_run_id": source_run_id,
            "recovery_id": recovery_id,
            "idempotency_key": idempotency_key,
        }
        response = await asyncio.to_thread(
            self.client.jobs.run_now, job_id=self.job_ids[parser_id], job_parameters=params
        )
        run_id = str(response.response.run_id if response.response else response.run_id)
        self._idempotency[idempotency_key] = run_id
        return WorkflowRun(run_id, "RUNNING", idempotency_key)

    async def get_run_status(self, run_id: str) -> WorkflowRun:
        run = await asyncio.to_thread(self.client.jobs.get_run, int(run_id))
        lifecycle = str(
            run.state.life_cycle_state.value
            if run.state and run.state.life_cycle_state
            else "UNKNOWN"
        )
        result = str(
            run.state.result_state.value if run.state and run.state.result_state else lifecycle
        )
        return WorkflowRun(
            run_id,
            result,
            next((k for k, v in self._idempotency.items() if v == run_id), "unknown"),
        )

    async def cancel_run(self, run_id: str) -> WorkflowRun:
        await asyncio.to_thread(self.client.jobs.cancel_run, int(run_id))
        return WorkflowRun(run_id, "CANCELLED", "unknown")

    async def wait_for_completion(self, run_id: str, timeout_seconds: int = 600) -> WorkflowRun:
        delay = 2
        for _ in range(max(1, timeout_seconds // delay)):
            state = await self.get_run_status(run_id)
            if state.status in {"SUCCESS", "SUCCEEDED", "FAILED", "CANCELED", "CANCELLED"}:
                return state
            await asyncio.sleep(delay)
            delay = min(delay * 2, 30)
        raise TimeoutError(f"workflow run {run_id} exceeded timeout")
