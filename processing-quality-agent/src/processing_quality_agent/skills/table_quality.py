from processing_quality_agent.models.document import DocumentContext
from processing_quality_agent.models.quality import MetricEvidence


def evaluate(context: DocumentContext) -> MetricEvidence:
    doc = context.silver_document
    expected = bool(context.manifest.source_metadata.get("tables_expected"))
    tables = doc.table_payload if doc else []
    if not expected:
        return MetricEvidence(metric="table_quality", score=1, observations=["Tables not required"])
    if not tables:
        return MetricEvidence(
            metric="table_quality", score=0, observations=["Expected tables are missing"]
        )
    structured = sum(bool(table.get("cells") or table.get("rows")) for table in tables) / len(
        tables
    )
    return MetricEvidence(
        metric="table_quality", score=structured, observations=[f"Found {len(tables)} tables"]
    )
