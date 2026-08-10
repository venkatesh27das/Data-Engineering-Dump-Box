import json
import re
from collections import defaultdict
from datetime import date, datetime

from neo4j import AsyncGraphDatabase
from neo4j.graph import Node, Path, Relationship

from app.domain.assets import KnowledgeAssetPackage, ReviewStatus
from app.domain.publication import PublicationResult
from app.graph.base import GraphStore, GraphStoreError, GraphStoreNotConfigured

_RELATIONSHIP_TYPE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_LABEL = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,63}$")


class Neo4jGraphStore(GraphStore):
    def __init__(self, *, uri: str, username: str, password: str, database: str = "neo4j") -> None:
        self.uri = uri
        self.username = username
        self.password = password
        self.database = database

    @property
    def configured(self) -> bool:
        return bool(self.uri and self.username and self.password and self.database)

    def _driver(self):
        if not self.configured:
            raise GraphStoreNotConfigured("Neo4j credentials are not configured")
        return AsyncGraphDatabase.driver(self.uri, auth=(self.username, self.password))

    async def health_check(self) -> bool:
        if not self.configured:
            return False
        try:
            async with self._driver() as driver:
                records, _, _ = await driver.execute_query("RETURN 1 AS ok", database_=self.database)
                if not records or records[0]["ok"] != 1:
                    return False
            return True
        except Exception:
            return False

    async def publish_package(self, package: KnowledgeAssetPackage) -> PublicationResult:
        approved_entity_ids = {entity.id for entity in package.entities if entity.review_status == ReviewStatus.APPROVED}
        node_groups: dict[str, list[dict[str, object]]] = defaultdict(list)
        relationship_groups: dict[str, list[dict[str, object]]] = defaultdict(list)
        total_reviewable = len(package.entities) + len(package.relationships) + len(package.concepts) + len(package.facts) + len(package.events)

        for entity in package.entities:
            if entity.review_status != ReviewStatus.APPROVED:
                continue
            label = entity.entity_type if _LABEL.fullmatch(entity.entity_type) else "Entity"
            node_groups[f"Entity:{label}"].append(self._node_row(package, entity.id, {
                "name": entity.canonical_name,
                "asset_type": entity.entity_type,
                "confidence": entity.confidence,
                "aliases": entity.aliases,
                "attributes_json": json.dumps(entity.attributes, sort_keys=True),
                "evidence_json": self._evidence_json(entity.evidence),
                "source_names": sorted({item.source_name for item in entity.evidence}),
            }))
        for concept in package.concepts:
            if concept.review_status == ReviewStatus.APPROVED:
                node_groups["Concept"].append(self._node_row(package, concept.id, {"name": concept.name, "asset_type": "Concept", "definition": concept.definition, "confidence": concept.confidence, "aliases": concept.synonyms, "evidence_json": self._evidence_json(concept.evidence), "source_names": sorted({item.source_name for item in concept.evidence})}))
        for fact in package.facts:
            if fact.review_status == ReviewStatus.APPROVED:
                node_groups["Fact"].append(self._node_row(package, fact.id, {"name": f"{fact.subject} {fact.predicate} {fact.object}", "asset_type": "Fact", "subject": fact.subject, "predicate": fact.predicate, "object": fact.object, "confidence": fact.confidence, "attributes_json": json.dumps(fact.qualifiers, sort_keys=True), "evidence_json": self._evidence_json(fact.evidence), "source_names": sorted({item.source_name for item in fact.evidence})}))
        for event in package.events:
            if event.review_status == ReviewStatus.APPROVED:
                node_groups["Event"].append(self._node_row(package, event.id, {"name": event.name, "asset_type": event.event_type, "occurred_at": event.occurred_at.isoformat() if event.occurred_at else None, "participants": event.participants, "confidence": event.confidence, "attributes_json": json.dumps(event.attributes, sort_keys=True), "evidence_json": self._evidence_json(event.evidence), "source_names": sorted({item.source_name for item in event.evidence})}))

        for relationship in package.relationships:
            if relationship.review_status != ReviewStatus.APPROVED:
                continue
            if relationship.source_entity_id not in approved_entity_ids or relationship.target_entity_id not in approved_entity_ids:
                continue
            if not _RELATIONSHIP_TYPE.fullmatch(relationship.relationship_type):
                continue
            relationship_groups[relationship.relationship_type].append({
                "project_id": package.project_id,
                "package_id": package.package_id,
                "asset_id": relationship.id,
                "source_id": relationship.source_entity_id,
                "target_id": relationship.target_entity_id,
                "properties": {
                    "confidence": relationship.confidence,
                    "properties_json": json.dumps(relationship.properties, sort_keys=True),
                    "evidence_json": self._evidence_json(relationship.evidence),
                    "source_names": sorted({item.source_name for item in relationship.evidence}),
                    "review_status": relationship.review_status.value,
                    "package_id": package.package_id,
                },
            })

        node_count = sum(len(rows) for rows in node_groups.values())
        relationship_count = sum(len(rows) for rows in relationship_groups.values())
        try:
            async with self._driver() as driver:
                async with driver.session(database=self.database) as session:
                    await session.execute_write(self._publish_transaction, node_groups, relationship_groups)
        except GraphStoreNotConfigured:
            raise
        except Exception as error:
            raise GraphStoreError("Neo4j publication failed") from error
        return PublicationResult(nodes_published=node_count, relationships_published=relationship_count, assets_skipped=total_reviewable - node_count - relationship_count)

    @staticmethod
    async def _publish_transaction(tx, node_groups: dict[str, list[dict[str, object]]], relationship_groups: dict[str, list[dict[str, object]]]) -> None:
        for labels, rows in node_groups.items():
            safe_labels = ":".join(labels.split(":"))
            result = await tx.run(
                f"""
                UNWIND $rows AS row
                MERGE (n:KnowledgeAsset:{safe_labels} {{project_id: row.project_id, asset_id: row.asset_id}})
                SET n += row.properties, n.package_id = row.package_id, n.review_status = 'approved', n.updated_at = datetime()
                """,
                rows=rows,
            )
            await result.consume()
        for relationship_type, rows in relationship_groups.items():
            result = await tx.run(
                f"""
                UNWIND $rows AS row
                MATCH (source:KnowledgeAsset {{project_id: row.project_id, asset_id: row.source_id}})
                MATCH (target:KnowledgeAsset {{project_id: row.project_id, asset_id: row.target_id}})
                MERGE (source)-[r:{relationship_type} {{project_id: row.project_id, asset_id: row.asset_id}}]->(target)
                SET r += row.properties, r.updated_at = datetime()
                """,
                rows=rows,
            )
            await result.consume()

    async def get_subgraph(self, project_id: str) -> dict[str, list[dict[str, object]]]:
        query = """
        MATCH (n:KnowledgeAsset {project_id: $project_id})
        OPTIONAL MATCH (n)-[r]->(m:KnowledgeAsset {project_id: $project_id})
        RETURN collect(DISTINCT {data: {id: n.asset_id, label: n.name, type: n.asset_type, confidence: n.confidence, sources: coalesce(n.source_names, []), search_text: toLower(coalesce(n.name, '') + ' ' + coalesce(n.asset_type, '') + ' ' + coalesce(n.attributes_json, ''))}}) AS nodes,
               collect(DISTINCT CASE WHEN r IS NULL THEN null ELSE {data: {id: r.asset_id, source: n.asset_id, target: m.asset_id, label: type(r), confidence: r.confidence, search_text: toLower(type(r) + ' ' + coalesce(r.properties_json, ''))}} END) AS edges
        """
        try:
            async with self._driver() as driver:
                records, _, _ = await driver.execute_query(query, project_id=project_id, database_=self.database)
            if not records:
                return {"nodes": [], "edges": []}
            return {"nodes": list(records[0]["nodes"]), "edges": [edge for edge in records[0]["edges"] if edge is not None]}
        except GraphStoreNotConfigured:
            raise
        except Exception as error:
            raise GraphStoreError("Neo4j graph retrieval failed") from error

    async def get_node(self, project_id: str, node_id: str) -> dict[str, object] | None:
        query = """
        MATCH (n:KnowledgeAsset {project_id: $project_id, asset_id: $node_id})
        OPTIONAL MATCH (n)-[r]-(other:KnowledgeAsset {project_id: $project_id})
        RETURN properties(n) AS node, labels(n) AS labels,
               collect(CASE WHEN r IS NULL THEN null ELSE {
                   id: r.asset_id,
                   type: type(r),
                   direction: CASE WHEN startNode(r) = n THEN 'outgoing' ELSE 'incoming' END,
                   other_node_id: other.asset_id,
                   other_node_label: other.name,
                   confidence: r.confidence
               } END) AS relationships
        """
        try:
            async with self._driver() as driver:
                records, _, _ = await driver.execute_query(query, project_id=project_id, node_id=node_id, database_=self.database)
            if not records:
                return None
            serialized_node = self._serialize_neo4j(dict(records[0]["node"]))
            raw = dict(serialized_node) if isinstance(serialized_node, dict) else {}
            evidence = self._parse_json_list(raw.pop("evidence_json", "[]"))
            attributes = self._parse_json_object(raw.pop("attributes_json", "{}"))
            relationships = [
                dict(serialized)
                for item in records[0]["relationships"]
                if item is not None and isinstance((serialized := self._serialize_neo4j(dict(item))), dict)
            ]
            sources = list(raw.get("source_names") or [])
            description = raw.get("definition") or attributes.get("description")
            return {
                "id": str(raw.get("asset_id", node_id)),
                "name": str(raw.get("name", node_id)),
                "type": str(raw.get("asset_type", "Other")),
                "labels": [label for label in records[0]["labels"] if label != "KnowledgeAsset"],
                "confidence": raw.get("confidence"),
                "description": str(description) if description is not None else None,
                "sources": sources,
                "properties": {**raw, **attributes},
                "evidence": evidence,
                "relationships": relationships,
            }
        except GraphStoreNotConfigured:
            raise
        except Exception as error:
            raise GraphStoreError("Neo4j node retrieval failed") from error

    async def query(self, project_id: str, cypher: str, parameters: dict[str, object] | None = None) -> list[dict[str, object]]:
        try:
            async with self._driver() as driver:
                records, _, _ = await driver.execute_query(cypher, parameters_=parameters or {"project_id": project_id}, database_=self.database)
            return [{key: self._serialize_neo4j(value) for key, value in record.items()} for record in records[:200]]
        except GraphStoreNotConfigured:
            raise
        except Exception as error:
            raise GraphStoreError("Neo4j read-only query failed") from error

    @staticmethod
    def _node_row(package: KnowledgeAssetPackage, asset_id: str, properties: dict[str, object]) -> dict[str, object]:
        return {"project_id": package.project_id, "package_id": package.package_id, "asset_id": asset_id, "properties": properties}

    @staticmethod
    def _evidence_json(evidence) -> str:
        return json.dumps([item.model_dump(mode="json") for item in evidence], sort_keys=True)

    @staticmethod
    def _parse_json_list(value: object) -> list[dict[str, object]]:
        try:
            parsed = json.loads(str(value))
            return [dict(item) for item in parsed if isinstance(item, dict)] if isinstance(parsed, list) else []
        except (TypeError, ValueError):
            return []

    @staticmethod
    def _parse_json_object(value: object) -> dict[str, object]:
        try:
            parsed = json.loads(str(value))
            return dict(parsed) if isinstance(parsed, dict) else {}
        except (TypeError, ValueError):
            return {}

    @classmethod
    def _serialize_neo4j(cls, value: object) -> object:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        if isinstance(value, Node):
            return {"id": value.get("asset_id"), "labels": sorted(value.labels), "properties": {key: cls._serialize_neo4j(item) for key, item in value.items()}}
        if isinstance(value, Relationship):
            return {"id": value.get("asset_id"), "type": value.type, "properties": {key: cls._serialize_neo4j(item) for key, item in value.items()}}
        if isinstance(value, Path):
            return {"nodes": [cls._serialize_neo4j(node) for node in value.nodes], "relationships": [cls._serialize_neo4j(item) for item in value.relationships]}
        if isinstance(value, dict):
            return {str(key): cls._serialize_neo4j(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [cls._serialize_neo4j(item) for item in value]
        return str(value)
