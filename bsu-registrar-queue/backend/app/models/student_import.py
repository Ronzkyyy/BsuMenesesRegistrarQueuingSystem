"""Response models for the Admin student file import (preview and commit)."""
from typing import Literal

from pydantic import BaseModel


class ImportRowProblem(BaseModel):
    row: int
    student_number: str
    column: str
    message: str
    values: dict[str, str]     # the row's original cells, for the "rows with errors" download


class ImportChange(BaseModel):
    row: int
    student_number: str
    name: str
    action: Literal["new", "update"]
    fields: dict[str, list[str]] = {}    # update only: field -> [before, after]


class StudentImportReport(BaseModel):
    committed: bool
    file_type: str
    total_rows: int
    new: int
    updated: int
    unchanged: int
    invalid: int
    columns: list[str]
    ignored_columns: list[str]
    problems: list[ImportRowProblem]
    changes: list[ImportChange]
