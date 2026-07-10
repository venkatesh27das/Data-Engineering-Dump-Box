from pathlib import Path

import pytest

from source_readiness_agent.app import build_runtime
from source_readiness_agent.config import Settings
from source_readiness_agent.connectors.mock import MockConnector
from source_readiness_agent.models.contracts import Approval
from source_readiness_agent.models.requests import (
    AssessSourceRequest,
    GenerateConfigurationRequest,
    SampleRunRequest,
    ValidateConfigurationRequest,
)
from source_readiness_agent.services.assessment_service import AssessmentService


@pytest.fixture
def runtime():
    settings = Settings(app_env="local", use_mock_tools=True, source_allowlist_json='["mock://"]')
    value = build_runtime(settings)
    connector = MockConnector(Path("tests/fixtures/mock_source").resolve(), ["mock://"])
    value.orchestrator.assessment_service = AssessmentService(
        value.repository, settings, {"MOCK": connector}, {"pdf", "txt", "json"}
    )
    return value


@pytest.mark.asyncio
async def test_complete_local_flow_and_idempotency(runtime):
    source = {
        "source_id": "SRC-POLICY-01",
        "source_name": "Policy Documents",
        "source_type": "MOCK",
        "source_system": "fixture",
        "connection_reference": "mock",
        "source_location": "mock://",
        "business_owner": "Policy Operations",
        "technical_owner": "Data Engineering",
    }
    assessed = await runtime.orchestrator.assess_source(AssessSourceRequest(source=source))
    assert assessed.source_profile.sampled_file_count == 4
    generated = await runtime.orchestrator.generate_configuration(
        GenerateConfigurationRequest(
            assessment_id=assessed.readiness_assessment.assessment_id,
            allowed_parsers=["databricks_primary", "native_text_reader"],
        )
    )
    validated = await runtime.orchestrator.validate_configuration(
        ValidateConfigurationRequest(proposal_id=generated.configuration_proposal.proposal_id)
    )
    assert validated.validation_result.status in {"VALID", "VALID_WITH_WARNINGS"}
    request = SampleRunRequest(
        proposal_id=generated.configuration_proposal.proposal_id,
        sample_size=4,
        approval=Approval(
            approved=True, approval_reference="CHG-10001", approved_by="engineer@example.com"
        ),
        dry_run=True,
    )
    first = await runtime.orchestrator.sample_run(request)
    second = await runtime.orchestrator.sample_run(request)
    assert first.sample_run.sample_run_id == second.sample_run.sample_run_id
    assert first.sample_run.status == "SUCCEEDED"


@pytest.mark.asyncio
async def test_disallowed_source_is_access_blocked(runtime):
    request = AssessSourceRequest(
        source={
            "source_id": "SRC-X",
            "source_name": "X",
            "source_type": "MOCK",
            "source_system": "fixture",
            "connection_reference": "mock",
            "source_location": "file:///tmp/not-allowed",
            "business_owner": "b",
            "technical_owner": "t",
        }
    )
    result = await runtime.orchestrator.assess_source(request)
    assert result.readiness_assessment.readiness_status == "ACCESS_BLOCKED"
