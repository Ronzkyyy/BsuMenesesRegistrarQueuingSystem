"""Validate raw rows with the app's own StudentCreate rules, diff against the
database, and (on commit) save every new/updated row in one transaction.

The live MX email check (student_service.validate_email_deliverable) is
deliberately NOT used: the file is the registrar's own record, and 2,000
DNS lookups would take ~30 minutes. Format is still checked (EmailStr).
"""
import re
from typing import Optional

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ...db_models import Course as DBCourse, Major as DBMajor, StudentDB, StudentDBType, YearLevel as DBYear
from ...models.student import StudentCreate
from ...models.student_import import ImportChange, ImportRowProblem, StudentImportReport
from . import normalize
from .columns import FLAG_COLUMNS, LABELS
from .reader import RawRow, ReadResult

_SCIENTIFIC = re.compile(r"^\d+(\.\d+)?[eE][+-]?\d+$")
_FIELDS = ["first_name", "last_name", "email", "student_type", "course", "major", "year_level",
           "is_scholar", "is_varsity", "is_graduating"]
_YEAR_LABELS = {"1st_year": "1st Year", "2nd_year": "2nd Year", "3rd_year": "3rd Year",
                "4th_year": "4th Year", "5th_year": "5th Year", "graduate": "Graduate"}
_FIELD_MESSAGES = {
    "student_id": ("Student Number", "Must be exactly 10 digits."),
    "first_name": ("First Name", "Required, up to 50 characters."),
    "last_name": ("Last Name", "Required, up to 50 characters."),
    "email": ("Email", "Not a valid email address (up to 100 characters)."),
}


class ImportConflictError(Exception):
    """A concurrent change broke a unique rule while saving. Carries no
    database text on purpose: it would include the student data being saved."""


class _RowError(Exception):
    def __init__(self, column: str, message: str):
        self.column, self.message = column, message


def _display(field: str, value) -> str:
    if value is None or value == "":
        return "—"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    value = getattr(value, "value", value)
    return _YEAR_LABELS.get(value, str(value)) if field == "year_level" else str(value)


def _current(student: StudentDB, field: str):
    value = getattr(student, field)
    return getattr(value, "value", value)


class StudentImporter:
    def __init__(self, db: Session):
        self.db = db

    def _parse(self, raw: RawRow) -> tuple[StudentCreate, dict[str, Optional[bool]]]:
        v = raw.values
        number = v.get("student_number", "").strip()
        if _SCIENTIFIC.match(number):
            raise _RowError("Student Number", f"Student number was changed by Excel ({number}). "
                                              "Format the column as Text and re-enter it.")
        parsed = {}
        for column, fn in (("student_type", normalize.student_type), ("course", normalize.course),
                           ("major", normalize.major), ("year_level", normalize.year_level)):
            try:
                parsed[column] = fn(v.get(column, ""))
            except normalize.NormalizeError as e:
                raise _RowError(LABELS[column], str(e))
        flags = {}
        for column in FLAG_COLUMNS:
            try:
                flags[column] = normalize.flag(v.get(column, ""))
            except normalize.NormalizeError as e:
                raise _RowError(LABELS[column], str(e))
        try:
            student = StudentCreate(
                student_id=number, first_name=v.get("first_name", ""), last_name=v.get("last_name", ""),
                email=v.get("email", "").strip(), **parsed,
            )
        except ValidationError as e:
            error = e.errors()[0]
            loc = error["loc"][0] if error["loc"] else None
            if loc in _FIELD_MESSAGES:
                raise _RowError(*_FIELD_MESSAGES[loc])
            # Model-level rule (BIT major) -> "Value error, major is required ..."
            raise _RowError("Major", error["msg"].removeprefix("Value error, ") + ".")
        return student, flags

    def run(self, read: ReadResult, commit: bool) -> StudentImportReport:
        problems: list[ImportRowProblem] = []
        valid: list[tuple[RawRow, StudentCreate, dict]] = []
        first_row: dict[str, int] = {}

        for raw in read.rows:
            number = raw.values.get("student_number", "").strip()
            try:
                student, flags = self._parse(raw)
            except _RowError as e:
                problems.append(ImportRowProblem(row=raw.row, student_number=number, column=e.column,
                                                 message=e.message, values=raw.original))
                continue
            if student.student_id in first_row:
                problems.append(ImportRowProblem(
                    row=raw.row, student_number=number, column="Student Number",
                    message=f"Student number also appears in row {first_row[student.student_id]}.",
                    values=raw.original))
                continue
            first_row[student.student_id] = raw.row
            valid.append((raw, student, flags))

        existing = {
            s.student_id: s for s in
            self.db.query(StudentDB).filter(StudentDB.student_id.in_(list(first_row))).all()
        } if first_row else {}

        changes: list[ImportChange] = []
        to_save: list[tuple[Optional[StudentDB], dict]] = []
        unchanged = 0
        for raw, student, flags in valid:
            current = existing.get(student.student_id)
            target = {
                "first_name": student.first_name, "last_name": student.last_name,
                "email": student.email, "student_type": student.student_type.value,
                "course": student.course.value, "major": student.major.value if student.major else None,
                "year_level": student.year_level.value,
            }
            for column in FLAG_COLUMNS:
                if flags[column] is not None:
                    target[column] = flags[column]
                else:
                    target[column] = getattr(current, column) if current else False
            name = f"{student.first_name} {student.last_name}"
            if current is None:
                changes.append(ImportChange(row=raw.row, student_number=student.student_id,
                                            name=name, action="new"))
                to_save.append((None, {"student_id": student.student_id, **target}))
                continue
            diff = {f: [_display(f, _current(current, f)), _display(f, target[f])]
                    for f in _FIELDS if _current(current, f) != target[f]}
            if not diff:
                unchanged += 1
                continue
            changes.append(ImportChange(row=raw.row, student_number=student.student_id,
                                        name=name, action="update", fields=diff))
            to_save.append((current, target))

        if commit and to_save:
            self._save(to_save)

        return StudentImportReport(
            committed=commit, file_type=read.file_type, total_rows=len(read.rows),
            new=sum(1 for c in changes if c.action == "new"),
            updated=sum(1 for c in changes if c.action == "update"),
            unchanged=unchanged, invalid=len(problems),
            columns=read.headers, ignored_columns=read.ignored_columns,
            problems=problems, changes=changes,
        )

    def _save(self, to_save: list[tuple[Optional[StudentDB], dict]]) -> None:
        def db_values(t: dict) -> dict:
            return {
                **t,
                "student_type": StudentDBType(t["student_type"]),
                "course": DBCourse(t["course"]),
                "major": DBMajor(t["major"]) if t["major"] else None,
                "year_level": DBYear(t["year_level"]),
            }
        try:
            for current, target in to_save:
                values = db_values(target)
                if current is None:
                    self.db.add(StudentDB(**values))
                else:
                    for f, value in values.items():
                        setattr(current, f, value)
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise ImportConflictError() from None
        except Exception:
            self.db.rollback()
            raise
