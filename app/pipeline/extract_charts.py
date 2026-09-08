import logging

from app.models.assets import ChartAsset
from app.models.region import Region
from app.models.run import WarningRecord
from app.pipeline.extract_images import anchor_cell


def extract_charts(ws, sheet, run_id: str):
    assets, regions, warnings = [], [], []
    for index, chart in enumerate(ws._charts):
        identifier = f"{run_id}_{sheet.sheet_id}_chart{index}"
        try:
            xml = chart.to_tree()
            title = (
                " ".join(
                    n.text for n in chart.title.to_tree().iter() if n.tag.split("}")[-1] == "t" and n.text
                )
                if chart.title
                else None
            )
            refs = sorted({n.text for n in xml.iter() if n.tag.split("}")[-1] == "f" and n.text})
            anchor = anchor_cell(chart)
            region = Region(
                region_id=f"{identifier}_region",
                sheet_id=sheet.sheet_id,
                range=anchor,
                region_type="chart",
                detected_by="excel_chart",
            )
            assets.append(
                ChartAsset(
                    chart_id=identifier,
                    workbook_id=sheet.workbook_id,
                    sheet_id=sheet.sheet_id,
                    region_id=region.region_id,
                    anchor=anchor,
                    title=title,
                    chart_type=type(chart).__name__,
                    referenced_ranges=refs,
                )
            )
            regions.append(region)
        except Exception as exc:
            logging.getLogger(__name__).exception(
                "visual_extraction_failed", extra={"sheet_name": sheet.name}
            )
            warnings.append(
                WarningRecord(
                    code="CHART_EXTRACTION_FAILED", message=type(exc).__name__, sheet_name=sheet.name
                )
            )
    return assets, regions, warnings
