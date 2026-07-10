import json
from pathlib import Path

import pytest

from source_readiness_agent.agent import parse_responses_request
from source_readiness_agent.app import build_runtime
from source_readiness_agent.config import Settings
from source_readiness_agent.connectors.mock import MockConnector
from source_readiness_agent.services.assessment_service import AssessmentService


def test_parse_simple_and_responses_envelopes():
    assert parse_responses_request({"operation_mode": "X", "payload": {"a": 1}}) == (
        "X",
        {"a": 1},
    )
    body = {"operation_mode": "X", "payload": {"a": 1}}
    request = {
        "input": [
            {
                "role": "user",
                "content": [{"type": "input_text", "text": json.dumps(body)}],
            }
        ]
    }
    assert parse_responses_request(request) == ("X", {"a": 1})
    with pytest.raises(ValueError):
        parse_responses_request({"input": "bad"})


@pytest.mark.asyncio
async def test_agent_assess_dispatch_and_reject_chat():
    settings = Settings(source_allowlist_json='["mock://"]')
    runtime = build_runtime(settings)
    runtime.orchestrator.assessment_service = AssessmentService(
        runtime.repository,
        settings,
        {"MOCK": MockConnector(Path("tests/fixtures/mock_source").resolve(), ["mock://"])},
        {"pdf", "txt", "json"},
    )
    payload = {
        "source": {
            "source_id": "SRC-R",
            "source_name": "Responses",
            "source_type": "MOCK",
            "source_system": "fixture",
            "connection_reference": "mock",
            "source_location": "mock://",
            "business_owner": "b",
            "technical_owner": "t",
        }
    }
    result = await runtime.agent.invoke_structured("ASSESS_SOURCE", payload)
    assert result["operation_mode"] == "ASSESS_SOURCE"
    with pytest.raises(ValueError):
        await runtime.agent.invoke_structured("CHAT", {})
