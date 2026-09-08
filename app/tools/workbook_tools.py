"""Read-only tools scoped to an already-authorized workbook region. Never accepts filesystem paths."""

from openpyxl.utils.cell import range_boundaries

from app.models.region import Region
from app.pipeline.detect_regions import contains


class WorkbookTools:
    def __init__(self, formula_wb, value_wb, sheet_name: str, region: Region, max_cells: int = 200):
        self.wb, self.values = formula_wb, value_wb
        self.sheet_name, self.region, self.max_cells = sheet_name, region, max_cells

    def inspect_range(self, cell_range: str | None = None, include_styles: bool = False) -> dict:
        box = range_boundaries(cell_range or self.region.range)
        scope = range_boundaries(self.region.range)
        if (
            any(v is None for v in box)
            or not contains(scope, box[1], box[0])
            or not contains(scope, box[3], box[2])
        ):
            raise ValueError("Requested cells must stay inside the selected region")
        rows, used = [], 0
        # Clip loops before visiting cells; return bounded content even for million-cell ranges.
        for r in range(box[1], min(box[3] + 1, box[1] + self.max_cells)):
            row = []
            for c in range(box[0], min(box[2] + 1, box[0] + self.max_cells - used)):
                cell = self.wb[self.sheet_name].cell(r, c)
                cached = self.values[self.sheet_name].cell(r, c).value
                item = {
                    "cell": cell.coordinate,
                    "value": str(cached)[:300] if cached is not None else None,
                    "formula": str(cell.value)[:300] if cell.data_type == "f" else None,
                }
                if include_styles:
                    item["styles"] = {
                        "bold": bool(cell.font.bold),
                        "number_format": cell.number_format,
                        "fill": cell.fill.fill_type,
                        "border": cell.border.bottom.style,
                    }
                row.append(item)
                used += 1
            if row:
                rows.append(row)
            if used >= self.max_cells:
                break
        return {
            "sheet": self.sheet_name,
            "range": cell_range or self.region.range,
            "rows": rows,
            "truncated": (box[2] - box[0] + 1) * (box[3] - box[1] + 1) > used,
        }

    def dispatch(self, name: str, arguments: dict) -> dict:
        if set(arguments) - {"cell_range"}:
            raise ValueError("Unsupported tool arguments")
        if name not in {"inspect_range", "get_values", "get_formulas", "get_styles"}:
            raise ValueError("Tool is not allowed")
        result = self.inspect_range(arguments.get("cell_range"), include_styles=name == "get_styles")
        if name in {"get_values", "get_formulas"}:
            unwanted = "formula" if name == "get_values" else "value"
            for row in result["rows"]:
                for cell in row:
                    cell.pop(unwanted, None)
        return result

    @staticmethod
    def schemas() -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": f"{name.replace('_', ' ')} inside the selected region; bounded output only.",
                    "parameters": {
                        "type": "object",
                        "properties": {"cell_range": {"type": "string"}},
                        "additionalProperties": False,
                    },
                },
            }
            for name in ("inspect_range", "get_values", "get_formulas", "get_styles")
        ]
