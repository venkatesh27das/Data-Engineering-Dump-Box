import csv
import io

from app.domain.normalized import ColumnDefinition, ForeignKeyDefinition, NormalizedSource, TableDefinition


class SchemaCsvParseError(ValueError):
    pass


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "y", "pk"}


def parse_schema_csv(content: str, *, source_id: str, source_name: str) -> NormalizedSource:
    reader = csv.DictReader(io.StringIO(content))
    fieldnames = {name.lower() for name in (reader.fieldnames or [])}
    if not {"table_name", "column_name"}.issubset(fieldnames):
        if not reader.fieldnames:
            raise SchemaCsvParseError("CSV does not contain a header row")
        table_name = source_name.rsplit(".", 1)[0]
        columns = [ColumnDefinition(name=name.strip(), data_type="TEXT", inferred_key=name.strip().lower() == "id" or name.strip().lower().endswith("_id")) for name in reader.fieldnames if name.strip()]
        return NormalizedSource(source_id=source_id, source_name=source_name, modality="structured", source_type="sample_csv", text=content, tables=[TableDefinition(name=table_name, columns=columns)], parsing_confidence=0.85, warnings=["Column types were inferred from a sample CSV header"])
    grouped: dict[str, list[dict[str, str]]] = {}
    for raw_row in reader:
        row = {str(key).lower(): value for key, value in raw_row.items() if key is not None}
        table_name = (row.get("table_name") or "").strip()
        column_name = (row.get("column_name") or "").strip()
        if table_name and column_name:
            grouped.setdefault(table_name, []).append(row)
    if not grouped:
        raise SchemaCsvParseError("Schema CSV did not contain any columns")

    tables: list[TableDefinition] = []
    for table_name, rows in grouped.items():
        columns: list[ColumnDefinition] = []
        foreign_keys: list[ForeignKeyDefinition] = []
        for row in rows:
            name = row["column_name"].strip()
            key_type = (row.get("key_type") or "").strip()
            reference_table = (row.get("referenced_table") or row.get("foreign_table") or "").strip() or None
            reference_column = (row.get("referenced_column") or row.get("foreign_column") or "").strip() or None
            if key_type.upper().startswith("FK->") and "." in key_type:
                reference_table, reference_column = key_type[4:].rsplit(".", 1)
            primary = _truthy(row.get("is_primary_key") or row.get("primary_key")) or key_type.upper() == "PK"
            columns.append(
                ColumnDefinition(
                    name=name,
                    data_type=(row.get("data_type") or row.get("type") or "TEXT").strip().upper(),
                    nullable=not _truthy(row.get("not_null")) if not row.get("nullable") else _truthy(row.get("nullable")),
                    primary_key=primary,
                    unique=_truthy(row.get("is_unique") or row.get("unique")),
                    inferred_key=name.lower() == "id" or name.lower().endswith("_id"),
                    references_table=reference_table,
                    references_column=reference_column,
                    description=(row.get("description") or row.get("business_description") or "").strip() or None,
                )
            )
            if reference_table and reference_column:
                foreign_keys.append(ForeignKeyDefinition(columns=[name], referenced_table=reference_table, referenced_columns=[reference_column]))
        tables.append(TableDefinition(name=table_name, columns=columns, primary_key=[column.name for column in columns if column.primary_key], foreign_keys=foreign_keys))

    return NormalizedSource(
        source_id=source_id,
        source_name=source_name,
        modality="structured",
        source_type="schema_csv",
        text=content,
        tables=tables,
        parsing_confidence=0.98,
    )
