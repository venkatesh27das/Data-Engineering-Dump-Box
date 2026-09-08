"""Local upload and results UI over the deterministic core. No API server required."""

import json
import logging
import math
from pathlib import Path

import polars as pl
import streamlit as st

from app.config.settings import Settings
from app.models.run import Stage
from app.pipeline.ingest import InvalidWorkbook
from app.services.run_service import BusyError, RunService
from app.ui.review import show_enrichment

LOGGER = logging.getLogger(__name__)
SAMPLES_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures"


@st.cache_resource
def get_service() -> RunService:
    return RunService(Settings())


@st.cache_data(ttl=15, show_spinner=False)
def get_system_status() -> dict:
    return get_service().system_status()


def read_json(output: Path, relative: str):
    return json.loads((output / relative).read_text(encoding="utf-8"))


def show_results(service: RunService, run_id: str) -> None:
    run = service.metadata.run(run_id)
    if run.stage == Stage.FAILED:
        st.error("Processing failed. Try a different workbook or review the error below.")
        st.code(run.error or "Unknown processing error")
        return
    if run.stage not in (Stage.COMPLETED, Stage.COMPLETED_WITH_WARNINGS):
        st.info(f"Processing status: {run.stage}")
        return

    output = service.settings.output_dir / run.run_id
    workbook = read_json(output, "metadata/workbook.json")
    manifest = read_json(output, "manifest.json")
    sheets = read_json(output, "metadata/sheets.json")
    tables = read_json(output, "metadata/table_assets.json")
    st.divider()
    st.subheader("Workbook results")
    st.text(workbook["filename"])
    if run.stage == Stage.COMPLETED_WITH_WARNINGS:
        st.warning("Processing complete with warnings. Review the Warnings tab for details.")
    else:
        st.success("Processing complete.")
    metrics = st.columns(6)
    for column, label, value in zip(
        metrics,
        ("Sheets", "Tables", "Formulas", "Dependencies", "Images", "Charts"),
        (
            workbook["sheet_count"],
            len(tables),
            workbook["formula_count"],
            manifest["counts"]["dependencies"],
            workbook["image_count"],
            workbook["chart_count"],
        ),
    ):
        column.metric(label, value)

    quality = read_json(output, "quality/quality_report.json")
    quality_column, review_column = st.columns(2)
    score = workbook.get("overall_quality_score")
    quality_column.metric("Quality score", f"{score:.0%}" if score is not None else "Not assessed")
    review_column.metric("Review required", quality.get("review_required", 0))

    sheet_tab, table_tab, formula_tab, dependency_tab, warning_tab, download_tab = st.tabs(
        ["Sheets", "Tables", "Formulas", "Dependencies", "Warnings", "Downloads"]
    )
    names = {sheet["sheet_id"]: sheet["name"] for sheet in sheets}
    with sheet_tab:
        st.dataframe(
            [
                {
                    key: sheet[key]
                    for key in (
                        "name",
                        "visibility",
                        "max_row",
                        "max_column",
                        "non_empty_cells",
                        "table_count",
                        "formula_count",
                        "merged_range_count",
                    )
                }
                for sheet in sheets
            ],
            hide_index=True,
        )
        selected = st.selectbox("Inspect a sheet", list(names), format_func=names.get, key=f"sheet_{run_id}")
        sheet = next(s for s in sheets if s["sheet_id"] == selected)
        st.caption(f"Images: {sheet['image_count']} · Charts: {sheet['chart_count']}")
        for title, field in (
            ("Native tables", "native_tables"),
            ("Merged ranges", "merged_ranges"),
            ("Comments", "comments"),
            ("Hyperlinks", "hyperlinks"),
        ):
            with st.expander(title):
                if sheet[field]:
                    st.json(sheet[field])
                else:
                    st.caption("None found.")
    with table_tab:
        if not tables:
            st.info(
                "No tabular regions found. "
                "Inspect the detected regions and correct their classification in the review view."
            )
        else:
            choices = {t["table_id"]: t for t in tables}
            table_id = st.selectbox(
                "Preview a table",
                list(choices),
                format_func=lambda key: f"{names[choices[key]['sheet_id']]} / {choices[key]['table_name']}",
                key=f"table_{run_id}",
            )
            table = choices[table_id]
            st.caption(
                f"Source: {names[table['sheet_id']]}!{table['source_range']} · "
                f"{table['row_count']:,} rows · Preview limited to 100 rows"
            )
            path = output / table["parquet_path"]
            st.dataframe(pl.scan_parquet(path).head(100).collect(), hide_index=True)
            st.download_button(
                "Download table as Parquet",
                path.read_bytes(),
                path.name,
                mime="application/octet-stream",
                key=f"parquet_{run_id}_{table_id}",
            )
    with formula_tab:
        formulas = [
            json.loads(line) for line in (output / "formulas/formulas.jsonl").read_text().splitlines()
        ]
        if not formulas:
            st.info("No formulas found.")
        else:
            selected_sheet = st.selectbox(
                "Formula sheet", ["All sheets", *names.values()], key=f"formulas_{run_id}"
            )
            filtered = [
                f
                for f in formulas
                if selected_sheet == "All sheets" or names[f["sheet_id"]] == selected_sheet
            ]
            st.caption(
                "Formula expressions are preserved. Cached values are shown when available; formulas are not recalculated."
            )
            st.dataframe(
                [
                    {
                        "sheet": names[f["sheet_id"]],
                        "cell": f["cell"],
                        "formula": f["formula"],
                        "cached_value": None if f["cached_value"] is None else str(f["cached_value"]),
                        "references": ", ".join(f["referenced_cells"] + f["referenced_ranges"]),
                        "parse_status": f["parse_status"],
                    }
                    for f in filtered[:500]
                ],
                hide_index=True,
            )
            st.caption(
                f"Showing {min(len(filtered), 500)} of {len(filtered)} formulas. Download the full result below."
            )
    with dependency_tab:
        graph = read_json(output, "graph/dependency_graph.json")
        nodes = {n["id"]: n for n in graph["nodes"]}
        dependencies = [e for e in graph["edges"] if e["relationship"] == "DEPENDS_ON"]
        if not dependencies:
            st.info("No formula dependencies found.")
        else:

            def label(node_id: str) -> str:
                node = nodes[node_id]
                return f"{node['sheet']}!{node['address']}"

            st.caption(
                "Each formula depends on the input shown beside it. Ranges remain compact range references."
            )
            st.dataframe(
                [
                    {"formula cell": label(e["source"]), "depends on": label(e["target"])}
                    for e in dependencies[:500]
                ],
                hide_index=True,
            )
            st.caption(f"Showing {min(len(dependencies), 500)} of {len(dependencies)} dependencies.")
    with warning_tab:
        warnings = manifest["warnings"]
        if warnings:
            st.caption(f"{len(warnings)} warnings. Missing cached values are common in generated workbooks.")
            st.dataframe(warnings[:500], hide_index=True)
        else:
            st.success("No processing warnings.")
    with download_tab:
        for title, relative, mime in (
            ("Run manifest", "manifest.json", "application/json"),
            ("Formula records", "formulas/formulas.jsonl", "application/x-ndjson"),
            ("Dependency graph (JSON)", "graph/dependency_graph.json", "application/json"),
            ("Dependency graph (GraphML)", "graph/dependency_graph.graphml", "application/xml"),
        ):
            path = output / relative
            st.download_button(
                title, path.read_bytes(), path.name, mime=mime, key=f"download_{run_id}_{relative}"
            )
        st.caption("Local output folder")
        st.code(str(output))

    show_enrichment(service, output, workbook, sheets, run_id)


