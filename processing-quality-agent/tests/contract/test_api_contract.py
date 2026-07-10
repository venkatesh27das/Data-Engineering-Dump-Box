from fastapi.testclient import TestClient

from processing_quality_agent.app import create_app
from processing_quality_agent.config import Settings


def test_typed_and_responses_endpoints():
    with TestClient(create_app(Settings(use_mock_tools=True, mlflow_experiment=""))) as client:
        response = client.post("/api/v1/investigate", json={"document_id": "DOC-102"})
        assert response.status_code == 200
        assert response.json()["operation_mode"] == "INVESTIGATE"
        invocation = client.post(
            "/invocations",
            json={
                "input": "Why did it fail?",
                "custom_inputs": {"mode": "INVESTIGATE", "document_id": "DOC-102"},
            },
        )
        assert invocation.status_code == 200
        assert invocation.json()["object"] == "response"
        assert (
            invocation.json()["custom_outputs"]["diagnosis"]["primary_failure"]
            == "TABLE_EXTRACTION_FAILURE"
        )


def test_validation_rejects_missing_selector():
    with TestClient(create_app(Settings(use_mock_tools=True, mlflow_experiment=""))) as client:
        response = client.post("/api/v1/investigate", json={})
        assert response.status_code == 422
