import json
from pathlib import Path

import pytest

from app.config import Settings
from app.domain.projects import ProjectCreate
from app.repositories.projects import ProjectRepository
from app.services.demo_reset import DemoResetSafetyError, build_reset_plan, reset_local_demo
from app.services.uploads import ALLOWED_EXTENSIONS
from app.storage.database import Database


def test_reset_removes_local_state_and_preserves_placeholders(tmp_path: Path) -> None:
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'app.db'}",
        upload_dir=str(tmp_path / "uploads"),
        artifact_dir=str(tmp_path / "artifacts"),
    )
    database = Database(settings.sqlite_path)
    project = ProjectRepository(database).create(ProjectCreate(name="Demo", knowledge_objective="Test reset behavior"))
    settings.upload_path.mkdir()
    settings.artifact_path.mkdir()
    upload = settings.upload_path / "project-1" / "source.sql"
    upload.parent.mkdir()
    upload.write_text("CREATE TABLE demo (id INT);", encoding="utf-8")
    artifact = settings.artifact_path / "project-1" / "package.json"
    artifact.parent.mkdir()
    artifact.write_text("{}", encoding="utf-8")
    placeholder = settings.artifact_path / ".gitkeep"
    placeholder.write_text("", encoding="utf-8")

    plan = build_reset_plan(settings, database)
    assert plan.table_counts["projects"] == 1
    assert set(plan.files) == {upload.resolve(), artifact.resolve()}

    applied = reset_local_demo(settings, database)
    assert applied.record_count == 1
    assert not upload.exists() and not artifact.exists()
    assert placeholder.exists() and settings.sqlite_path.exists()
    assert ProjectRepository(database).get(project.id) is None


def test_reset_refuses_symlinks(tmp_path: Path) -> None:
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'app.db'}",
        upload_dir=str(tmp_path / "uploads"),
        artifact_dir=str(tmp_path / "artifacts"),
    )
    settings.upload_path.mkdir()
    settings.artifact_path.mkdir()
    target = tmp_path / "outside.txt"
    target.write_text("keep", encoding="utf-8")
    (settings.upload_path / "unsafe-link").symlink_to(target)

    with pytest.raises(DemoResetSafetyError, match="symlink"):
        build_reset_plan(settings)
    assert target.read_text(encoding="utf-8") == "keep"


def test_demo_fixture_manifest_is_complete_and_uploadable() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    fixture_root = repository_root / "test" / "knowledge_graph_test_pack"
    manifest = json.loads((fixture_root / "test_manifest.json").read_text(encoding="utf-8"))
    fixture_names = manifest["structured_files"] + manifest["unstructured_files"]

    assert manifest["recommended_mode"] == "Hybrid"
    assert manifest["recommended_graph_depth"] == "Contextual Knowledge"
    assert fixture_names
    for filename in fixture_names:
        fixture = fixture_root / filename
        assert fixture.is_file(), filename
        assert fixture.suffix.lower() in ALLOWED_EXTENSIONS, filename
