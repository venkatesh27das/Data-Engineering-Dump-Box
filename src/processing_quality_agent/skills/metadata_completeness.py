from processing_quality_agent.models.document import DocumentContext
from processing_quality_agent.models.quality import MetricEvidence


def evaluate(context: DocumentContext) -> MetricEvidence:
    required = {"file_name", "mime_type", "file_hash", "source_system"}
    manifest = context.manifest.model_dump()
    present = sum(bool(manifest.get(key)) for key in required)
    score = present / len(required)
    return MetricEvidence(
        metric="metadata_completeness",
        score=score,
        observations=[f"{present}/{len(required)} required fields present"],
    )
