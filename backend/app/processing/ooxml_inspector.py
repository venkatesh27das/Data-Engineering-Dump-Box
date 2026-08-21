import re
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlsplit, urlunsplit
from xml.etree import ElementTree


def inspect_ooxml(path: Path, book: Any) -> dict[str, list[dict[str, Any]] | bool]:
    result: dict[str, list[dict[str, Any]] | bool] = {
        "external_links": [],
        "connections": [],
        "queries": [],
        "pivots": [],
        "conditional_formats": [],
        "data_validations": [],
        "macro_present": False,
    }
    _inspect_sheet_features(book, result)
    if path.suffix.lower() not in {".xlsx", ".xlsm"}:
        return result
    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
            result["macro_present"] = "xl/vbaProject.bin" in names
            _inspect_relationships(archive, result)
            _inspect_connections(archive, result)
            _inspect_queries(archive, result)
            _inspect_pivot_parts(archive, result)
    except (zipfile.BadZipFile, KeyError, ElementTree.ParseError):
        pass
    return result


def _inspect_sheet_features(book: Any, result: dict[str, Any]) -> None:
    for sheet in book.worksheets:
        for conditional in sheet.conditional_formatting:
            for rule in conditional.rules:
                result["conditional_formats"].append(
                    {
                        "sheet_name": sheet.title,
                        "source_range": str(conditional.sqref),
                        "rule_type": rule.type,
                        "operator": getattr(rule, "operator", None),
                        "priority": getattr(rule, "priority", None),
                        "formula": list(getattr(rule, "formula", []) or []),
                        "stop_if_true": bool(getattr(rule, "stopIfTrue", False)),
                    }
                )
        validations = getattr(sheet.data_validations, "dataValidation", [])
        for validation in validations:
            result["data_validations"].append(
                {
                    "sheet_name": sheet.title,
                    "source_range": str(validation.sqref),
                    "validation_type": validation.type,
                    "operator": validation.operator,
                    "formula1": validation.formula1,
                    "formula2": validation.formula2,
                    "allow_blank": validation.allowBlank,
                    "error_title": validation.errorTitle,
                    "error_message": validation.error,
                }
            )
        for pivot in getattr(sheet, "_pivots", []):
            location = getattr(pivot, "location", None)
            source = getattr(
                getattr(getattr(pivot, "cache", None), "cacheSource", None),
                "worksheetSource",
                None,
            )
            result["pivots"].append(
                {
                    "pivot_id": f"pivot.{sheet.title}.{getattr(pivot, 'name', 'unnamed')}",
                    "sheet_name": sheet.title,
                    "name": getattr(pivot, "name", None),
                    "cache_id": getattr(pivot, "cacheId", None),
                    "source_range": getattr(location, "ref", None),
                    "source_sheet": getattr(source, "sheet", None),
                    "source_data_range": getattr(source, "ref", None),
                    "source_name": getattr(source, "name", None),
                    "row_field_count": len(getattr(getattr(pivot, "rowFields", None), "x", []) or []),
                    "column_field_count": len(getattr(getattr(pivot, "colFields", None), "x", []) or []),
                    "data_field_count": len(
                        getattr(getattr(pivot, "dataFields", None), "dataField", []) or []
                    ),
                }
            )


def _inspect_relationships(archive: zipfile.ZipFile, result: dict[str, Any]) -> None:
    seen: set[tuple[str, str]] = set()
    for name in archive.namelist():
        if not name.endswith(".rels"):
            continue
        try:
            root = ElementTree.fromstring(archive.read(name))
        except ElementTree.ParseError:
            continue
        for relation in root.findall("{*}Relationship"):
            target = relation.attrib.get("Target", "")
            relation_type = relation.attrib.get("Type", "").rsplit("/", 1)[-1]
            if relation.attrib.get("TargetMode") != "External" and not relation_type.startswith(
                "externalLink"
            ):
                continue
            key = (relation_type, target)
            if key in seen:
                continue
            seen.add(key)
            result["external_links"].append(
                {
                    "relationship_type": relation_type,
                    "target": _safe_external_target(target),
                    "source_part": name,
                }
            )


