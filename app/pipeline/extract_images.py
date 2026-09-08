import logging
from mimetypes import guess_type
from pathlib import Path

from openpyxl.utils.cell import get_column_letter

from app.models.assets import ImageAsset
from app.models.region import Region
from app.models.run import WarningRecord


def anchor_cell(obj) -> str:
    anchor = obj.anchor
    if isinstance(anchor, str):
        return anchor
    start = getattr(anchor, "_from", None)
    return f"{get_column_letter(start.col + 1)}{start.row + 1}" if start else "A1"


def extract_images(ws, sheet, output: Path):
    assets, regions, warnings = [], [], []
    for index, image in enumerate(ws._images):
        identifier = f"{output.name}_{sheet.sheet_id}_image{index}"
        try:
            anchor = anchor_cell(image)
            extension = image.format if image.format in {"png", "jpeg", "gif"} else "png"
            filename = f"images/{identifier}.{extension}"
            (output / filename).write_bytes(image._data())
            region = Region(
                region_id=f"{identifier}_region",
                sheet_id=sheet.sheet_id,
                range=anchor,
                region_type="image",
                detected_by="embedded_image",
            )
            assets.append(
                ImageAsset(
                    image_id=identifier,
                    workbook_id=sheet.workbook_id,
                    sheet_id=sheet.sheet_id,
                    region_id=region.region_id,
                    anchor=anchor,
                    filename=filename,
                    mime_type=guess_type(filename)[0] or "image/png",
                    width=int(image.width),
                    height=int(image.height),
                )
            )
            regions.append(region)
        except Exception as exc:
            logging.getLogger(__name__).exception(
                "visual_extraction_failed", extra={"sheet_name": sheet.name}
            )
            warnings.append(
                WarningRecord(
                    code="IMAGE_EXTRACTION_FAILED", message=type(exc).__name__, sheet_name=sheet.name
                )
            )
    return assets, regions, warnings
