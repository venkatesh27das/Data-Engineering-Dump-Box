from processing_quality_agent.logging_config import redact


def test_secret_redaction_nested():
    output = redact({"api_key": "secret", "nested": {"token": "token", "safe": 1}})
    assert output["api_key"] == "[REDACTED]"
    assert output["nested"]["token"] == "[REDACTED]"
    assert output["nested"]["safe"] == 1
