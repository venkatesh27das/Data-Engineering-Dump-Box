from datetime import UTC, datetime
from pathlib import Path

import pytest
from pypdf import PdfWriter

from app.agents.supervisor import SupervisorPlanner, specialist_profiles
from app.config import Settings
from app.domain.extraction import ConceptDiscoveryResponse, EntityExtractionResponse, RelationshipExtractionResponse
from app.domain.projects import GraphDepth, ProjectCreate, SourceAsset, SourceCategory
from app.providers.base import ChatMessage, ChatResponse, ModelProvider, StructuredModel
from app.repositories.projects import ProjectRepository, SourceRepository
from app.repositories.runs import AssetPackageRepository, RunArtifactRepository, RunRepository
from app.orchestration import RunOrchestrator
from app.storage.database import Database


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class OrchestrationProvider(ModelProvider):
    def __init__(self, source_id: str, source_name: str) -> None:
        self.source_id = source_id
        self.source_name = source_name
        self.max_tokens_seen: list[int | None] = []

    async def chat(self, messages: list[ChatMessage], *, model: str | None = None, temperature: float = 0.2, max_tokens: int | None = None) -> ChatResponse:
        raise NotImplementedError

    async def structured_generate(self, messages: list[ChatMessage], response_model: type[StructuredModel], *, model: str | None = None, temperature: float = 0.1, max_tokens: int | None = None) -> StructuredModel:
        self.max_tokens_seen.append(max_tokens)
        evidence = [{"source_id": self.source_id, "source_name": self.source_name, "page": 1 if self.source_name.endswith(".pdf") else None}]
        payloads: dict[str, dict[str, object]] = {
            ConceptDiscoveryResponse.__name__: {"concepts": [{"id": "CON-1", "name": "Supplier", "definition": "A supplier", "confidence": 0.9, "evidence": evidence}]},
            EntityExtractionResponse.__name__: {"entities": [
                {"id": "ENT-1", "canonical_name": "ACME Corporation", "entity_type": "Supplier", "confidence": 0.96, "evidence": evidence},
                {"id": "ENT-2", "canonical_name": "Contract 1032", "entity_type": "Contract", "confidence": 0.93, "evidence": evidence},
            ]},
            RelationshipExtractionResponse.__name__: {"relationships": [{"id": "REL-1", "source_entity_id": "ENT-1", "target_entity_id": "ENT-2", "relationship_type": "HAS_CONTRACT", "confidence": 0.92, "evidence": evidence}]},
        }
        return response_model.model_validate(payloads[response_model.__name__])

    async def embed(self, texts: list[str], *, model: str | None = None) -> list[list[float]]:
        return [[0.0] for _ in texts]

    async def health_check(self) -> bool:
        return True


class EmptyOrchestrationProvider(OrchestrationProvider):
    async def structured_generate(self, messages: list[ChatMessage], response_model: type[StructuredModel], *, model: str | None = None, temperature: float = 0.1, max_tokens: int | None = None) -> StructuredModel:
        self.max_tokens_seen.append(max_tokens)
        return response_model.model_validate({})


def _settings(tmp_path: Path) -> Settings:
    return Settings(database_url=f"sqlite:///{tmp_path / 'app.db'}", upload_dir=str(tmp_path / "uploads"), artifact_dir=str(tmp_path / "artifacts"))


def _project(database: Database):
    return ProjectRepository(database).create(ProjectCreate(name="Test Graph", knowledge_objective="Understand suppliers and contracts", graph_depth=GraphDepth.ENTITY_RELATIONSHIPS))


def _source(project_id: str, path: Path, source_id: str = "SRC-1") -> SourceAsset:
    category = SourceCategory.STRUCTURED if path.suffix == ".sql" else SourceCategory.UNSTRUCTURED
    return SourceAsset(id=source_id, project_id=project_id, filename=path.name, original_filename=path.name, category=category, extension=path.suffix, mime_type="application/octet-stream", size_bytes=path.stat().st_size, storage_path=str(path), created_at=datetime.now(UTC))


