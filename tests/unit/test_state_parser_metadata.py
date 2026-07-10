import pytest

from source_readiness_agent.models.contracts import FileProfile, Modality, SourceDefinition
from source_readiness_agent.orchestration.state import OperationState, WorkflowState
from source_readiness_agent.skills.metadata_profile_generation import generate_metadata_profile
from source_readiness_agent.skills.parser_eligibility import default_registry


def test_state_transitions_are_deterministic():
    state = OperationState(correlation_id="c", actor="a")
    state.transition(WorkflowState.SOURCE_VALIDATING)
    with pytest.raises(ValueError):
        state.transition(WorkflowState.ACTIVATED)


def test_parser_eligibility_and_metadata_provenance():
    profile = FileProfile(
        object_id="1",
        file_name="scan.pdf",
        file_type="pdf",
        detected_mime_type="application/pdf",
        mime_match=True,
        size_bytes=100,
        zero_byte=False,
        modality=Modality.DOCUMENT,
        scanned_probability=0.9,
        supported=True,
    )
    assert [x.parser_id for x in default_registry().eligible(profile, "dev")] == [
        "azure_document_intelligence"
    ]
    source = SourceDefinition(
        source_id="SRC",
        source_name="s",
        source_type="MOCK",
        source_system="mock",
        connection_reference="mock",
        source_location="mock://",
        business_owner="b",
        technical_owner="t",
    )
    metadata = generate_metadata_profile(source, ["region"])
    assert metadata.provenance["document_type"].startswith("AI-inferred")
    assert "region" in metadata.mandatory_document_fields
