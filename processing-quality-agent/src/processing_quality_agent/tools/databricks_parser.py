from __future__ import annotations

from processing_quality_agent.models.document import DocumentContext
from processing_quality_agent.models.parser import (
    CostEstimate,
    EligibilityResult,
    HealthStatus,
    ParserRequest,
    ParserResult,
    ParserStatus,
)
from processing_quality_agent.tools.workflow_client import DatabricksWorkflowClient


class DatabricksParserAdapter:
    parser_id = "databricks_primary"

    def __init__(self, workflow_client: DatabricksWorkflowClient | None = None) -> None:
        self.workflow_client = workflow_client

    def is_eligible(self, document: DocumentContext) -> EligibilityResult:
        return EligibilityResult(
            eligible=document.manifest.mime_type in {"application/pdf", "text/plain"}
        )

    def estimate_cost(self, request: ParserRequest) -> CostEstimate:
        return CostEstimate(amount=0.01, basis="configured workflow estimate")

    async def health_check(self) -> HealthStatus:
        return HealthStatus(
            healthy=self.workflow_client is not None,
            detail="Configure a governed SQL function, job, or endpoint in production.",
        )

    async def parse(self, request: ParserRequest) -> ParserResult:
        if not self.workflow_client:
            return ParserResult(
                parser_id=self.parser_id,
                status=ParserStatus.FAILED,
                error_code="PARSER_CONFIGURATION_ERROR",
                error_message="Databricks parser invocation is not configured",
            )
        return ParserResult(
            parser_id=self.parser_id,
            status=ParserStatus.FAILED,
            error_code="PARSER_CONFIGURATION_ERROR",
            error_message="Use the recovery workflow so run lineage and approval are preserved",
        )
