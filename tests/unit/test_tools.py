import pytest

from processing_quality_agent.models.parser import ParserRequest
from processing_quality_agent.models.recovery import ApprovalContext
from processing_quality_agent.tools.azure_document_intelligence import (
    AzureDocumentIntelligenceAdapter,
)
from processing_quality_agent.tools.base import ToolError, WriteContext
from processing_quality_agent.tools.bronze_reader import BronzeReader
from processing_quality_agent.tools.custom_parser import CustomParserAdapter
from processing_quality_agent.tools.databricks_parser import DatabricksParserAdapter
from processing_quality_agent.tools.mcp_client import DisabledMCPClient
from processing_quality_agent.tools.metrics_reader import MetricsReader
from processing_quality_agent.tools.mock_repository import InMemoryRepository
from processing_quality_agent.tools.registry import ToolRegistry
from processing_quality_agent.tools.review_queue import (
    HumanReviewRequest,
    InMemoryReviewQueue,
)
from processing_quality_agent.tools.silver_reader import ParserHistoryReader
from processing_quality_agent.tools.status_writer import GovernedWriter


async def test_read_tools_and_registry():
    repository = InMemoryRepository()
    bronze = BronzeReader(repository)
    history = ParserHistoryReader(repository)
    metrics = MetricsReader(repository)
    registry = ToolRegistry()
    registry.register(bronze)
    assert registry.get("get_document_context") is bronze
    assert (await bronze.invoke("DOC-102")).manifest.document_id == "DOC-102"
    assert len(await history.invoke("DOC-102")) == 1
    assert len(await metrics.invoke(["databricks_primary"])) == 1
    with pytest.raises(ToolError, match="unregistered"):
        registry.get("missing")
    with pytest.raises(ToolError, match="duplicate"):
        registry.register(bronze)


async def test_governed_writer_dry_run_and_idempotent_write():
    repository = InMemoryRepository()
    writer = GovernedWriter("update_processing_status", "update state", repository)
    approval = ApprovalContext(
        approved=True, approval_reference="CHG-1", approved_by="engineer@example.com"
    )
    context = WriteContext("engineer@example.com", approval, "recovery", "corr", True)
    dry = await writer.invoke(write_context=context, idempotency_key="key", payload={})
    assert dry["status"] == "DRY_RUN"
    live_context = WriteContext("engineer@example.com", approval, "recovery", "corr")
    first = await writer.invoke(
        write_context=live_context, idempotency_key="key", payload={"status": "READY"}
    )
    second = await writer.invoke(
        write_context=live_context, idempotency_key="key", payload={"status": "OTHER"}
    )
    assert first == second


async def test_review_queue_and_disabled_mcp():
    queue = InMemoryReviewQueue()
    request = HumanReviewRequest(
        review_id="R1",
        document_id="D",
        run_id="run",
        issue_type="OCR",
        severity="HIGH",
        issue_summary="unreadable",
        recommended_action="review",
        created_by="agent",
    )
    assert (await queue.submit(request)).review_id == "R1"
    assert await DisabledMCPClient().discover_tools() == []
    with pytest.raises(RuntimeError, match="not configured"):
        await DisabledMCPClient().call_tool("x", {})


async def test_parser_adapter_guards_and_health():
    context = await InMemoryRepository().get_document_context("DOC-102")
    databricks = DatabricksParserAdapter()
    assert databricks.is_eligible(context).eligible
    assert not (await databricks.health_check()).healthy
    result = await databricks.parse(
        ParserRequest(document_id="D", source_file_uri="abfss://container/file.pdf")
    )
    assert result.error_code == "PARSER_CONFIGURATION_ERROR"
    azure = AzureDocumentIntelligenceAdapter(None)
    assert azure.is_eligible(context).eligible
    assert not (await azure.health_check()).healthy
    custom = CustomParserAdapter()
    assert not custom.is_eligible(context).eligible
    with pytest.raises(RuntimeError, match="disabled"):
        await custom.parse(ParserRequest(document_id="D", source_file_uri="abfss://x"))
