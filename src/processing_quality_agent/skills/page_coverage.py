from processing_quality_agent.models.document import DocumentContext
from processing_quality_agent.models.quality import MetricEvidence


def evaluate(context: DocumentContext) -> MetricEvidence:
    doc = context.silver_document
    if not doc or doc.page_count <= 0:
        return MetricEvidence(
            metric="page_coverage", score=0, observations=["No page count available"]
        )
    score = min(1.0, doc.extracted_page_count / doc.page_count)
    return MetricEvidence(
        metric="page_coverage",
        score=score,
        observations=[f"Extracted {doc.extracted_page_count}/{doc.page_count} pages"],
    )
