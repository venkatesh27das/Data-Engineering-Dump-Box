import logging

import openpyxl

from app.config.settings import Settings
from app.graph.dependency_graph import build_graph
from app.models.run import Run, Stage, WarningRecord
from app.models.workbook import Workbook
from app.pipeline.extract_tables import extract_tables
from app.pipeline.inspect_workbook import inspect_workbook
from app.pipeline.normalize import normalize
from app.pipeline.parse_formulas import extract_formulas
from app.storage.graph_store import save_graph
from app.storage.metadata_store import MetadataStore
from app.storage.structured_store import StructuredStore

logger = logging.getLogger(__name__)


def process(workbook: Workbook, run: Run, settings: Settings, metadata: MetadataStore) -> Run:
    output = settings.output_dir / run.run_id
    output.mkdir(exist_ok=False)
    run.output_path = str(output)
    for directory in ("metadata", "tables", "text", "formulas", "graph", "images", "renders", "quality"):
        (output / directory).mkdir()
    formula_wb = value_wb = None

    def stage(value):
        run.stage = workbook.processing_status = value
        metadata.save_run(run)
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
        stage(Stage.EXTRACTING_TABLES)
        tables, regions = [], []
        for sheet in sheets:
            assets, native_regions, _ = extract_tables(
                formula_wb[sheet.name], value_wb[sheet.name], sheet, output
            )
            tables.extend(assets)
            regions.extend(native_regions)
            for asset in assets:
                warnings.extend(
                    WarningRecord(code=w.split(":")[0], message=w, sheet_name=sheet.name)
                    for w in asset.warnings
                )
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
        stage(Stage.BUILDING_GRAPH)
        graph = save_graph(build_graph(workbook, sheets, regions, tables, formulas), output / "graph")
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
        )
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
