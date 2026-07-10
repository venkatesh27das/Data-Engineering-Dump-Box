from processing_quality_agent.models.document import DocumentContext
from processing_quality_agent.models.quality import MetricEvidence


def evaluate(context: DocumentContext) -> MetricEvidence:
    doc = context.silver_document
    if not doc:
        return MetricEvidence(metric="layout_quality", score=0, observations=["No document output"])
    elements = context.silver_elements
    if not elements:
        return MetricEvidence(
            metric="layout_quality",
            score=0.5 if doc.layout_payload else 0,
            observations=["No normalized elements"],
        )
    boxed = sum(bool(element.bounding_box) for element in elements) / len(elements)
    return MetricEvidence(
        metric="layout_quality", score=boxed, observations=[f"{boxed:.0%} elements have geometry"]
    )
