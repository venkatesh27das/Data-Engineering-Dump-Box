from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.domain.assets import (
    Entity,
    GraphSchema,
    KnowledgeAssetPackage,
    QualityDisposition,
    QualityReport,
    Relationship,
)


def test_entity_confidence_is_bounded() -> None:
    with pytest.raises(ValidationError):
        Entity(id="ENT-1", canonical_name="ACME", entity_type="Supplier", confidence=1.2)


def test_relationship_cannot_self_reference() -> None:
    with pytest.raises(ValidationError):
        Relationship(id="REL-1", source_entity_id="ENT-1", target_entity_id="ENT-1", relationship_type="SUPPLIES", confidence=0.9)


def test_package_rejects_missing_entity_references() -> None:
    quality = QualityReport(overall_score=0.9, evidence_coverage=0.9, average_confidence=0.9, consistency=0.9, completeness=0.9, disposition=QualityDisposition.PASS)
    with pytest.raises(ValidationError):
        KnowledgeAssetPackage(
            package_id="PKG-1",
            project_id="project-1",
            sources=[],
            entities=[Entity(id="ENT-1", canonical_name="ACME", entity_type="Supplier", confidence=0.9)],
            relationships=[Relationship(id="REL-1", source_entity_id="ENT-1", target_entity_id="ENT-2", relationship_type="SUPPLIES", confidence=0.9)],
            graph_schema=GraphSchema(),
            quality_report=quality,
            created_at=datetime.now(UTC),
        )
