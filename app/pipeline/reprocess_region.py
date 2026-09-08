"""Re-extract only one region into a child run. Parent artifacts remain immutable."""

import hashlib
import json
import logging
import shutil

import openpyxl
from openpyxl.utils.cell import range_boundaries

from app.graph.dependency_graph import build_graph
from app.models.assets import ChartAsset, FormulaAsset, ImageAsset, TableAsset, TextAsset
from app.models.region import Region
from app.models.run import Stage, WarningRecord
from app.models.workbook import Sheet, Workbook
from app.pipeline.enrich import enrich_visuals
from app.pipeline.extract_tables import extract_inferred_table
from app.pipeline.extract_text import extract_text
from app.pipeline.normalize import normalize, write_json
from app.pipeline.quality import assess_quality
from app.pipeline.retrieval import embed_assets, make_summaries
from app.storage.graph_store import save_graph
from app.storage.structured_store import StructuredStore

logger = logging.getLogger(__name__)


def reprocess_region(workbook, run, parent, target_id, request, settings, metadata, on_stage=None):
    output = settings.output_dir / run.run_id
    source = settings.output_dir / parent.run_id
    formula_wb = value_wb = None

    def stage(value):
        run.stage = value
        metadata.save_run(run)
        if on_stage:
            on_stage(value)
        logger.info(
            "region_processing_stage", extra={"run_id": run.run_id, "region_id": target_id, "stage": value}
        )

    try:
        shutil.copytree(source, output)
        (output / "manifest.json").unlink(missing_ok=True)
        run.output_path = str(output)
        stage(Stage.INSPECTING)

        def read(relative):
            return json.loads((source / relative).read_text())

        # Load the parent's snapshot, not the latest workbook counters from another branch.
        workbook = Workbook.model_validate(read("metadata/workbook.json"))
        workbook.run_id = run.run_id
        sheets = [Sheet.model_validate(s) for s in read("metadata/sheets.json")]
        regions = [Region.model_validate(r) for r in read("metadata/regions.json")]
        tables = [TableAsset.model_validate(t) for t in read("metadata/table_assets.json")]
        images = [ImageAsset.model_validate(t) for t in read("metadata/images.json")]
        charts = [ChartAsset.model_validate(t) for t in read("metadata/charts.json")]
        texts = [
            TextAsset.model_validate_json(line)
            for line in (source / "text/text_assets.jsonl").read_text().splitlines()
        ]
        formulas = [
            FormulaAsset.model_validate_json(line)
            for line in (source / "formulas/formulas.jsonl").read_text().splitlines()
        ]
        target = next(r for r in regions if r.region_id == target_id)
        sheet = next(s for s in sheets if s.sheet_id == target.sheet_id)
        # Keep unrelated warnings; quality/review warnings are recomputed below.
        warnings = [
            WarningRecord.model_validate(w)
            for w in read("quality/quality_report.json")["warnings"]
            if w["code"] not in {"LOW_CONFIDENCE_REGION", "AGENT_UNAVAILABLE", "AGENT_REVIEW_FAILED"}
        ]
        formula_wb = openpyxl.load_workbook(workbook.file_path, data_only=False, keep_links=False)
        value_wb = openpyxl.load_workbook(workbook.file_path, data_only=True, keep_links=False)

        # Every child region gets a new identity so feedback and historical region URLs remain stable.
        def identifier(old):
            return "a_" + hashlib.sha256(f"{run.run_id}:{old}".encode()).hexdigest()[:24]

        region_ids = {r.region_id: identifier(r.region_id) for r in regions}
        for table in tables:
            if table.region_id == target_id:
                (output / table.parquet_path).unlink(missing_ok=True)
        tables = [t for t in tables if t.region_id != target_id]
        texts = [t for t in texts if t.region_id != target_id or t.content_type == "comments"]
        shutil.rmtree(output / "renders", ignore_errors=True)
        (output / "renders").mkdir()
        for region in regions:
            region.region_id = region_ids[region.region_id]
        for assets, id_field in (
            (tables, "table_id"),
            (texts, "text_asset_id"),
            (images, "image_id"),
            (charts, "chart_id"),
        ):
            for asset in assets:
                new_asset_id = identifier(getattr(asset, id_field))
                if isinstance(asset, TableAsset):
                    old_path = output / asset.parquet_path
                    asset.parquet_path = f"tables/{new_asset_id}.parquet"
                    old_path.rename(output / asset.parquet_path)
                elif isinstance(asset, ImageAsset):
                    old_path = output / asset.filename
                    asset.filename = f"images/{new_asset_id}{old_path.suffix}"
                    old_path.rename(output / asset.filename)
                setattr(asset, id_field, new_asset_id)
                if asset.region_id:
                    asset.region_id = region_ids[asset.region_id]
                if isinstance(asset, TableAsset):
                    asset.duckdb_table = f"table_{asset.table_id}"
        if request.expected_region_type:
            target.region_type = request.expected_region_type
            target.detected_by = "human_feedback"
            target.confidence = 1.0
            target.requires_agent_review = False
            target.agent_review_status = "human_reviewed"
            target.header_row = (
                range_boundaries(target.range)[1]
                if target.region_type in {"table", "summary_table"}
                else None
            )
        elif request.use_agent:
            stage(Stage.AGENT_REVIEW)
            from app.pipeline.enrich import review_region

            review_region(target, sheet.name, formula_wb, value_wb, settings, warnings, request.content)
        stage(Stage.EXTRACTING_TABLES)
        if target.region_type in {"table", "summary_table", "kpi_block"}:
            if target.region_type == "kpi_block":
                target.header_row = None
            tables.append(
                extract_inferred_table(formula_wb[sheet.name], value_wb[sheet.name], sheet, target, output)
            )
        stage(Stage.EXTRACTING_TEXT)
        # Comment records were preserved; avoid duplicating them on selected-region extraction.
        texts.extend(
            t for t in extract_text(formula_wb[sheet.name], sheet, [target]) if t.content_type != "comments"
        )
        texts = [
            t
            for t in texts
            if t.content_type not in {"sheet_summary", "workbook_summary", "table_description"}
        ]
        texts.extend(
            enrich_visuals(
                [target],
                sheets,
                [i for i in images if i.region_id == target.region_id],
                workbook,
                output,
                settings,
                warnings,
            )
        )
        summaries = make_summaries(workbook, sheets, tables, regions, formulas, settings, warnings)
        texts.extend(summaries)
        stage(Stage.EMBEDDING)
        embed_assets(texts, workbook, sheets, settings, warnings)
        for region in regions:
            if region.requires_agent_review:
                warnings.append(
                    WarningRecord(code="LOW_CONFIDENCE_REGION", message=f"Review region {region.range}")
                )
        for s in sheets:
            s.table_count = sum(t.sheet_id == s.sheet_id for t in tables)
        workbook.table_count = len(tables)
        stage(Stage.QUALITY_CHECK)
        quality = assess_quality(regions, tables, formulas, images, charts, workbook, warnings)
        workbook.overall_quality_score = quality["overall_quality_score"]
        stage(Stage.BUILDING_GRAPH)
        graph = save_graph(
            build_graph(workbook, sheets, regions, tables, formulas, texts, images, charts), output / "graph"
        )
        stage(Stage.NORMALIZING)
        run.stage = workbook.processing_status = (
            Stage.COMPLETED_WITH_WARNINGS if warnings else Stage.COMPLETED
        )
        normalize(
            output,
            run,
            workbook,
            sheets,
            regions,
            tables,
            formulas,
            graph,
            warnings,
            StructuredStore(settings.duckdb_path),
            texts=texts,
            images=images,
            charts=charts,
            quality=quality,
            feedback=metadata.feedback(target_id),
            summaries=summaries,
        )
        metadata.save_regions(workbook.workbook_id, run.run_id, regions)
        metadata.save_workbook(workbook)
        stage(run.stage)
    except Exception as exc:
        run.error = f"{type(exc).__name__}: {exc}"
        stage(Stage.FAILED)
        if output.exists():
            write_json(output / "failure.json", {"run_id": run.run_id, "error": run.error})
        logger.exception("region_reprocessing_failed", extra={"region_id": target_id, "run_id": run.run_id})
    finally:
        for wb in (formula_wb, value_wb):
            if wb is not None:
                wb.close()
    return run
