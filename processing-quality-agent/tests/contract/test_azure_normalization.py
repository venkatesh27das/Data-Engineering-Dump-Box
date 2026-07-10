from types import SimpleNamespace

from processing_quality_agent.models.parser import ParserRequest
from processing_quality_agent.tools.azure_document_intelligence import (
    AzureDocumentIntelligenceAdapter,
)


def test_azure_result_normalization_preserves_pages_tables_and_geometry():
    line = SimpleNamespace(
        content="hello", polygon=[SimpleNamespace(x=0, y=0), SimpleNamespace(x=1, y=1)]
    )
    page = SimpleNamespace(page_number=1, lines=[line])
    cell = SimpleNamespace(row_index=0, column_index=0, content="A")
    table = SimpleNamespace(row_count=1, column_count=1, cells=[cell])
    raw = SimpleNamespace(pages=[page], tables=[table])
    result = AzureDocumentIntelligenceAdapter(None).normalize_result(
        ParserRequest(document_id="D", source_file_uri="abfss://x"), raw
    )
    assert result.document.page_count == 1
    assert result.document.table_payload[0]["cells"][0]["content"] == "A"
    assert result.elements[0].bounding_box == [0.0, 0.0, 1.0, 1.0]
