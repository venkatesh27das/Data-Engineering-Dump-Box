"""Approved, idempotent controlled sample-run orchestration."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from uuid import uuid4

from source_readiness_agent.models.contracts import (
    AuditMetadata,
    RunStatus,
    SampleRun,
    SamplingStrategy,
    ValidationStatus,
)
from source_readiness_agent.models.requests import SampleRunRequest
from source_readiness_agent.tools.base import require_approval
from source_readiness_agent.tools.repository import InMemoryRepository
from source_readiness_agent.tools.workflow_client import DatabricksWorkflowClient


class SampleRunService:
    def __init__(self, repository: InMemoryRepository, workflow: DatabricksWorkflowClient) -> None:
        self.repository = repository
        self.workflow = workflow
        self._by_key: dict[str, str] = {}

    async def run(self, request: SampleRunRequest, correlation_id: str) -> SampleRun:
        audit = AuditMetadata(
            actor=request.actor,
            reason="controlled sample run",
            correlation_id=correlation_id,
            approval_reference=request.approval.approval_reference,
        )
        require_approval(request.approval, audit)
        proposal = self.repository.get_proposal(request.proposal_id)
        if proposal.validation_status not in {
            ValidationStatus.VALID,
            ValidationStatus.VALID_WITH_WARNINGS,
        }:
            raise ValueError("proposal must pass deterministic validation")
        key = hashlib.sha256(
            f"{proposal.proposal_id}:{proposal.version}:{request.sample_size}:{request.dry_run}".encode()
        ).hexdigest()
        if key in self._by_key:
            return self.repository.sample_runs[self._by_key[key]]
        assessment = self.repository.get_assessment(proposal.assessment_id)
        object_ids = [
            profile.object_id
            for profile in (
                assessment.source_profile.file_profiles if assessment.source_profile else []
            )
        ][: request.sample_size]
        run = SampleRun(
            sample_run_id=f"SAMPLE-{uuid4().hex[:12].upper()}",
            proposal_id=proposal.proposal_id,
            source_id=proposal.source_id,
            selected_objects=object_ids,
            selection_strategy=SamplingStrategy.HYBRID,
            workflow_type="DATABRICKS_WORKFLOW",
            idempotency_key=key,
            dry_run=request.dry_run,
            status=RunStatus.RUNNING,
        )
        run.external_run_id = await self.workflow.trigger_sample_run(
            proposal.workflow_parameters, key, request.dry_run
        )
        external_status = await self.workflow.wait_for_completion(run.external_run_id)
        selected = len(object_ids)
        run.status = RunStatus.SUCCEEDED if external_status == "SUCCEEDED" else RunStatus.FAILED
        run.bronze_registered_count = selected if run.status == RunStatus.SUCCEEDED else 0
        run.parsed_count = (
            sum(
                profile.supported
                for profile in (
                    assessment.source_profile.file_profiles if assessment.source_profile else []
                )[: request.sample_size]
            )
            if run.status == RunStatus.SUCCEEDED
            else 0
        )
        run.unsupported_count = selected - run.parsed_count
        run.failed_count = max(0, selected - run.bronze_registered_count)
        accounting = 100.0 if selected == run.bronze_registered_count + run.failed_count else 0.0
        registration = 100.0 * run.bronze_registered_count / max(selected, 1)
        parse = 100.0 * run.parsed_count / max(selected - run.unsupported_count, 1)
        run.quality_summary = {
            "accounting_percent": accounting,
            "registration_percent": registration,
            "supported_parse_percent": parse,
            "manifest_completeness_percent": 100.0 if run.status == RunStatus.SUCCEEDED else 0.0,
            "lineage_completeness_percent": 100.0 if run.status == RunStatus.SUCCEEDED else 0.0,
            "sample_run_score": round((accounting + registration + parse) / 3, 2),
        }
        if accounting < 100 or registration < 95 or parse < 90:
            run.status = RunStatus.FAILED
            run.issues.append("sample-run thresholds were not met")
        run.completion_time = datetime.now(UTC)
        self.repository.save_sample_run(run)
        self._by_key[key] = run.sample_run_id
        return run
