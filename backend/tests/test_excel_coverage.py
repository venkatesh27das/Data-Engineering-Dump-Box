import json
import zipfile
from pathlib import Path
from types import SimpleNamespace

from pyxlsb.worksheet import Cell

from app.processing.extractor import extract_workbook, workbook_protection_present
from app.processing.package_writer import write_package
from app.processing.vba_inspector import inspect_vba

FIXTURES = Path(__file__).parent / "fixtures" / "workbooks"


def test_missing_workbook_protection_metadata_is_treated_as_unprotected():
    assert workbook_protection_present(SimpleNamespace(security=None)) is False
    assert (
        workbook_protection_present(
            SimpleNamespace(security=SimpleNamespace(lockStructure=True, lockWindows=False))
        )
        is True
    )


def test_advanced_layout_and_ooxml_features_are_extracted(tmp_path: Path):
    result = extract_workbook(FIXTURES / "15_advanced_layout.xlsx", "wb_advanced", "run_advanced", False)

    multi = next(table for table in result.tables if table["name"] == "Multi Header Data")
    repeated = [table for table in result.tables if table["region_type"] == "repeated_table"]

    assert multi["header_depth"] == 2
    assert multi["normalized_headers"] == [
        "customer_id",
        "customer_name",
        "financial_revenue",
        "financial_margin",
    ]
    assert len(repeated) == 2
    assert result.forms[0]["title"] == "Employee Profile"
    assert result.forms[0]["field_count"] == 4
    assert len(result.external_links) == 1
    assert len(result.connections) == 1
    assert "secret" not in result.connections[0]["connection_string"]
    assert "[REDACTED]" in result.connections[0]["connection_string"]
    assert len(result.queries) == 1
    assert len(result.pivots) == 1
    assert len(result.conditional_formats) == 1
    assert len(result.data_validations) == 1
    assert result.charts[0]["data_sources"]
    assert result.charts[0]["anchor_cell"] == "E2"
    assert result.images[0]["anchor_cell"] == "E18"

    archive = write_package(result, tmp_path)
    with zipfile.ZipFile(archive) as package:
        names = set(package.namelist())
        assert "metadata/external_links.jsonl" in names
        assert "metadata/connections.jsonl" in names
        assert "metadata/pivots.jsonl" in names
        assert "metadata/forms.jsonl" in names
        visual = package.read("semantic_units/visual_units.jsonl").decode()
        assert "Monthly Revenue" in visual
        manifest = json.loads(package.read("manifest.json"))
        assert manifest["counts"]["forms"] == 1


def test_static_vba_inspector_does_not_report_macros_for_xlsx():
    report = inspect_vba(FIXTURES / "01_clean_table.xlsx")
    assert report["contains_macros"] is False
    assert report["inspection_status"] == "not_present"


class _FakeSheet:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def rows(self):
        yield [Cell(0, 0, "Order ID"), Cell(0, 1, "Amount")]
        yield [Cell(1, 0, "ORD-1"), Cell(1, 1, 125)]
        yield [Cell(2, 0, "ORD-2"), Cell(2, 1, 200)]


class _FakeBinaryBook:
    sheets = ["Orders"]

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def get_sheet(self, _name):
        return _FakeSheet()


def test_xlsb_values_get_table_and_semantic_unit_parity(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("pyxlsb.open_workbook", lambda _path: _FakeBinaryBook())
    result = extract_workbook(tmp_path / "orders.xlsb", "wb_binary", "run_binary", False)

    assert result.manifest["file_type"] == "xlsb"
    assert len(result.tables) == 1
    assert result.tables[0]["normalized_headers"] == ["order_id", "amount"]
    assert len(result.units) == 2
    assert result.table_rows[result.tables[0]["table_id"]][0]["order_id"] == "ORD-1"
