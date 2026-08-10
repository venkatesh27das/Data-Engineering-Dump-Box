from pathlib import Path

import pytesseract
from PIL import Image, UnidentifiedImageError

from app.domain.normalized import DocumentPage, NormalizedSource
from app.tools.documents.chunk_document import chunk_document


class ImageParseError(ValueError):
    pass


def parse_image(path: Path, *, source_id: str, source_name: str) -> NormalizedSource:
    try:
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            text = pytesseract.image_to_string(image).strip()
    except pytesseract.TesseractNotFoundError:
        text = ""
        page = DocumentPage(page_number=1, text=text, character_count=0)
        return NormalizedSource(
            source_id=source_id,
            source_name=source_name,
            modality="unstructured",
            source_type="image_ocr_pending",
            pages=[page],
            parsing_confidence=0,
            warnings=["OCR is required, but the local Tesseract executable is unavailable"],
        )
    except (UnidentifiedImageError, OSError) as error:
        raise ImageParseError(f"Image could not be opened: {error}") from error
    page = DocumentPage(page_number=1, text=text, character_count=len(text))
    confidence = min(0.95, len(text) / 300) if text else 0.0
    warnings = [] if confidence >= 0.5 else ["OCR text quality is low and should be reviewed"]
    return NormalizedSource(
        source_id=source_id,
        source_name=source_name,
        modality="unstructured",
        source_type="image_ocr",
        text=text,
        pages=[page],
        chunks=chunk_document([page]),
        parsing_confidence=confidence,
        warnings=warnings,
    )
