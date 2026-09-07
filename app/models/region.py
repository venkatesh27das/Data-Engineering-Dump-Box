from pydantic import BaseModel


class Region(BaseModel):
    region_id: str
    sheet_id: str
    range: str
    region_type: str = "table"
    confidence: float = 1.0
    detected_by: str = "native_excel_table"
    requires_agent_review: bool = False
    agent_review_status: str = "not_requested"
