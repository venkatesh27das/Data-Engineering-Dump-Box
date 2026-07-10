import pytest

from source_readiness_agent.config import Settings
from source_readiness_agent.models.contracts import (
    Approval,
    AuditMetadata,
    BronzeConfiguration,
    ConfigurationProposal,
    IngestionConfiguration,
    IngestionMethod,
    LandingConfiguration,
    MetadataProfile,
    ParserRoutingProfile,
    RunStatus,
    SampleRun,
    SamplingStrategy,
    ValidationStatus,
)
from source_readiness_agent.models.requests import ActivateConfigurationRequest
from source_readiness_agent.orchestration.planner import plan
from source_readiness_agent.services.activation_service import ActivationService
from source_readiness_agent.tools.adf_client import AzureDataFactoryClient
from source_readiness_agent.tools.bronze_config_reader import BronzeConfigurationReader
from source_readiness_agent.tools.bronze_config_writer import BronzeConfigurationWriter
from source_readiness_agent.tools.mcp_client import MockMCPClient
from source_readiness_agent.tools.repository import InMemoryRepository
from source_readiness_agent.tools.sample_result_reader import SampleResultReader
from source_readiness_agent.tools.workflow_client import DatabricksWorkflowClient


def proposal() -> ConfigurationProposal:
    landing = LandingConfiguration(
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
    return ConfigurationProposal(
        proposal_id="P1",
        source_id="SRC",
        environment="dev",
        version=1,
        assessment_id="A1",
        ingestion_configuration=IngestionConfiguration(
            ingestion_method=IngestionMethod.DATABRICKS_CONNECTOR_BATCH,
            connector_id="c",
            schedule="daily",
            incremental_strategy="BATCH_ID",
            landing_configuration=landing,
        ),
        landing_configuration=landing,
        bronze_configuration=BronzeConfiguration(
            target_catalog="c",
            target_schema="b",
            volume_name="v",
            manifest_table="m",
            exception_table="e",
            parser_config_table="p",
            lineage_table="l",
            source_to_manifest_mapping={"id": "id"},
        ),
        parser_routing_profile=ParserRoutingProfile(
            eligible_file_types=["pdf"], primary_parser="databricks_primary"
        ),
        metadata_profile=MetadataProfile(
            mandatory_source_fields=["source_id"], mandatory_document_fields=["file_name"]
        ),
        validation_status=ValidationStatus.VALID,
        created_by="engineer",
    )


@pytest.mark.asyncio
async def test_mock_action_clients_and_mcp_are_idempotent():
    adf = AzureDataFactoryClient({"sample"}, enabled=False)
    assert not await adf.validate_pipeline_exists("sample")
    with pytest.raises(PermissionError):
        await adf.trigger_pipeline_run("bad", {}, "k", True)
    run = await adf.trigger_pipeline_run("sample", {}, "k", True)
    assert run == await adf.trigger_pipeline_run("sample", {}, "k", True)
    assert await adf.wait_for_completion(run) == "SUCCEEDED"
    await adf.cancel_pipeline_run(run)

    workflow = DatabricksWorkflowClient(enabled=False)
    assert not await workflow.validate_job_exists()
    run = await workflow.trigger_sample_run({}, "k", True)
    assert await workflow.get_run_status(run) == "SUCCEEDED"
    await workflow.cancel_run(run)

    mcp = MockMCPClient({"echo": lambda args: args})
    assert await mcp.discover_tools() == [{"name": "echo", "mutating": False}]
    assert await mcp.call_tool("echo", {"ok": True}) == {"ok": True}
    with pytest.raises(KeyError):
        await mcp.call_tool("missing", {})


def test_repository_read_write_activation_and_planner():
    repository = InMemoryRepository()
    value = proposal()
    repository.save_proposal(value)
    assert (
        BronzeConfigurationReader(repository).get_existing_source_configuration("P1").version == 1
    )
    approval = Approval(approved=True, approval_reference="CHG", approved_by="owner")
    audit = AuditMetadata(actor="engineer", reason="activate", correlation_id="C")
    assert (
        BronzeConfigurationWriter(repository)
        .register_approved_source_configuration(value, approval, audit)
        .active
    )
    run = SampleRun(
        sample_run_id="R1",
        proposal_id="P1",
        source_id="SRC",
        selected_objects=[],
        selection_strategy=SamplingStrategy.HYBRID,
        workflow_type="MOCK",
        status=RunStatus.SUCCEEDED,
        idempotency_key="k",
    )
    repository.save_sample_run(run)
    assert SampleResultReader(repository).get_sample_run_status("R1").status == "SUCCEEDED"
    assert plan("ASSESS_SOURCE") == "assessment_service"
    with pytest.raises(ValueError):
        plan("CHAT")


def test_activation_service_success_and_guards():
    repository = InMemoryRepository()
    value = proposal()
    repository.save_proposal(value)
    repository.save_sample_run(
        SampleRun(
            sample_run_id="R1",
            proposal_id="P1",
            source_id="SRC",
            selected_objects=[],
            selection_strategy=SamplingStrategy.HYBRID,
            workflow_type="MOCK",
            status=RunStatus.SUCCEEDED,
            idempotency_key="k",
        )
    )
    request = ActivateConfigurationRequest(
        validated_configuration_id="P1",
        successful_sample_run_id="R1",
        approval=Approval(approved=True, approval_reference="CHG", approved_by="owner"),
        change_reference="CHG",
    )
    with pytest.raises(PermissionError):
        ActivationService(repository, Settings(activation_enabled=False)).activate(request, "C")
    active = ActivationService(repository, Settings(activation_enabled=True)).activate(request, "C")
    assert active.active and active.approval_reference == "CHG"
