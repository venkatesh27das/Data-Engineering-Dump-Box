import logging

from deepagents import create_deep_agent

from app.domain.projects import GraphDepth, Project, SourceAsset
from app.domain.runs import ExecutionPlan, PlanStep
from app.providers.base import ModelProvider
from app.providers.lmstudio import LMStudioProvider

logger = logging.getLogger(__name__)


def specialist_profiles() -> list[dict[str, str]]:
    return [
        {
            "name": "source-analyst",
            "description": "Classifies structured and unstructured sources and recommends deterministic parsers or OCR.",
            "system_prompt": "Inspect source metadata and return concise modality-specific processing recommendations. Never execute uploaded SQL.",
        },
        {
            "name": "knowledge-engineer",
            "description": "Plans evidence-linked concept, entity, relationship, fact, event and semantic extraction.",
            "system_prompt": "Recommend only schema-constrained extraction tasks supported by supplied sources and preserve provenance.",
        },
        {
            "name": "graph-modeller",
            "description": "Plans graph labels, relationship types, properties and constraints without publishing data.",
            "system_prompt": "Produce graph modelling recommendations from typed candidate assets. Do not publish to Neo4j.",
        },
        {
            "name": "quality-reviewer",
            "description": "Plans evidence, confidence, duplicate, consistency and completeness validation.",
            "system_prompt": "Identify validation checks and conditions requiring review or re-planning. Do not expose hidden reasoning.",
        },
    ]


class SupervisorPlanner:
    def __init__(self, provider: ModelProvider) -> None:
        self.provider = provider

    async def plan(self, project: Project, sources: list[SourceAsset]) -> ExecutionPlan:
        fallback = self._deterministic_plan(project, sources)
        if not isinstance(self.provider, LMStudioProvider) or not (self.provider.orchestrator_model or self.provider.knowledge_model):
            return fallback
        try:
            agent = create_deep_agent(
                model=self.provider.as_langchain_chat_model("orchestrator"),
                system_prompt=(
                    "You are the Knowledge Asset Supervisor. Create an operational plan only; do not extract assets. "
                    "Delegate source, knowledge, graph and quality planning to the named subagents. Select only tools "
                    "appropriate for source modality and requested graph depth."
                ),
                subagents=specialist_profiles(),
                response_format=ExecutionPlan,
                name="knowledge-asset-supervisor",
            )
            prompt = (
                f"Objective: {project.knowledge_objective}\nMode: {project.processing_mode.value}\n"
                f"Graph depth: {project.graph_depth.value}\nSources: "
                + ", ".join(f"{source.filename} ({source.category.value})" for source in sources)
            )
            result = await agent.ainvoke({"messages": [{"role": "user", "content": prompt}]})
            structured = result.get("structured_response")
            if structured:
                return ExecutionPlan.model_validate(structured).model_copy(update={"plan_source": "deep_agent"})
        except Exception as error:
            logger.warning("Deep Agent planning failed; using deterministic fallback: %s", error)
        return fallback

    @staticmethod
    def _deterministic_plan(project: Project, sources: list[SourceAsset]) -> ExecutionPlan:
        modalities = sorted({source.category.value for source in sources})
        steps: list[PlanStep] = []
        parser_by_extension = {
            ".sql": "parse_ddl", ".json": "parse_schema_json", ".csv": "parse_schema_csv",
            ".pdf": "parse_pdf", ".docx": "parse_docx", ".png": "parse_image", ".jpg": "parse_image", ".jpeg": "parse_image",
        }
        for source in sources:
            steps.append(PlanStep(specialist="source_analyst", tool=parser_by_extension[source.extension], reason=f"Parse {source.filename} as {source.category.value} input"))
        steps.extend([
            PlanStep(specialist="knowledge_engineer", tool="discover_concepts", reason="Identify business vocabulary for the objective"),
            PlanStep(specialist="knowledge_engineer", tool="extract_entities", reason="Create canonical evidence-linked entities"),
        ])
        if project.graph_depth != GraphDepth.METADATA:
            steps.extend([
                PlanStep(specialist="knowledge_engineer", tool="resolve_entities", reason="Resolve duplicates and aliases deterministically"),
                PlanStep(specialist="knowledge_engineer", tool="extract_relationships", reason="Create evidence-linked graph relationships"),
            ])
        if project.graph_depth in {GraphDepth.SEMANTIC, GraphDepth.CONTEXTUAL}:
            steps.append(PlanStep(specialist="knowledge_engineer", tool="map_semantics", reason="Map source terms to discovered concepts"))
        if project.graph_depth == GraphDepth.CONTEXTUAL:
            steps.extend([
                PlanStep(specialist="knowledge_engineer", tool="extract_facts", reason="Extract contextual facts"),
                PlanStep(specialist="knowledge_engineer", tool="extract_events", reason="Extract supported temporal events"),
            ])
        steps.extend([
            PlanStep(specialist="graph_modeller", tool="build_graph_schema", reason="Create a graph-ready schema without publishing"),
            PlanStep(specialist="quality_reviewer", tool="score_assets", reason="Validate provenance, confidence and completeness"),
        ])
        levels = ["L0", "L1"]
        if project.graph_depth != GraphDepth.METADATA:
            levels.extend(["L2", "L3"])
        if project.graph_depth in {GraphDepth.SEMANTIC, GraphDepth.CONTEXTUAL}:
            levels.append("L4")
        if project.graph_depth == GraphDepth.CONTEXTUAL:
            levels.append("L5")
        return ExecutionPlan(source_modalities=modalities, graph_levels=levels, steps=steps)
