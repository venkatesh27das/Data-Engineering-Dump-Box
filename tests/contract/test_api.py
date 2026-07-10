from fastapi.testclient import TestClient

from source_readiness_agent.app import create_app
from source_readiness_agent.config import Settings


def test_health_ready_and_responses_validation():
    client = TestClient(create_app(Settings(app_env="local", use_mock_tools=True)))
    assert client.get("/health").json() == {"status": "healthy"}
    assert client.get("/ready").json()["activation_enabled"] is False
    response = client.post(
        "/invocations", json={"input": [{"role": "user", "content": "not-json"}]}
    )
    assert response.status_code == 422


def test_activation_disabled_by_default():
    client = TestClient(
        create_app(Settings(app_env="local", use_mock_tools=True, activation_enabled=False))
    )
    response = client.post(
        "/api/v1/activate",
        json={
            "validated_configuration_id": "P",
            "successful_sample_run_id": "R",
            "approval": {"approved": True, "approval_reference": "CHG", "approved_by": "owner"},
            "change_reference": "CHG",
        },
    )
    assert response.status_code == 403
