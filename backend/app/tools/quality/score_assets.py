from uuid import uuid4

from app.domain.assets import Concept, Entity, Event, Fact, QualityDisposition, QualityIssue, QualityReport, Relationship, SemanticMapping


def score_assets(*, entities: list[Entity], relationships: list[Relationship], concepts: list[Concept], facts: list[Fact], events: list[Event], semantic_mappings: list[SemanticMapping], unresolved_references: int = 0, ambiguous_entities: int = 0) -> QualityReport:
    assets = [*entities, *relationships, *concepts, *facts, *events, *semantic_mappings]
    if not assets:
        return QualityReport(overall_score=0, evidence_coverage=0, average_confidence=0, consistency=0, completeness=0, unresolved_references=unresolved_references, disposition=QualityDisposition.FAIL, issues=[QualityIssue(id=str(uuid4()), severity="error", code="NO_ASSETS", message="No knowledge assets were generated")])
    evidence_coverage = sum(bool(asset.evidence) for asset in assets) / len(assets)
    average_confidence = sum(asset.confidence for asset in assets) / len(assets)
    consistency = max(0.0, 1 - unresolved_references / max(1, len(relationships)))
    required_groups = [entities, relationships, concepts]
    completeness = sum(bool(group) for group in required_groups) / len(required_groups)
    issues: list[QualityIssue] = []
    if ambiguous_entities:
        issues.append(QualityIssue(id=str(uuid4()), severity="warning", code="AMBIGUOUS_ENTITIES", message=f"{ambiguous_entities} entity matches require review"))
    if evidence_coverage < 1:
        issues.append(QualityIssue(id=str(uuid4()), severity="error", code="MISSING_EVIDENCE", message="One or more assets are missing provenance"))
    overall = 0.35 * evidence_coverage + 0.3 * average_confidence + 0.2 * consistency + 0.15 * completeness
    disposition = QualityDisposition.PASS if overall >= 0.8 and not issues else QualityDisposition.REVIEW_REQUIRED
    return QualityReport(overall_score=overall, evidence_coverage=evidence_coverage, average_confidence=average_confidence, consistency=consistency, completeness=completeness, unresolved_references=unresolved_references, disposition=disposition, issues=issues)
