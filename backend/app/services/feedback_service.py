import re
from typing import Any, Protocol
from uuid import uuid4

from app.agents.schemas import FeedbackInterpretation


class FeedbackRuntime(Protocol):
    def interpret_feedback(self, text: str) -> FeedbackInterpretation: ...


def parse_feedback(text: str, runtime: FeedbackRuntime | None = None) -> list[dict[str, Any]]:
    if runtime and text.strip():
        try:
            interpreted = runtime.interpret_feedback(text.strip())
            if interpreted.directives:
                return [
                    {
                        "directive_id": f"directive.{uuid4().hex[:12]}",
                        **directive.model_dump(),
                        "parser": "local_feedback_agent",
                    }
                    for directive in interpreted.directives
                ]
        except Exception:
            pass
    return _parse_feedback_deterministically(text)


def _parse_feedback_deterministically(text: str) -> list[dict[str, Any]]:
    directives: list[dict[str, Any]] = []
    lower = text.lower()
    row_match = re.search(r"(?:row|header(?: row)?)\s*(\d+)", lower)
    sheet_match = re.search(
        r"(?:in|on|from)\s+['\"]?([a-z0-9 _-]+?)['\"]?\s+(?:sheet|as|is|should|to|and|$)", lower
    )
    if "header" in lower and row_match:
        header = int(row_match.group(1))
        directives.append(
            _directive(
                "override_header_row",
                {"sheet_name": sheet_match.group(1).strip().title() if sheet_match else "*"},
                {"header_row": header, "ignore_rows": list(range(1, header))},
                0.86,
            )
        )
    if "exclude" in lower and "sheet" in lower:
        name = sheet_match.group(1).strip().title() if sheet_match else "unspecified"
        directives.append(_directive("exclude_sheet", {"sheet_name": name}, {}, 0.72, name == "unspecified"))
    if any(word in lower for word in ("same identifier", "same field", "equivalent")):
        fields = re.findall(r"(?:[A-Z][\w ]{1,30}(?:ID|No|Number))", text)
        directives.append(
            _directive(
                "confirm_semantic_mapping",
                {
                    "source_field": fields[0] if fields else "unspecified",
                    "target_field": fields[1] if len(fields) > 1 else "unspecified",
                },
                {"enterprise_term": "Shared identifier"},
                0.68,
                len(fields) < 2,
            )
        )
    if not directives:
        directives.append(
            _directive("set_business_context", {"scope": "impacted_assets"}, {"context": text.strip()}, 0.78)
        )
    return directives


def _directive(
    kind: str, target: dict[str, Any], parameters: dict[str, Any], confidence: float, confirm: bool = False
) -> dict[str, Any]:
    return {
        "directive_id": f"directive.{uuid4().hex[:12]}",
        "type": kind,
        "target": target,
        "parameters": parameters,
        "confidence": confidence,
        "requires_confirmation": confirm,
    }