@pytest.mark.anyio
async def test_modality_changes_planned_parser_tools(tmp_path: Path) -> None:
    database = Database(tmp_path / "plan.db")
    project = _project(database)
    sql_path = tmp_path / "schema.sql"
    sql_path.write_text("CREATE TABLE suppliers (id INT);", encoding="utf-8")
    pdf_path = tmp_path / "document.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    with pdf_path.open("wb") as output:
        writer.write(output)
    planner = SupervisorPlanner(OrchestrationProvider("SRC-1", "schema.sql"))
    structured = await planner.plan(project, [_source(project.id, sql_path)])
    unstructured = await planner.plan(project, [_source(project.id, pdf_path)])
    assert "parse_ddl" in {step.tool for step in structured.steps}
    assert "parse_pdf" in {step.tool for step in unstructured.steps}
    assert {profile["name"] for profile in specialist_profiles()} == {"source-analyst", "knowledge-engineer", "graph-modeller", "quality-reviewer"}


@pytest.mark.anyio
async def test_run_completes_and_persists_package(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    database = Database(settings.sqlite_path)
    project = _project(database)
    path = tmp_path / "supplier_schema.sql"
    path.write_text("CREATE TABLE suppliers (supplier_id INT PRIMARY KEY);", encoding="utf-8")
    source = SourceRepository(database).create(_source(project.id, path))
    run = RunRepository(database).create(project.id)
    provider = OrchestrationProvider(source.id, source.filename)
    await RunOrchestrator(database=database, settings=settings, provider=provider).execute(run_id=run.id, project=project, sources=[source])
    completed = RunRepository(database).get(project.id, run.id)
    assert completed and completed.status.value == "completed"
    package = AssetPackageRepository(database, settings.artifact_path).load_latest(project.id)
    assert package and len(package.entities) == 2 and len(package.relationships) == 1
    assert any(event.title == "Graph assets generated" for event in RunRepository(database).list_events(run.id))
    artifacts = RunArtifactRepository(database).list_for_run(run.id)
    assert {artifact.artifact_type for artifact in artifacts} >= {
        "normalized_source", "entities", "relationships", "graph_schema", "quality_report", "asset_package",
    }
    assert any(artifact.parent_ids for artifact in artifacts if artifact.artifact_type != "normalized_source")
    assert provider.max_tokens_seen == [project.max_tokens] * 3


@pytest.mark.anyio
async def test_low_quality_document_triggers_observable_replan(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    database = Database(settings.sqlite_path)
    project = _project(database)
    path = tmp_path / "scan.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    with path.open("wb") as output:
        writer.write(output)
    source = SourceRepository(database).create(_source(project.id, path))
    run = RunRepository(database).create(project.id)
    await RunOrchestrator(database=database, settings=settings, provider=OrchestrationProvider(source.id, source.filename)).execute(run_id=run.id, project=project, sources=[source])
    events = RunRepository(database).list_events(run.id)
    assert any(event.event_type == "replan" for event in events)
    assert sum(event.title == "Analyzing sources" for event in events) == 2
    assert RunRepository(database).get(project.id, run.id).status.value == "completed"  # type: ignore[union-attr]


@pytest.mark.anyio
async def test_empty_quality_failure_does_not_publish_successful_package(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    database = Database(settings.sqlite_path)
    project = _project(database)
    path = tmp_path / "blank.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    with path.open("wb") as output:
        writer.write(output)
    source = SourceRepository(database).create(_source(project.id, path))
    run = RunRepository(database).create(project.id)

    await RunOrchestrator(
        database=database,
        settings=settings,
        provider=EmptyOrchestrationProvider(source.id, source.filename),
    ).execute(run_id=run.id, project=project, sources=[source])

    failed = RunRepository(database).get(project.id, run.id)
    events = RunRepository(database).list_events(run.id)
    assert failed and failed.status.value == "failed"
    assert failed.current_stage == "quality_failed"
    assert failed.error_message == "No knowledge assets were generated"
    assert AssetPackageRepository(database, settings.artifact_path).load_latest(project.id) is None
    assert any(event.title == "Quality review failed" for event in events)
    assert not any(event.title == "Graph assets generated" for event in events)
