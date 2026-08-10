import json

from pydantic import BaseModel, Field, ValidationError, model_validator

from app.domain.normalized import ColumnDefinition, ForeignKeyDefinition, NormalizedSource, TableDefinition


class _JsonColumn(BaseModel):
    name: str
    data_type: str = "TEXT"
    nullable: bool = True
    primary_key: bool = False
    unique: bool = False
    description: str | None = None


class _JsonForeignKey(BaseModel):
    columns: list[str] = Field(default_factory=list)
    referenced_table: str = ""
    referenced_columns: list[str] = Field(default_factory=list)
    column: str | None = None
    references: str | None = None

    @model_validator(mode="after")
    def normalize_formats(self) -> "_JsonForeignKey":
        columns = self.columns or ([self.column] if self.column else [])
        referenced_table = self.referenced_table
        referenced_columns = self.referenced_columns
        if self.references and "." in self.references:
            referenced_table, referenced_column = self.references.rsplit(".", 1)
            referenced_columns = referenced_columns or [referenced_column]
        return self.model_copy(update={"columns": columns, "referenced_table": referenced_table, "referenced_columns": referenced_columns})


class _JsonTable(BaseModel):
    name: str
    description: str | None = None
    columns: list[_JsonColumn] = Field(default_factory=list)
    primary_key: list[str] = Field(default_factory=list)
    foreign_keys: list[_JsonForeignKey] = Field(default_factory=list)
    sample_semantics: dict[str, dict[str, str | int | float | bool | None]] = Field(default_factory=dict)


class _SchemaDocument(BaseModel):
    tables: list[_JsonTable]


class SchemaJsonParseError(ValueError):
    pass


def parse_schema_json(content: str, *, source_id: str, source_name: str) -> NormalizedSource:
    try:
        payload = _SchemaDocument.model_validate(json.loads(content))
    except (json.JSONDecodeError, ValidationError) as error:
        raise SchemaJsonParseError(f"Invalid schema JSON: {error}") from error
    tables: list[TableDefinition] = []
    for table in payload.tables:
        inferred_names = list(table.primary_key)
        inferred_names.extend(column for foreign_key in table.foreign_keys for column in foreign_key.columns)
        inferred_names.extend(attribute for sample in table.sample_semantics.values() for attribute in sample)
        explicit_names = {column.name for column in table.columns}
        columns = [
            ColumnDefinition(
                **column.model_dump(exclude={"primary_key"}),
                primary_key=column.primary_key or column.name in table.primary_key,
                inferred_key=column.name.lower() == "id" or column.name.lower().endswith("_id"),
            )
            for column in table.columns
        ]
        columns.extend(
            ColumnDefinition(name=name, data_type="TEXT", primary_key=name in table.primary_key, inferred_key=name.lower() == "id" or name.lower().endswith("_id"))
            for name in dict.fromkeys(inferred_names)
            if name not in explicit_names
        )
        tables.append(
            TableDefinition(
                name=table.name,
                description=table.description,
                columns=columns,
                primary_key=table.primary_key or [column.name for column in table.columns if column.primary_key],
                foreign_keys=[ForeignKeyDefinition(columns=foreign_key.columns, referenced_table=foreign_key.referenced_table, referenced_columns=foreign_key.referenced_columns) for foreign_key in table.foreign_keys],
            )
        )
    return NormalizedSource(
        source_id=source_id,
        source_name=source_name,
        modality="structured",
        source_type="schema_json",
        text=content,
        tables=tables,
        parsing_confidence=1.0,
    )
