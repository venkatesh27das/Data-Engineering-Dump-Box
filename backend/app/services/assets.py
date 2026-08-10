from collections.abc import Iterable

from app.domain.assets import (
    Concept,
    Entity,
    Event,
    Fact,
    KnowledgeAssetPackage,
    Relationship,
    ReviewStatus,
)
from app.domain.review import AssetKind, AssetPage, AssetView

ReviewableAsset = Entity | Relationship | Concept | Fact | Event


class AssetNotFoundError(LookupError):
    pass


class AssetService:
    @staticmethod
    def page(
        package: KnowledgeAssetPackage,
        kind: AssetKind,
        *,
        search: str | None,
        asset_type: str | None,
        source: str | None,
        minimum_confidence: float | None,
        maximum_confidence: float | None,
        review_status: ReviewStatus | None,
        page: int,
        page_size: int,
    ) -> AssetPage:
        views = [AssetService.to_view(asset, kind, package) for asset in AssetService._assets(package, kind)]
        available_types = sorted({view.asset_type for view in views})
        available_sources = sorted({evidence.source_name for view in views for evidence in view.evidence})
        query = search.casefold().strip() if search else None
        filtered = [
            view
            for view in views
            if (not query or query in view.name.casefold() or query in view.asset_type.casefold())
            and (not asset_type or view.asset_type == asset_type)
            and (not source or any(evidence.source_name == source for evidence in view.evidence))
            and (minimum_confidence is None or view.confidence >= minimum_confidence)
            and (maximum_confidence is None or view.confidence <= maximum_confidence)
            and (review_status is None or view.review_status == review_status)
        ]
        start = (page - 1) * page_size
        return AssetPage(
            kind=kind,
            items=filtered[start : start + page_size],
            total=len(filtered),
            page=page,
            page_size=page_size,
            available_types=available_types,
            available_sources=available_sources,
        )

    @staticmethod
    def set_review_status(
        package: KnowledgeAssetPackage,
        asset_id: str,
        status: ReviewStatus,
    ) -> tuple[KnowledgeAssetPackage, AssetView]:
        for kind in AssetKind:
            collection = list(AssetService._assets(package, kind))
            for index, asset in enumerate(collection):
                if asset.id != asset_id:
                    continue
                updated = asset.model_copy(update={"review_status": status})
                collection[index] = updated
                updated_package = package.model_copy(update={kind.value: collection})
                return updated_package, AssetService.to_view(updated, kind, updated_package)
        raise AssetNotFoundError(asset_id)

    @staticmethod
    def to_view(asset: ReviewableAsset, kind: AssetKind, package: KnowledgeAssetPackage) -> AssetView:
        if isinstance(asset, Entity):
            return AssetView(id=asset.id, kind=kind, name=asset.canonical_name, asset_type=asset.entity_type, confidence=asset.confidence, review_status=asset.review_status, evidence=asset.evidence, aliases=asset.aliases, attributes=asset.attributes)
        if isinstance(asset, Relationship):
            entity_names = {entity.id: entity.canonical_name for entity in package.entities}
            source_name = entity_names.get(asset.source_entity_id, asset.source_entity_id)
            target_name = entity_names.get(asset.target_entity_id, asset.target_entity_id)
            return AssetView(id=asset.id, kind=kind, name=f"{source_name} → {target_name}", asset_type=asset.relationship_type, confidence=asset.confidence, review_status=asset.review_status, evidence=asset.evidence, attributes=asset.properties, source_entity_id=asset.source_entity_id, target_entity_id=asset.target_entity_id)
        if isinstance(asset, Concept):
            attributes = {"definition": asset.definition, "broader_concept_id": asset.broader_concept_id}
            return AssetView(id=asset.id, kind=kind, name=asset.name, asset_type="Concept", confidence=asset.confidence, review_status=asset.review_status, evidence=asset.evidence, aliases=asset.synonyms, attributes=attributes)
        if isinstance(asset, Fact):
            attributes = {"subject": asset.subject, "predicate": asset.predicate, "object": asset.object, **asset.qualifiers}
            return AssetView(id=asset.id, kind=kind, name=f"{asset.subject} {asset.predicate} {asset.object}", asset_type="Fact", confidence=asset.confidence, review_status=asset.review_status, evidence=asset.evidence, attributes=attributes)
        attributes = {"occurred_at": asset.occurred_at.isoformat() if asset.occurred_at else None, "participants": ", ".join(asset.participants), **asset.attributes}
        return AssetView(id=asset.id, kind=kind, name=asset.name, asset_type=asset.event_type, confidence=asset.confidence, review_status=asset.review_status, evidence=asset.evidence, attributes=attributes)

    @staticmethod
    def _assets(package: KnowledgeAssetPackage, kind: AssetKind) -> Iterable[ReviewableAsset]:
        return getattr(package, kind.value)
