import logging
from datetime import UTC, datetime
from typing import TypedDict
from uuid import uuid4

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph

from app.agents.supervisor import SupervisorPlanner
from app.config import Settings
from app.domain.assets import (
    Concept, Entity, Event, Fact, GraphSchema, KnowledgeAssetPackage, QualityDisposition, QualityReport,
    Relationship, SemanticMapping,
)
from app.domain.normalized import NormalizedSource
from app.domain.projects import GraphDepth, Project, SourceAsset
from app.domain.runs import ExecutionPlan, RunStatus
from app.providers.base import ModelProvider
from app.repositories.runs import AssetPackageRepository, RunArtifactRepository, RunRepository
from app.services.source_parser import SourceParser
from app.storage.database import Database
from app.tools.graph import build_graph_schema
from app.tools.knowledge import discover_concepts, extract_entities, extract_events, extract_facts, extract_relationships, map_semantics, resolve_entities
from app.tools.quality import score_assets

logger = logging.getLogger(__name__)


class OrchestrationState(TypedDict, total=False):
    plan: dict[str, object]
    normalized_sources: list[dict[str, object]]
    entities: list[dict[str, object]]
    relationships: list[dict[str, object]]
    concepts: list[dict[str, object]]
    facts: list[dict[str, object]]
    events: list[dict[str, object]]
    semantic_mappings: list[dict[str, object]]
    graph_schema: dict[str, object]
    quality_report: dict[str, object]
    package: dict[str, object]
    retry_count: int
    replan_reason: str
    ambiguous_count: int
    artifact_ids: dict[str, list[str]]


