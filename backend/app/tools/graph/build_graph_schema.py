import re

from app.domain.assets import Entity, GraphNodeDefinition, GraphPropertyDefinition, GraphRelationshipDefinition, GraphSchema, Relationship


def _identifier(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", value).strip("_")
    if not cleaned:
        return "Other"
    return f"N_{cleaned}" if cleaned[0].isdigit() else cleaned


def build_graph_schema(entities: list[Entity], relationships: list[Relationship]) -> GraphSchema:
    type_by_id = {entity.id: _identifier(entity.entity_type) for entity in entities}
    labels = sorted(set(type_by_id.values()))
    node_definitions = [GraphNodeDefinition(label=label, properties=[GraphPropertyDefinition(name="asset_id", data_type="string", required=True), GraphPropertyDefinition(name="name", data_type="string", required=True), GraphPropertyDefinition(name="confidence", data_type="float", required=True)]) for label in labels]
    relationship_keys = sorted({(_identifier(relationship.relationship_type).upper(), type_by_id[relationship.source_entity_id], type_by_id[relationship.target_entity_id]) for relationship in relationships})
    relationship_definitions = [GraphRelationshipDefinition(relationship_type=relationship_type, source_label=source_label, target_label=target_label, properties=[GraphPropertyDefinition(name="asset_id", data_type="string", required=True), GraphPropertyDefinition(name="confidence", data_type="float", required=True)]) for relationship_type, source_label, target_label in relationship_keys]
    return GraphSchema(node_definitions=node_definitions, relationship_definitions=relationship_definitions, constraints=[f"UNIQUE {label}.asset_id" for label in labels])
