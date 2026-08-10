from app.domain.normalized import DocumentChunk, DocumentPage


def chunk_document(
    pages: list[DocumentPage],
    *,
    chunk_size: int = 1_200,
    overlap: int = 150,
) -> list[DocumentChunk]:
    if chunk_size <= overlap or overlap < 0:
        raise ValueError("chunk_size must be greater than a non-negative overlap")
    chunks: list[DocumentChunk] = []
    for page in pages:
        text = page.text.strip()
        start = 0
        index = 1
        while start < len(text):
            end = min(len(text), start + chunk_size)
            if end < len(text):
                natural_break = max(text.rfind("\n", start, end), text.rfind(". ", start, end))
                if natural_break > start + chunk_size // 2:
                    end = natural_break + 1
            chunk_text = text[start:end].strip()
            if chunk_text:
                chunks.append(DocumentChunk(id=f"page-{page.page_number}-chunk-{index}", text=chunk_text, page=page.page_number, start_offset=start, end_offset=end))
                index += 1
            if end >= len(text):
                break
            start = max(start + 1, end - overlap)
    return chunks