def main() -> None:
    st.set_page_config(page_title="Excel Intelligence", page_icon="📊", layout="wide")
    st.title("Excel Intelligence")
    st.write("Upload an Excel workbook to explore its sheets, tables, formulas, and dependencies.")
    service = get_service()
    with st.sidebar:
        st.subheader("Local workbook explorer")
        st.caption("Your workbook is processed and stored on this computer.")
        st.caption(
            "Native and inferred tables, text, visuals, and formula references are processed locally. Review ambiguous regions below the results."
        )
        status = get_system_status()
        st.write("LM Studio: " + ("connected" if status["lm_studio"]["available"] else "offline"))
        st.write(
            "LibreOffice: "
            + ("available" if status["libreoffice_available"] else "unavailable")
        )
        st.caption(
            "Agent: "
            + ("configured" if status["agent_configured"] else "not configured")
            + " · VLM: "
            + ("configured" if status["vlm_configured"] else "not configured")
            + " · Embeddings: "
            + ("configured" if status["embeddings_configured"] else "not configured")
        )
    source = st.radio("Choose a workbook", ["Upload Excel", "Try a sample"], horizontal=True)
    upload = None
    sample = None
    if source == "Upload Excel":
        upload = st.file_uploader(
            "Excel workbook",
            type=["xlsx"],
            key="workbook_upload",
            max_upload_size=max(1, math.ceil(service.settings.max_upload_mb)),
        )
        st.caption(f"Maximum file size: {service.settings.max_upload_mb:g} MB")
    else:
        samples = sorted(SAMPLES_DIR.glob("fixture_*.xlsx"))
        if samples:
            sample = st.selectbox(
                "Sample workbook",
                samples,
                format_func=lambda p: p.stem.replace("fixture_", "").replace("_", " ").title(),
            )
            st.download_button(
                "Download sample workbook",
                sample.read_bytes(),
                sample.name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        else:
            st.info("No sample workbooks are available yet. Upload your own Excel file to get started.")
    if st.button("Process workbook", type="primary", disabled=upload is None and sample is None):
        st.session_state.pop("result_run_id", None)
        try:
            with st.status("Processing workbook…", expanded=True) as status:
                st.write("Saving workbook and inspecting sheets, tables, and formulas…")
                if upload is not None:
                    upload.seek(0)
                    workbook = service.upload(upload, upload.name)
                else:
                    with sample.open("rb") as stream:
                        workbook = service.upload(stream, sample.name)
                run = service.process(
                    workbook.workbook_id,
                    on_stage=lambda stage: status.update(label=stage.replace("_", " ").title()),
                )
                st.session_state["result_run_id"] = run.run_id
                status.update(
                    label="Processing failed" if run.stage == Stage.FAILED else "Processing complete",
                    state="error" if run.stage == Stage.FAILED else "complete",
                    expanded=False,
                )
        except (InvalidWorkbook, BusyError) as exc:
            st.error(str(exc))
        except Exception:
            LOGGER.exception("ui_processing_failed")
            st.error("The workbook could not be processed. Check the application logs and try again.")
    if run_id := st.session_state.get("result_run_id"):
        try:
            show_results(service, run_id)
        except (KeyError, OSError, ValueError):
            LOGGER.exception("ui_results_unavailable")
            st.error("These results are no longer available. Process the workbook again.")
    else:
        st.info("Choose a workbook above, then click Process workbook to see the results here.")


if __name__ == "__main__":
    main()
