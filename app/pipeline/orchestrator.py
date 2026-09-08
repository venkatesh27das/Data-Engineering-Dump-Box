import logging

import openpyxl

from app.config.settings import Settings
from app.graph.dependency_graph import build_graph
from app.models.run import Run, Stage, WarningRecord
from app.models.workbook import Workbook
from app.pipeline.detect_regions import detect_regions
from app.pipeline.enrich import enrich_visuals, review_regions
from app.pipeline.extract_charts import extract_charts
from app.pipeline.extract_images import extract_images
from app.pipeline.extract_tables import extract_inferred_table, extract_tables
from app.pipeline.extract_text import extract_text
from app.pipeline.inspect_workbook import inspect_workbook
from app.pipeline.normalize import normalize
from app.pipeline.parse_formulas import extract_formulas
from app.pipeline.quality import assess_quality
from app.pipeline.retrieval import embed_assets, make_summaries
from app.storage.graph_store import save_graph
from app.storage.metadata_store import MetadataStore
from app.storage.structured_store import StructuredStore

logger = logging.getLogger(__name__)


def process(workbook: Workbook, run: Run, settings: Settings, metadata: MetadataStore, on_stage=None) -> Run:
    output = settings.output_dir / run.run_id
    output.mkdir(exist_ok=False)
    run.output_path = str(output)
    for directory in ("metadata", "tables", "text", "formulas", "graph", "images", "renders", "quality"):
        (output / directory).mkdir()
    formula_wb = value_wb = None

    def stage(value):
        run.stage = workbook.processing_status = value
        metadata.save_run(run)
        if on_stage:
            on_stage(value)
        metadata.save_workbook(workbook)
        logger.info(
            "processing_stage",
            extra={"run_id": run.run_id, "workbook_id": workbook.workbook_id, "stage": value},
        )

    try:
        stage(Stage.INSPECTING)
        formula_wb = openpyxl.load_workbook(workbook.file_path, data_only=False, keep_links=False)
        value_wb = openpyxl.load_workbook(workbook.file_path, data_only=True, keep_links=False)
        sheets = inspect_workbook(formula_wb, workbook, settings.max_sheet_cells)
        warnings = [
            WarningRecord(code=code, message="Detected during OOXML inventory; not executed")
            for code in workbook.unsupported_features
        ]
        stage(Stage.DETECTING_REGIONS)
        regions = [
            r
            for sheet in sheets
            for r in detect_regions(
                formula_wb[sheet.name],
                sheet,
                run.run_id,
                settings.region_agent_threshold,
                settings.max_regions_per_sheet,
            )
        ]
        stage(Stage.EXTRACTING_TABLES)
        tables = []
        for sheet in sheets:
            assets, _native_regions, _ = extract_tables(
                formula_wb[sheet.name], value_wb[sheet.name], sheet, output
            )
            tables.extend(assets)
            for region in [
                r
                for r in regions
                if r.sheet_id == sheet.sheet_id
                and r.detected_by != "native_excel_table"
                and r.region_type in {"table", "summary_table"}
            ]:
                try:
                    tables.append(
                        extract_inferred_table(
                            formula_wb[sheet.name], value_wb[sheet.name], sheet, region, output
                        )
                    )
                except Exception as exc:
                    logger.exception(
                        "inferred_table_failed",
                        extra={"sheet_name": sheet.name, "region_id": region.region_id},
                    )
                    region.requires_agent_review = True
                    warnings.append(
                        WarningRecord(
                            code="TABLE_EXTRACTION_FAILED", message=type(exc).__name__, sheet_name=sheet.name
                        )
                    )
            for asset in assets:
                warnings.extend(
                    WarningRecord(code=w.split(":")[0], message=w, sheet_name=sheet.name)
                    for w in asset.warnings
                )
        stage(Stage.EXTRACTING_TEXT)
        texts = [
            asset
            for sheet in sheets
            for asset in extract_text(
                formula_wb[sheet.name], sheet, [r for r in regions if r.sheet_id == sheet.sheet_id]
            )
        ]
        stage(Stage.EXTRACTING_VISUALS)
        images, charts = [], []
        for sheet in sheets:
            found_images, image_regions, image_warnings = extract_images(
                formula_wb[sheet.name], sheet, output
            )
            found_charts, chart_regions, chart_warnings = extract_charts(
                formula_wb[sheet.name], sheet, run.run_id
            )
            images.extend(found_images)
            charts.extend(found_charts)
            regions.extend(image_regions + chart_regions)
            warnings.extend(image_warnings + chart_warnings)
            sheet.region_count = sum(r.sheet_id == sheet.sheet_id for r in regions)
        stage(Stage.PARSING_FORMULAS)
        formulas = extract_formulas(formula_wb, value_wb, sheets)
        sheet_names = {s.sheet_id: s.name for s in sheets}
        for formula in formulas:
            warnings.extend(
                WarningRecord(
                    code=issue,
                    message="Formula dependencies may be incomplete",
                    sheet_name=sheet_names[formula.sheet_id],
                    cell=formula.cell,
                )
                for issue in formula.issues
            )
            if formula.cached_value is None:
                warnings.append(
                    WarningRecord(
                        code="MISSING_FORMULA_CACHE",
                        message="Formula preserved; not evaluated",
                        sheet_name=sheet_names[formula.sheet_id],
                        cell=formula.cell,
                    )
                )
        stage(Stage.AGENT_REVIEW)
        review_regions(regions, sheets, formula_wb, value_wb, settings, warnings)
        for sheet in sheets:
            for region in [
                r for r in regions if r.sheet_id == sheet.sheet_id and r.detected_by == "workbook_agent"
            ]:
                for table in [t for t in tables if t.region_id == region.region_id]:
                    (output / table.parquet_path).unlink(missing_ok=True)
                tables = [t for t in tables if t.region_id != region.region_id]
                if region.region_type in {"table", "summary_table", "kpi_block"}:
                    try:
                        tables.append(
                            extract_inferred_table(
                                formula_wb[sheet.name], value_wb[sheet.name], sheet, region, output
                            )
                        )
                    except Exception:
                        logger.exception(
                            "agent_table_extraction_failed", extra={"region_id": region.region_id}
                        )
                        region.requires_agent_review = True
                        warnings.append(
                            WarningRecord(
                                code="TABLE_EXTRACTION_FAILED",
                                message="Agent-classified table could not be extracted",
                            )
                        )
            sheet.table_count = sum(t.sheet_id == sheet.sheet_id for t in tables)
        texts = [
            asset
            for sheet in sheets
            for asset in extract_text(
                formula_wb[sheet.name], sheet, [r for r in regions if r.sheet_id == sheet.sheet_id]
            )
        ]
        texts.extend(enrich_visuals(regions, sheets, images, workbook, output, settings, warnings))
        summaries = make_summaries(workbook, sheets, tables, regions, formulas, settings, warnings)
        texts.extend(summaries)
        stage(Stage.EMBEDDING)
        embed_assets(texts, workbook, sheets, settings, warnings)
        for region in regions:
            if region.requires_agent_review:
                warnings.append(
                    WarningRecord(
                        code="LOW_CONFIDENCE_REGION",
                        message=f"Review region {region.range}",
                        sheet_name=sheet_names[region.sheet_id],
                    )
                )
        stage(Stage.QUALITY_CHECK)
        quality = assess_quality(regions, tables, formulas, images, charts, workbook, warnings)
        workbook.overall_quality_score = quality["overall_quality_score"]
        workbook.table_count = len(tables)
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
            summaries=summaries,
        )
        metadata.save_regions(workbook.workbook_id, run.run_id, regions)
        stage(run.stage)
    except Exception as exc:
        run.error = f"{type(exc).__name__}: {exc}"
        stage(Stage.FAILED)
        # Preserve successful intermediate assets for diagnosis.
        from app.pipeline.normalize import write_json

        write_json(output / "failure.json", {"run_id": run.run_id, "error": run.error})
        logger.exception(
            "processing_failed",
            extra={"run_id": run.run_id, "stage": run.stage, "workbook_id": workbook.workbook_id},
        )
    finally:
        for wb in (formula_wb, value_wb):
            if wb is not None:
                wb.close()
    return run
