"""In-memory operational repository for local mode and tests."""

from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from typing import Any

from source_readiness_agent.models.contracts import (
    ConfigurationProposal,
    OperationResult,
    ReadinessAssessment,
    SampleRun,
)


class InMemoryRepository:
    def __init__(self) -> None:
        self.assessments: dict[str, ReadinessAssessment] = {}
        self.proposals: dict[str, ConfigurationProposal] = {}
        self.sample_runs: dict[str, SampleRun] = {}
        self.operations: dict[str, OperationResult] = {}
        self.sources: dict[str, Any] = {}
        self.audit_events: list[dict[str, Any]] = []
        self._versions: defaultdict[tuple[str, str], int] = defaultdict(int)
        self._active: dict[tuple[str, str], str] = {}

    def save_assessment(self, assessment: ReadinessAssessment, source: Any) -> None:
        self.assessments[assessment.assessment_id] = deepcopy(assessment)
        self.sources[assessment.source_id] = deepcopy(source)

    def get_assessment(self, assessment_id: str) -> ReadinessAssessment:
        return deepcopy(self.assessments[assessment_id])

    def next_version(self, source_id: str, environment: str) -> int:
        key = (source_id, environment)
        self._versions[key] += 1
        return self._versions[key]

    def save_proposal(self, proposal: ConfigurationProposal) -> None:
        self.proposals[proposal.proposal_id] = deepcopy(proposal)

    def get_proposal(self, proposal_id: str) -> ConfigurationProposal:
        return deepcopy(self.proposals[proposal_id])

    def save_sample_run(self, run: SampleRun) -> None:
        self.sample_runs[run.sample_run_id] = deepcopy(run)

    def activate(self, proposal: ConfigurationProposal) -> ConfigurationProposal:
        key = (proposal.source_id, proposal.environment)
        old_id = self._active.get(key)
        if old_id:
            old = self.proposals[old_id]
            old.active = False
        proposal.active = True
        self.proposals[proposal.proposal_id] = deepcopy(proposal)
        self._active[key] = proposal.proposal_id
        return deepcopy(proposal)

    def record_operation(self, result: OperationResult) -> None:
        self.operations[result.correlation_id] = deepcopy(result)

    def audit(self, event: dict[str, Any]) -> None:
        self.audit_events.append(deepcopy(event))