class RunOrchestrator:
    def __init__(self, *, database: Database, settings: Settings, provider: ModelProvider) -> None:
        self.database = database
        self.settings = settings
        self.provider = provider
        self.runs = RunRepository(database)
        self.artifacts = RunArtifactRepository(database)
        self.packages = AssetPackageRepository(database, settings.artifact_path)

    async def execute(self, *, run_id: str, project: Project, sources: list[SourceAsset]) -> None:
        self.runs.update(run_id, status=RunStatus.RUNNING, current_stage="planning", started=True)
        self._event(run_id, "planning", "running", "Planning knowledge construction", "Inspecting the objective and available source modalities", "run")
        try:
            graph = self._build_graph(run_id, project, sources)
            self.settings.artifact_path.mkdir(parents=True, exist_ok=True)
            checkpoint_path = self.settings.artifact_path / "langgraph-checkpoints.db"
            async with AsyncSqliteSaver.from_conn_string(str(checkpoint_path)) as checkpointer:
                await checkpointer.setup()
                compiled = graph.compile(checkpointer=checkpointer)
                await compiled.ainvoke({"retry_count": 0}, config={"configurable": {"thread_id": run_id}, "recursion_limit": 30})
        except Exception as error:
            logger.exception("Knowledge asset run %s failed", run_id)
            self.runs.update(run_id, status=RunStatus.FAILED, current_stage="failed", error_message=str(error), completed=True)
            self._event(run_id, "failed", "failed", "Generation failed", str(error), "run")

    def _build_graph(self, run_id: str, project: Project, sources: list[SourceAsset]) -> StateGraph:
        parser = SourceParser()

        async def planning(state: OrchestrationState) -> OrchestrationState:
            plan = await SupervisorPlanner(self.provider).plan(project, sources)
            self.runs.update(run_id, current_stage="source_analysis", plan=plan)
            self._event(run_id, "planning", "completed", "Plan created", f"Selected {len(plan.steps)} specialist tool steps for {', '.join(plan.source_modalities)} sources", "stage")
            return {"plan": plan.model_dump(mode="json")}

        async def source_analysis(state: OrchestrationState) -> OrchestrationState:
            self._event(run_id, "source_analysis", "running", "Analyzing sources", f"Inspecting {len(sources)} uploaded sources", "stage")
            normalized: list[NormalizedSource] = []
            normalized_artifact_ids: list[str] = []
            low_quality: list[str] = []
            for source in sources:
                tool_name = next((step.tool for step in ExecutionPlan.model_validate(state["plan"]).steps if source.filename in step.reason), "source_parser")
                self._event(run_id, "source_analysis", "running", f"Using {tool_name}", source.filename, "tool")
                result = parser.parse(source)
                normalized.append(result)
                artifact = self.artifacts.add(
                    run_id,
                    stage="source_analysis",
                    artifact_type="normalized_source",
                    name=f"Normalized {source.filename}",
                    record_count=len(result.tables) or len(result.chunks) or len(result.pages),
                    parent_ids=[source.id],
                    metadata={
                        "source_id": source.id,
                        "source_name": source.filename,
                        "source_type": result.source_type,
                        "parsing_confidence": result.parsing_confidence,
                        "warning_count": len(result.warnings),
                    },
                    status="temporary",
                )
                normalized_artifact_ids.append(artifact.id)
                if result.parsing_confidence < 0.5:
                    low_quality.append(source.filename)
            reason = f"Low parsing confidence for {', '.join(low_quality)}" if low_quality else ""
            self._event(run_id, "source_analysis", "completed" if not low_quality else "warning", "Source analysis completed", f"Normalized {len(normalized)} sources" + (f"; {reason}" if reason else ""), "stage")
            artifact_ids = {**state.get("artifact_ids", {}), "normalized_sources": normalized_artifact_ids}
            return {
                "normalized_sources": [item.model_dump(mode="json") for item in normalized],
                "replan_reason": reason,
                "artifact_ids": artifact_ids,
            }

        async def knowledge_engineering(state: OrchestrationState) -> OrchestrationState:
            self.runs.update(run_id, current_stage="knowledge_engineering")
            normalized = [NormalizedSource.model_validate(item) for item in state["normalized_sources"]]
            objective = project.knowledge_objective
            self._event(run_id, "knowledge_engineering", "running", "Discovering concepts", "Knowledge Engineer is extracting schema-constrained assets", "stage")
            concepts = await discover_concepts(self.provider, normalized, objective, max_tokens=project.max_tokens)
            entities = await extract_entities(self.provider, normalized, objective, max_tokens=project.max_tokens)
            resolution = resolve_entities(entities)
            relationships: list[Relationship] = []
            semantic_mappings: list[SemanticMapping] = []
            facts: list[Fact] = []
            events: list[Event] = []
            if project.graph_depth != GraphDepth.METADATA:
                relationships = await extract_relationships(
                    self.provider,
                    normalized,
                    objective,
                    resolution.entities,
                    max_tokens=project.max_tokens,
                )
            if project.graph_depth in {GraphDepth.SEMANTIC, GraphDepth.CONTEXTUAL}:
                semantic_mappings = await map_semantics(
                    self.provider,
                    normalized,
                    objective,
                    concepts,
                    max_tokens=project.max_tokens,
                )
            if project.graph_depth == GraphDepth.CONTEXTUAL:
                facts = await extract_facts(self.provider, normalized, objective, max_tokens=project.max_tokens)
                events = await extract_events(self.provider, normalized, objective, max_tokens=project.max_tokens)
            if resolution.ambiguous_matches:
                self._event(run_id, "entity_resolution", "warning", f"{len(resolution.ambiguous_matches)} ambiguous entities detected", "Additional evidence analysis may be required", "quality")
            self._event(run_id, "knowledge_engineering", "completed", "Knowledge extraction completed", f"Created {len(resolution.entities)} entities and {len(relationships)} relationships", "stage")
            parent_ids = state.get("artifact_ids", {}).get("normalized_sources", [])
            knowledge_artifacts: dict[str, list[str]] = {}
            for artifact_type, name, items in (
                ("concepts", "Discovered concepts", concepts),
                ("entities", "Extracted entities", resolution.entities),
                ("relationships", "Extracted relationships", relationships),
                ("semantic_mappings", "Mapped semantics", semantic_mappings),
                ("facts", "Extracted facts", facts),
                ("events", "Extracted events", events),
            ):
                artifact = self.artifacts.add(
                    run_id,
                    stage="knowledge_engineering",
                    artifact_type=artifact_type,
                    name=name,
                    record_count=len(items),
                    parent_ids=parent_ids,
                    status="temporary",
                )
                knowledge_artifacts[artifact_type] = [artifact.id]
            artifact_ids = {**state.get("artifact_ids", {}), **knowledge_artifacts}
            return {
                "entities": [item.model_dump(mode="json") for item in resolution.entities],
                "relationships": [item.model_dump(mode="json") for item in relationships],
                "concepts": [item.model_dump(mode="json") for item in concepts],
                "facts": [item.model_dump(mode="json") for item in facts],
                "events": [item.model_dump(mode="json") for item in events],
                "semantic_mappings": [item.model_dump(mode="json") for item in semantic_mappings],
                "ambiguous_count": len(resolution.ambiguous_matches),
                "artifact_ids": artifact_ids,
            }

        async def graph_modelling(state: OrchestrationState) -> OrchestrationState:
            self.runs.update(run_id, current_stage="graph_modelling")
            self._event(run_id, "graph_modelling", "running", "Modelling graph schema", "Graph Modeller is defining labels, relationship types and constraints", "stage")
            schema = build_graph_schema([Entity.model_validate(item) for item in state["entities"]], [Relationship.model_validate(item) for item in state["relationships"]])
            schema_artifact = self.artifacts.add(
                run_id,
                stage="graph_modelling",
                artifact_type="graph_schema",
                name="Modelled graph schema",
                record_count=len(schema.node_definitions) + len(schema.relationship_definitions),
                parent_ids=[
                    *state.get("artifact_ids", {}).get("entities", []),
                    *state.get("artifact_ids", {}).get("relationships", []),
                ],
                status="temporary",
            )
            self._event(run_id, "graph_modelling", "completed", "Graph schema completed", f"Defined {len(schema.node_definitions)} node types", "stage")
            artifact_ids = {**state.get("artifact_ids", {}), "graph_schema": [schema_artifact.id]}
            return {"graph_schema": schema.model_dump(mode="json"), "artifact_ids": artifact_ids}

        async def quality_review(state: OrchestrationState) -> OrchestrationState:
            self.runs.update(run_id, current_stage="quality_review")
            self._event(run_id, "quality_review", "running", "Validating assets", "Quality Reviewer is checking evidence, confidence and completeness", "stage")
            entities = [Entity.model_validate(item) for item in state["entities"]]
            relationships = [Relationship.model_validate(item) for item in state["relationships"]]
            concepts = [Concept.model_validate(item) for item in state["concepts"]]
            facts = [Fact.model_validate(item) for item in state["facts"]]
            events = [Event.model_validate(item) for item in state["events"]]
            mappings = [SemanticMapping.model_validate(item) for item in state["semantic_mappings"]]
            report = score_assets(entities=entities, relationships=relationships, concepts=concepts, facts=facts, events=events, semantic_mappings=mappings, ambiguous_entities=state.get("ambiguous_count", 0))
            if state.get("replan_reason") and state.get("retry_count", 0) == 0:
                report = report.model_copy(update={"disposition": QualityDisposition.REPLAN_REQUIRED})
            package = KnowledgeAssetPackage(package_id=str(uuid4()), project_id=project.id, sources=sources, entities=entities, relationships=relationships, concepts=concepts, facts=facts, events=events, semantic_mappings=mappings, graph_schema=GraphSchema.model_validate(state["graph_schema"]), quality_report=report, created_at=datetime.now(UTC))
            quality_parent_ids = [
                artifact_id
                for artifact_type in ("concepts", "entities", "relationships", "semantic_mappings", "facts", "events", "graph_schema")
                for artifact_id in state.get("artifact_ids", {}).get(artifact_type, [])
            ]
            quality_artifact = self.artifacts.add(
                run_id,
                stage="quality_review",
                artifact_type="quality_report",
                name="Quality review",
                record_count=len(report.issues),
                parent_ids=quality_parent_ids,
                metadata={"score": report.overall_score, "disposition": report.disposition.value},
                status="failed" if report.disposition == QualityDisposition.FAIL else "completed",
            )
            self._event(run_id, "quality_review", "completed", "Quality review completed", f"Overall quality {report.overall_score:.0%}: {report.disposition.value}", "quality")
            artifact_ids = {**state.get("artifact_ids", {}), "quality_report": [quality_artifact.id]}
            return {
                "quality_report": report.model_dump(mode="json"),
                "package": package.model_dump(mode="json"),
                "artifact_ids": artifact_ids,
            }

        async def replan(state: OrchestrationState) -> OrchestrationState:
            attempt = state.get("retry_count", 0) + 1
            self.runs.update(run_id, current_stage="replanning")
            self._event(run_id, "replanning", "warning", "Re-planning source analysis", state.get("replan_reason", "Quality validation requested another pass"), "replan")
            return {"retry_count": attempt}

        async def finalize(state: OrchestrationState) -> OrchestrationState:
            package = KnowledgeAssetPackage.model_validate(state["package"])
            summary = self.packages.save(package, run_id)
            self.artifacts.add(
                run_id,
                stage="completed",
                artifact_type="asset_package",
                name=f"Knowledge asset package {summary.package_id[:8]}",
                record_count=summary.entity_count + summary.relationship_count + summary.concept_count + summary.fact_count + summary.event_count,
                parent_ids=[
                    *state.get("artifact_ids", {}).get("quality_report", []),
                    *state.get("artifact_ids", {}).get("graph_schema", []),
                ],
                metadata={"package_id": summary.package_id, "quality_score": summary.quality_score},
            )
            self.runs.update(run_id, status=RunStatus.COMPLETED, current_stage="completed", package_id=summary.package_id, completed=True)
            self._event(run_id, "completed", "completed", "Graph assets generated", f"Created {summary.entity_count} entities and {summary.relationship_count} relationships", "run")
            return {}

        async def fail_quality(state: OrchestrationState) -> OrchestrationState:
            report = QualityReport.model_validate(state["quality_report"])
            issue_messages = [issue.message for issue in report.issues if issue.severity == "error"]
            message = "; ".join(issue_messages) or "Generated assets did not pass quality validation"
            self.runs.update(
                run_id,
                status=RunStatus.FAILED,
                current_stage="quality_failed",
                error_message=message,
                completed=True,
            )
            self._event(run_id, "quality_review", "failed", "Quality review failed", message, "quality")
            return {}

        def quality_route(state: OrchestrationState) -> str:
            if state.get("replan_reason") and state.get("retry_count", 0) == 0:
                return "replan"
            report = QualityReport.model_validate(state["quality_report"])
            if report.disposition == QualityDisposition.FAIL:
                return "fail"
            return "complete"

        builder = StateGraph(OrchestrationState)
        builder.add_node("planning", planning)
        builder.add_node("source_analyst", source_analysis)
        builder.add_node("knowledge_engineer", knowledge_engineering)
        builder.add_node("graph_modeller", graph_modelling)
        builder.add_node("quality_reviewer", quality_review)
        builder.add_node("replan", replan)
        builder.add_node("finalize", finalize)
        builder.add_node("fail_quality", fail_quality)
        builder.add_edge(START, "planning")
        builder.add_edge("planning", "source_analyst")
        builder.add_edge("source_analyst", "knowledge_engineer")
        builder.add_edge("knowledge_engineer", "graph_modeller")
        builder.add_edge("graph_modeller", "quality_reviewer")
        builder.add_conditional_edges(
            "quality_reviewer",
            quality_route,
            {"replan": "replan", "fail": "fail_quality", "complete": "finalize"},
        )
        builder.add_edge("replan", "source_analyst")
        builder.add_edge("finalize", END)
        builder.add_edge("fail_quality", END)
        return builder

    def _event(self, run_id: str, stage: str, status: str, title: str, message: str, event_type: str) -> None:
        self.runs.add_event(run_id, stage=stage, status=status, title=title, message=message, event_type=event_type)
