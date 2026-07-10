from processing_quality_agent.models.document import DocumentContext
from processing_quality_agent.models.quality import MetricEvidence


def evaluate(context: DocumentContext) -> MetricEvidence:
    doc = context.silver_document
    missing = []
    if doc is None:
        missing.append("silver_document")
    elif not doc.document_id or not doc.run_id:
        missing.append("identity")
    return MetricEvidence(
        metric="schema_validity",
        score=0.0 if missing else 1.0,
        observations=[f"Missing {x}" for x in missing],
    )
