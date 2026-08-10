from pathlib import Path

from pypdf import PdfReader

from app.domain.normalized import DocumentPage, NormalizedSource
from app.tools.documents.chunk_document import chunk_document


class PdfParseError(ValueError):
    pass


def parse_pdf(path: Path, *, source_id: str, source_name: str) -> NormalizedSource:
    try:
        reader = PdfReader(path)
    except Exception as error:
        raise PdfParseError(f"PDF could not be opened: {error}") from error
    pages: list[DocumentPage] = []
    warnings: list[str] = []
    for number, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception as error:
            text = ""
            warnings.append(f"Page {number} text extraction failed: {error}")
        pages.append(DocumentPage(page_number=number, text=text, character_count=len(text)))
    total_characters = sum(page.character_count for page in pages)
    confidence = min(1.0, total_characters / max(1, len(pages) * 400))
    if confidence < 0.5:
        warnings.append("PDF text quality is low; OCR is recommended")
    return NormalizedSource(
        source_id=source_id,
        source_name=source_name,
        modality="unstructured",
        source_type="pdf",
        text="\n\n".join(page.text for page in pages),
        pages=pages,
        chunks=chunk_document(pages),
        parsing_confidence=confidence,
        warnings=warnings,
    )
