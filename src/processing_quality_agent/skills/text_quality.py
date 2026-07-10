from processing_quality_agent.models.document import DocumentContext
from processing_quality_agent.models.quality import MetricEvidence


def evaluate(context: DocumentContext) -> MetricEvidence:
    text = context.silver_document.normalized_text.strip() if context.silver_document else ""
    if not text:
        return MetricEvidence(metric="text_quality", score=0, observations=["No normalized text"])
    printable = sum(character.isprintable() for character in text) / len(text)
    length_score = min(1.0, len(text) / 500)
    score = 0.7 * printable + 0.3 * length_score
    return MetricEvidence(
        metric="text_quality",
        score=score,
        observations=[f"{len(text)} characters; printable ratio {printable:.2f}"],
    )
