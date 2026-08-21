from dataclasses import dataclass


@dataclass
class WorkbookError(Exception):
    code: str
    message: str
    status_code: int = 400

    def __str__(self) -> str:
        return self.message
