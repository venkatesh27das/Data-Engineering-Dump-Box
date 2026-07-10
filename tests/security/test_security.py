import pytest

from source_readiness_agent.logging_config import redact
from source_readiness_agent.models.contracts import SourceDefinition
from source_readiness_agent.tools.registry import ToolRegistry


def test_path_traversal_rejected():
    with pytest.raises(ValueError):
        SourceDefinition(
            source_id="SRC",
            source_name="s",
            source_type="MOCK",
            source_system="mock",
            connection_reference="mock",
            source_location="mock://../secret",
            business_owner="b",
            technical_owner="t",
        )


def test_secret_redaction():
    value = redact({"token": "abc", "message": "password=hunter2"})
    assert value["token"] == "[REDACTED]"
    assert "hunter2" not in value["message"]


def test_arbitrary_sql_tool_is_rejected():
    class Tool:
        descriptor = type(
            "D", (), {"name": "execute_sql", "mutating": False, "approval_required": False}
        )()

    with pytest.raises(ValueError):
        ToolRegistry().register(Tool())
