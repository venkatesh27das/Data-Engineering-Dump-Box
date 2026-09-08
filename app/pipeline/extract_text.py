from openpyxl.utils.cell import range_boundaries
from openpyxl.worksheet.worksheet import Worksheet

from app.models.assets import TextAsset
from app.models.region import Region
from app.models.workbook import Sheet
from app.pipeline.detect_regions import contains


def extract_text(ws: Worksheet, sheet: Sheet, regions: list[Region]) -> list[TextAsset]:
    assets = []
    for region in regions:
        if region.region_type in {"table", "summary_table", "empty", "image", "chart"}:
            continue
        left, top, right, bottom = range_boundaries(region.range)
        lines = []
        for row in ws.iter_rows(min_row=top, max_row=bottom, min_col=left, max_col=right):
            values = [str(c.value) for c in row if c.value is not None and c.data_type != "f"]
            if values:
                lines.append(" | ".join(values))
        if lines:
            assets.append(
                TextAsset(
                    text_asset_id=f"{region.region_id}_text",
                    workbook_id=sheet.workbook_id,
                    sheet_id=sheet.sheet_id,
                    region_id=region.region_id,
                    source_range=region.range,
                    content="\n".join(lines),
                    content_type=region.region_type,
                )
            )
    comments = {}
    for row in ws.iter_rows():
        for cell in row:
            if cell.comment:
                region = next(
                    (r for r in regions if contains(range_boundaries(r.range), cell.row, cell.column)), None
                )
                key = region.region_id if region else f"{sheet.sheet_id}_{cell.coordinate}"
                comments.setdefault(key, (region, []))[1].append(f"{cell.coordinate}: {cell.comment.text}")
    for key, (region, lines) in comments.items():
        assets.append(
            TextAsset(
                text_asset_id=f"{key}_comments",
                workbook_id=sheet.workbook_id,
                sheet_id=sheet.sheet_id,
                region_id=region.region_id if region else None,
                source_range=region.range if region else None,
                content="\n".join(lines),
                content_type="comments",
            )
        )
    return assets
