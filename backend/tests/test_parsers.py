from pathlib import Path

from pypdf import PdfWriter
from PIL import Image
import pytesseract

from app.tools.documents.parse_pdf import parse_pdf
from app.tools.documents.parse_image import parse_image
from app.tools.structured.parse_ddl import parse_ddl
from app.tools.structured.parse_schema_csv import parse_schema_csv
from app.tools.structured.parse_schema_json import parse_schema_json


def test_parse_ddl_extracts_keys_and_relationships() -> None:
    result = parse_ddl(
        """
        CREATE TABLE suppliers (
          supplier_id INTEGER PRIMARY KEY,
          name VARCHAR(200) NOT NULL
        );
        CREATE TABLE contracts (
          contract_id INTEGER PRIMARY KEY,
          supplier_id INTEGER NOT NULL,
          CONSTRAINT fk_supplier FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id)
        );
        """,
        source_id="SRC-1",
        source_name="supplier_schema.sql",
    )
    assert [table.name for table in result.tables] == ["suppliers", "contracts"]
    assert result.tables[0].primary_key == ["supplier_id"]
    assert result.tables[1].foreign_keys[0].referenced_table == "suppliers"


def test_parse_schema_json() -> None:
    result = parse_schema_json(
        '{"tables":[{"name":"products","columns":[{"name":"id","data_type":"uuid","primary_key":true},{"name":"name","data_type":"text"}]}]}',
        source_id="SRC-2",
        source_name="schema.json",
    )
    assert result.tables[0].columns[0].primary_key is True
    assert result.tables[0].columns[0].inferred_key is True


def test_parse_semantic_schema_json_without_explicit_columns() -> None:
    result = parse_schema_json(
        '{"tables":[{"name":"suppliers","primary_key":["supplier_id"],"sample_semantics":{"SUP-1":{"supplier_name":"ACME"}}}]}',
        source_id="SRC-2B",
        source_name="context.json",
    )
    assert {column.name for column in result.tables[0].columns} == {"supplier_id", "supplier_name"}


def test_parse_schema_csv() -> None:
    result = parse_schema_csv(
        "table_name,column_name,data_type,is_primary_key\nsuppliers,id,integer,true\nsuppliers,name,text,false\n",
        source_id="SRC-3",
        source_name="schema.csv",
    )
    assert result.tables[0].primary_key == ["id"]


def test_parse_metadata_key_type_and_sample_csv() -> None:
    metadata = parse_schema_csv(
        "table_name,column_name,data_type,key_type\nproducts,id,text,PK\nproducts,supplier_id,text,FK->suppliers.id\n",
        source_id="SRC-3B",
        source_name="metadata.csv",
    )
    assert metadata.tables[0].foreign_keys[0].referenced_table == "suppliers"
    sample = parse_schema_csv("supplier_id,supplier_name\nSUP-1,ACME\n", source_id="SRC-3C", source_name="supplier_sample.csv")
    assert sample.source_type == "sample_csv"
    assert sample.tables[0].name == "supplier_sample"


def test_pdf_parser_smoke(tmp_path: Path) -> None:
    path = tmp_path / "blank.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    with path.open("wb") as output:
        writer.write(output)

    result = parse_pdf(path, source_id="SRC-4", source_name="blank.pdf")
    assert result.source_type == "pdf"
    assert len(result.pages) == 1
    assert result.parsing_confidence == 0
    assert "OCR is recommended" in result.warnings[-1]


def test_image_parser_returns_typed_ocr_pending_state(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "scan.png"
    Image.new("RGB", (20, 20), "white").save(path)

    def missing_tesseract(*_args, **_kwargs):
        raise pytesseract.TesseractNotFoundError()

    monkeypatch.setattr(pytesseract, "image_to_string", missing_tesseract)
    result = parse_image(path, source_id="SRC-5", source_name="scan.png")
    assert result.source_type == "image_ocr_pending"
    assert result.parsing_confidence == 0
    assert "unavailable" in result.warnings[0]
