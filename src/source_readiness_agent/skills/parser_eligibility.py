"""Configurable parser registry and deterministic eligibility."""

from dataclasses import dataclass, field
from typing import Any

from source_readiness_agent.models.contracts import FileProfile


@dataclass(frozen=True)
class ParserDefinition:
    parser_id: str
    parser_type: str
    enabled: bool
    supported_file_types: frozenset[str]
    supported_modalities: frozenset[str]
    minimum_file_size: int = 0
    maximum_file_size: int = 104_857_600
    scanned_document_support: bool = False
    table_support: bool = False
    layout_support: bool = False
    endpoint_reference: str | None = None
    default_configuration: dict[str, Any] = field(default_factory=dict)
    approved_environments: frozenset[str] = frozenset({"dev", "test", "prod"})
    cost_category: str = "MEDIUM"
    latency_category: str = "MEDIUM"
    fallback_eligibility: bool = True


class ParserRegistry:
    def __init__(self, definitions: list[ParserDefinition]) -> None:
        self.definitions = {item.parser_id: item for item in definitions}

    def eligible(
        self, profile: FileProfile, environment: str, allowed: set[str] | None = None
    ) -> list[ParserDefinition]:
        return [
            item
            for item in self.definitions.values()
            if item.enabled
            and (allowed is None or item.parser_id in allowed)
            and environment in item.approved_environments
            and profile.file_type in item.supported_file_types
            and item.minimum_file_size <= profile.size_bytes <= item.maximum_file_size
            and (profile.scanned_probability < 0.7 or item.scanned_document_support)
        ]


def default_registry() -> ParserRegistry:
    return ParserRegistry(
        [
            ParserDefinition(
                "databricks_primary",
                "DATABRICKS_NATIVE",
                True,
                frozenset({"pdf", "docx", "pptx"}),
                frozenset({"DOCUMENT"}),
                table_support=True,
                layout_support=True,
            ),
            ParserDefinition(
                "azure_document_intelligence",
                "AZURE_DOCUMENT_INTELLIGENCE",
                True,
                frozenset({"pdf", "png", "jpg", "jpeg", "tif", "tiff"}),
                frozenset({"DOCUMENT", "IMAGE"}),
                scanned_document_support=True,
                table_support=True,
                layout_support=True,
                cost_category="HIGH",
            ),
            ParserDefinition(
                "native_text_reader",
                "NATIVE",
                True,
                frozenset({"txt", "html", "xml", "json"}),
                frozenset({"TEXT", "STRUCTURED"}),
                cost_category="LOW",
                latency_category="LOW",
            ),
        ]
    )
