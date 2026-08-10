import re

_WRITE_OR_ADMIN = re.compile(
    r"\b(CREATE|MERGE|DELETE|DETACH|SET|REMOVE|DROP|ALTER|LOAD|FOREACH|CALL|SHOW|GRANT|DENY|REVOKE|TERMINATE|START|STOP|USE|APOC|DBMS|GDS)\b",
    re.IGNORECASE,
)
_LIMIT = re.compile(r"\bLIMIT\s+(\d+)\b", re.IGNORECASE)


def validate_read_only_cypher(query: str) -> str:
    normalized = " ".join(query.strip().split())
    if ";" in normalized or "//" in normalized or "/*" in normalized:
        raise ValueError("Comments and multiple Cypher statements are not allowed")
    if not re.match(r"^(OPTIONAL\s+MATCH|MATCH|WITH|UNWIND)\b", normalized, re.IGNORECASE):
        raise ValueError("Read-only Cypher must begin with MATCH, OPTIONAL MATCH, WITH, or UNWIND")
    if _WRITE_OR_ADMIN.search(normalized):
        raise ValueError("Write and administrative Cypher clauses are not allowed")
    if not re.search(r"\bRETURN\b", normalized, re.IGNORECASE):
        raise ValueError("Read-only Cypher must contain RETURN")
    if "$project_id" not in normalized:
        raise ValueError("Query must scope graph data with the $project_id parameter")
    limit = _LIMIT.search(normalized)
    if limit and int(limit.group(1)) > 200:
        raise ValueError("Query LIMIT cannot exceed 200")
    if not limit:
        normalized = f"{normalized} LIMIT 100"
    return normalized
