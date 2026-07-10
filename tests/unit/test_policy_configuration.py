import pytest

from source_readiness_agent.models.contracts import (
    Approval,
    AuditMetadata,
    ConnectionValidationResult,
    LandingConfiguration,
    Modality,
    SourceDefinition,
    SourceInventoryEstimate,
    SourceType,
)
from source_readiness_agent.orchestration.idempotency import idempotency_key
from source_readiness_agent.skills.checkpoint_validation import AutoLoaderConfigurationValidator
from source_readiness_agent.skills.ingestion_strategy import recommend_ingestion
from source_readiness_agent.skills.path_validation import validate_landing
from source_readiness_agent.skills.source_profiling import build_source_profile
from source_readiness_agent.tools.base import ApprovalRequired, require_approval


def landing(**changes):
    data = dict(
        storage_account_reference="acc",
        filesystem="landing",
        root_path="/landing/dev/{source_system}/{application}/{use_case}/{ingestion_date}/{batch_id}/",
        partition_pattern="/landing/{source_system}/{application}/{use_case}/{ingestion_date}/{batch_id}/",
        source_partition="SRC",
        retention_policy="R1",
        checkpoint_path="/checkpoints/dev/SRC/",
        schema_location="/schemas/dev/SRC/",
        quarantine_path="/quarantine/dev/SRC/",
        allowed_extensions=["pdf"],
    )
    data.update(changes)
    return LandingConfiguration(**data)


def test_path_and_checkpoint_validation():
    errors, _ = validate_landing(landing())
    assert not errors
    errors, _ = validate_landing(landing(checkpoint_path="/schemas/dev/SRC/"))
    assert any("distinct" in error for error in errors)
    auto = {
        "source_path": "/landing/",
        "checkpoint_path": "/cp/",
        "schema_location": "/schema/",
        "file_format": "binaryFile",
        "schema_evolution_mode": "rescue",
        "trigger_mode": "availableNow",
    }
    assert not AutoLoaderConfigurationValidator().validate(auto, "SRC")
    assert "checkpoint conflicts with another source" in AutoLoaderConfigurationValidator(
        lambda *_: False
    ).validate(auto, "SRC")


def test_approval_and_idempotency():
    audit = AuditMetadata(actor="a", reason="r", correlation_id="c")
    with pytest.raises(ApprovalRequired):
        require_approval(Approval(), audit)
    require_approval(
        Approval(approved=True, approval_reference="CHG-1", approved_by="owner"), audit
    )
    assert idempotency_key("x", {"b": 2, "a": 1}) == idempotency_key("x", {"a": 1, "b": 2})


def test_ingestion_strategy_is_contextual():
    source = SourceDefinition(
        source_id="SRC",
        source_name="s",
        source_type=SourceType.API,
        source_system="api",
        connection_reference="ref",
        source_location="https://approved.example/source",
        business_owner="b",
        technical_owner="t",
        expected_modalities=[Modality.STRUCTURED],
    )
    profile = build_source_profile(
        "SRC",
        SourceInventoryEstimate(estimated_file_count=1, estimated_total_bytes=10),
        ConnectionValidationResult(accessible=True, allowed=True),
        [],
    )
    assert recommend_ingestion(source, profile)["selected_strategy"] == "API_PULL"
