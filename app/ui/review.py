import json
from typing import get_args

import openpyxl
import streamlit as st

from app.models.region import Region, RegionType
from app.services.feedback_service import FeedbackRequest, FeedbackService, ReprocessRequest
from app.services.run_service import BusyError
from app.tools.workbook_tools import WorkbookTools


def show_enrichment(service, output, workbook, sheets, run_id):
    def read(relative):
        path = output / relative
        return json.loads(path.read_text()) if path.exists() else []

    regions = read("metadata/regions.json")
    if not regions:
        st.info("Reprocess this workbook to discover regions and enable review.")
        return
    names = {s["sheet_id"]: s["name"] for s in sheets}
    region_tab, visual_tab, review_tab = st.tabs(["Regions & text", "Images & charts", "Review & reprocess"])
    with region_tab:
        st.dataframe(
            [
                {
                    "sheet": names[r["sheet_id"]],
                    "range": r["range"],
                    "type": r["region_type"],
                    "confidence": r["confidence"],
                    "review required": r["requires_agent_review"],
                }
                for r in regions
            ],
            hide_index=True,
        )
        path = output / "text/text_assets.jsonl"
        texts = [json.loads(line) for line in path.read_text().splitlines()]
        if texts:
            options = {t["text_asset_id"]: t for t in texts}
            choice = st.selectbox(
                "Read extracted text",
                list(options),
                key=f"text_{run_id}",
                format_func=lambda key: (
                    f"{names.get(options[key]['sheet_id'], 'Workbook')} / {options[key]['content_type']} / {options[key]['source_range'] or ''}"
                ),
            )
            st.text(options[choice]["content"])
        st.download_button(
            "Download text records", path.read_bytes(), "text_assets.jsonl", key=f"texts_download_{run_id}"
        )
    with visual_tab:
        images, charts = read("metadata/images.json"), read("metadata/charts.json")
        if images:
            choice = st.selectbox(
                "Embedded image",
                range(len(images)),
                key=f"image_{run_id}",
                format_func=lambda i: f"{names[images[i]['sheet_id']]}!{images[i]['anchor']}",
            )
            image = images[choice]
            st.image(str(output / image["filename"]), caption=f"{image['width']} × {image['height']} pixels")
        if charts:
            st.dataframe(
                [
                    {
                        "sheet": names[c["sheet_id"]],
                        "title": c["title"],
                        "type": c["chart_type"],
                        "anchor": c["anchor"],
                        "ranges": ", ".join(c["referenced_ranges"]),
                    }
                    for c in charts
                ],
                hide_index=True,
            )
        if not images and not charts:
            st.info("No embedded images or charts found.")
    with review_tab:
        pending = [r for r in regions if r["requires_agent_review"]]
        st.caption(
            f"{len(pending)} regions require review. Corrections produce a new run and preserve the original results."
        )
        only_pending = st.checkbox(
            "Only show regions requiring review", value=bool(pending), key=f"pending_{run_id}"
        )
        candidates = pending if only_pending else regions
        if not candidates:
            st.success("No regions need review.")
            return
        choices = {r["region_id"]: r for r in candidates}
        chosen = st.selectbox(
            "Region to review",
            list(choices),
            key=f"region_{run_id}",
            format_func=lambda key: (
                f"{names[choices[key]['sheet_id']]}!{choices[key]['range']} · {choices[key]['region_type']}"
            ),
        )
        region = Region.model_validate(choices[chosen])
        st.write(f"Confidence: {region.confidence:.0%} · Review status: {region.agent_review_status}")
        st.write("Evidence: " + "; ".join(region.evidence))
        if region.agent_result:
            st.json(region.agent_result)
        with st.expander("Inspect region sample"):
            fw = vw = None
            try:
                fw = openpyxl.load_workbook(workbook["file_path"], data_only=False, keep_links=False)
                vw = openpyxl.load_workbook(workbook["file_path"], data_only=True, keep_links=False)
                sample = WorkbookTools(fw, vw, names[region.sheet_id], region, max_cells=50).inspect_range()
                st.json(sample)
            finally:
                if fw:
                    fw.close()
                if vw:
                    vw.close()
            if st.button("Render preview", key=f"render_{chosen}"):
                try:
                    pages = service.render_region(chosen)
                    if pages:
                        for page in pages:
                            st.image(str(page))
                    else:
                        st.info("The renderer did not produce a page for this region.")
                except (OSError, RuntimeError, ValueError) as exc:
                    st.error(str(exc))
        content = st.text_area("Feedback", max_chars=4000, key=f"feedback_{chosen}")
        expected = st.selectbox(
            "Expected region type",
            ["Keep current classification", *get_args(RegionType)],
            key=f"expected_{chosen}",
        )
        expected = None if expected == "Keep current classification" else expected
        use_agent = st.checkbox(
            "Ask the local workbook agent to review",
            key=f"agent_{chosen}",
            disabled=not (
                getattr(service.settings, "enable_agent", False)
                and getattr(service.settings, "llm_model", "")
            ),
        )
        if st.button("Save feedback", key=f"save_feedback_{chosen}"):
            FeedbackService(service.metadata).submit(
                chosen, FeedbackRequest(content=content, expected_region_type=expected)
            )
            st.success("Feedback saved.")
        if st.button("Reprocess Region", type="primary", key=f"reprocess_{chosen}"):
            try:
                with st.status("Reprocessing selected region…") as status:
                    run = service.reprocess(
                        chosen,
                        ReprocessRequest(content=content, expected_region_type=expected, use_agent=use_agent),
                        on_stage=lambda stage: status.update(label=stage.replace("_", " ").title()),
                    )
                st.session_state["result_run_id"] = run.run_id
                st.rerun()
            except BusyError as exc:
                st.error(str(exc))

    if service.settings.enable_embeddings and service.settings.embedding_model:
        st.subheader("Semantic search")
        query = st.text_input(
            "Search extracted workbook content", max_chars=2000, key=f"search_{run_id}"
        )
        if st.button("Search", disabled=not query.strip(), key=f"search_button_{run_id}"):
            try:
                results = service.search(query, limit=10, run_id=run_id)
                if results:
                    st.dataframe(results, hide_index=True)
                else:
                    st.info("No matching embedded content was found for this run.")
            except (ValueError, RuntimeError) as exc:
                st.error(str(exc))
