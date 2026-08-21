from typing import Protocol

from app.agents.schemas import FeedbackInterpretation
from app.processing.extractor import ExtractionResult


class AgentRuntime(Protocol):
    framework_name: str

    def enrich(self, result: ExtractionResult) -> dict: ...

    def create_embeddings(self, chunks: list[dict]) -> list[dict]: ...

    def interpret_feedback(self, text: str) -> FeedbackInterpretation: ...

    def probe(self) -> dict: ...