def _inspect_connections(archive: zipfile.ZipFile, result: dict[str, Any]) -> None:
    if "xl/connections.xml" not in archive.namelist():
        return
    root = ElementTree.fromstring(archive.read("xl/connections.xml"))
    for connection in root.findall("{*}connection"):
        db_properties = connection.find("{*}dbPr")
        web_properties = connection.find("{*}webPr")
        item = {
            "connection_id": connection.attrib.get("id"),
            "name": connection.attrib.get("name"),
            "description": connection.attrib.get("description"),
            "type": connection.attrib.get("type"),
            "refresh_on_load": connection.attrib.get("refreshOnLoad") == "1",
            "background": connection.attrib.get("background") == "1",
            "source_file": _safe_external_target(connection.attrib.get("sourceFile", "")),
        }
        if db_properties is not None:
            item.update(
                {
                    "connection_string": _redact_connection_string(
                        db_properties.attrib.get("connection", "")
                    ),
                    "command": db_properties.attrib.get("command"),
                    "command_type": db_properties.attrib.get("commandType"),
                }
            )
        if web_properties is not None:
            item["web_url"] = _safe_external_target(web_properties.attrib.get("url", ""))
        result["connections"].append(item)


def _inspect_queries(archive: zipfile.ZipFile, result: dict[str, Any]) -> None:
    names = archive.namelist()
    for name in names:
        if not name.startswith("xl/queryTables/") or not name.endswith(".xml"):
            continue
        root = ElementTree.fromstring(archive.read(name))
        result["queries"].append(
            {
                "query_id": PurePosixPath(name).stem,
                "name": root.attrib.get("name"),
                "connection_id": root.attrib.get("connectionId"),
                "refresh_on_load": root.attrib.get("refreshOnLoad") == "1",
                "source_part": name,
                "query_type": "query_table",
            }
        )
    mashup_parts = [
        name
        for name in names
        if "datamashup" in name.casefold()
        or name.startswith("xl/model/")
        or name.startswith("customXml/")
        and name.endswith(".bin")
    ]
    if mashup_parts:
        result["queries"].append(
            {
                "query_id": "power_query_package",
                "name": "Power Query / Data Model package",
                "query_type": "power_query_package",
                "source_parts": mashup_parts,
            }
        )


def _inspect_pivot_parts(archive: zipfile.ZipFile, result: dict[str, Any]) -> None:
    known_parts = {item.get("source_part") for item in result["pivots"]}
    for name in archive.namelist():
        if not name.startswith("xl/pivotTables/") or not name.endswith(".xml"):
            continue
        if name in known_parts:
            continue
        root = ElementTree.fromstring(archive.read(name))
        location = root.find("{*}location")
        result["pivots"].append(
            {
                "pivot_id": f"pivot.{PurePosixPath(name).stem}",
                "name": root.attrib.get("name"),
                "cache_id": root.attrib.get("cacheId"),
                "source_range": location.attrib.get("ref") if location is not None else None,
                "row_field_count": len(root.findall(".//{*}rowFields/{*}field")),
                "column_field_count": len(root.findall(".//{*}colFields/{*}field")),
                "data_field_count": len(root.findall(".//{*}dataFields/{*}dataField")),
                "source_part": name,
            }
        )


def _redact_connection_string(value: str) -> str:
    if not value:
        return ""
    return re.sub(
        r"(?i)(password|pwd|token|access[_ ]?key|secret)\s*=\s*([^;]*)",
        lambda match: f"{match.group(1)}=[REDACTED]",
        value,
    )


def _safe_external_target(value: str) -> str:
    if not value:
        return ""
    parsed = urlsplit(value)
    if parsed.scheme in {"http", "https", "ftp"}:
        host = parsed.hostname or ""
        if parsed.port:
            host = f"{host}:{parsed.port}"
        return urlunsplit((parsed.scheme, host, parsed.path, "", ""))
    return re.sub(r"(?i)(password|pwd|token|secret)=([^;&]+)", r"\1=[REDACTED]", value)
