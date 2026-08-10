import re

from app.domain.normalized import ColumnDefinition, ForeignKeyDefinition, NormalizedSource, TableDefinition


class DDLParseError(ValueError):
    pass


_CREATE_TABLE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?P<name>(?:[`\"\[]?[A-Za-z_][\w$]*[`\"\]]?\.)?[`\"\[]?[A-Za-z_][\w$]*[`\"\]]?)\s*\(",
    re.IGNORECASE,
)
_CONSTRAINT_KEYWORDS = re.compile(
    r"\s+(?:NOT\s+NULL|NULL|PRIMARY\s+KEY|UNIQUE|REFERENCES|DEFAULT|CHECK|CONSTRAINT|COLLATE|GENERATED)\b",
    re.IGNORECASE,
)


def _clean_identifier(value: str) -> str:
    return ".".join(part.strip('`"[] ') for part in value.split("."))


def _matching_parenthesis(sql: str, opening: int) -> int:
    depth = 0
    quote: str | None = None
    for index in range(opening, len(sql)):
        character = sql[index]
        if quote:
            if character == quote and (index == 0 or sql[index - 1] != "\\"):
                quote = None
            continue
        if character in {"'", '"', "`"}:
            quote = character
        elif character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
            if depth == 0:
                return index
    raise DDLParseError("CREATE TABLE statement has unbalanced parentheses")


def _split_definitions(body: str) -> list[str]:
    definitions: list[str] = []
    start = 0
    depth = 0
    quote: str | None = None
    for index, character in enumerate(body):
        if quote:
            if character == quote and (index == 0 or body[index - 1] != "\\"):
                quote = None
            continue
        if character in {"'", '"', "`"}:
            quote = character
        elif character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
        elif character == "," and depth == 0:
            definitions.append(body[start:index].strip())
            start = index + 1
    trailing = body[start:].strip()
    if trailing:
        definitions.append(trailing)
    return definitions


def _identifier_list(value: str) -> list[str]:
    return [_clean_identifier(item) for item in value.split(",") if item.strip()]


def _parse_table(name: str, body: str) -> TableDefinition:
    columns: list[ColumnDefinition] = []
    primary_key: list[str] = []
    foreign_keys: list[ForeignKeyDefinition] = []

    for definition in _split_definitions(body):
        normalized = definition.strip()
        constraint_name: str | None = None
        constraint_match = re.match(r"CONSTRAINT\s+([^\s]+)\s+(.*)$", normalized, re.IGNORECASE | re.DOTALL)
        if constraint_match:
            constraint_name = _clean_identifier(constraint_match.group(1))
            normalized = constraint_match.group(2).strip()

        pk_match = re.match(r"PRIMARY\s+KEY\s*\(([^)]+)\)", normalized, re.IGNORECASE)
        if pk_match:
            primary_key.extend(_identifier_list(pk_match.group(1)))
            continue

        fk_match = re.match(
            r"FOREIGN\s+KEY\s*\(([^)]+)\)\s+REFERENCES\s+([^\s(]+)\s*\(([^)]+)\)",
            normalized,
            re.IGNORECASE,
        )
        if fk_match:
            foreign_keys.append(
                ForeignKeyDefinition(
                    columns=_identifier_list(fk_match.group(1)),
                    referenced_table=_clean_identifier(fk_match.group(2)),
                    referenced_columns=_identifier_list(fk_match.group(3)),
                    constraint_name=constraint_name,
                )
            )
            continue

        if re.match(r"(?:UNIQUE|CHECK)\b", normalized, re.IGNORECASE):
            continue

        column_match = re.match(r"([^\s]+)\s+(.+)$", normalized, re.DOTALL)
        if not column_match:
            continue
        column_name = _clean_identifier(column_match.group(1))
        remainder = column_match.group(2).strip()
        keyword = _CONSTRAINT_KEYWORDS.search(remainder)
        data_type = (remainder[: keyword.start()] if keyword else remainder).strip()
        inline_primary = bool(re.search(r"\bPRIMARY\s+KEY\b", remainder, re.IGNORECASE))
        reference = re.search(r"\bREFERENCES\s+([^\s(]+)\s*\(([^)]+)\)", remainder, re.IGNORECASE)
        column = ColumnDefinition(
            name=column_name,
            data_type=data_type.upper(),
            nullable=not bool(re.search(r"\bNOT\s+NULL\b", remainder, re.IGNORECASE)) and not inline_primary,
            primary_key=inline_primary,
            unique=bool(re.search(r"\bUNIQUE\b", remainder, re.IGNORECASE)),
            inferred_key=column_name.lower() == "id" or column_name.lower().endswith("_id"),
            references_table=_clean_identifier(reference.group(1)) if reference else None,
            references_column=_clean_identifier(reference.group(2)) if reference else None,
        )
        columns.append(column)
        if inline_primary:
            primary_key.append(column_name)
        if reference:
            foreign_keys.append(
                ForeignKeyDefinition(
                    columns=[column_name],
                    referenced_table=_clean_identifier(reference.group(1)),
                    referenced_columns=[_clean_identifier(reference.group(2))],
                )
            )

    primary_set = set(primary_key)
    columns = [column.model_copy(update={"primary_key": column.name in primary_set or column.primary_key}) for column in columns]
    return TableDefinition(name=_clean_identifier(name), columns=columns, primary_key=list(dict.fromkeys(primary_key)), foreign_keys=foreign_keys)


def parse_ddl(sql: str, *, source_id: str, source_name: str) -> NormalizedSource:
    tables: list[TableDefinition] = []
    for match in _CREATE_TABLE.finditer(sql):
        opening = match.end() - 1
        closing = _matching_parenthesis(sql, opening)
        tables.append(_parse_table(match.group("name"), sql[opening + 1 : closing]))
    if not tables:
        raise DDLParseError("No CREATE TABLE statements were found")
    return NormalizedSource(
        source_id=source_id,
        source_name=source_name,
        modality="structured",
        source_type="sql_ddl",
        text=sql,
        tables=tables,
        parsing_confidence=1.0,
    )
