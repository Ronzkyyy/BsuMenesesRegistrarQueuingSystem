# Student File Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let an Admin upload an .xlsx or .csv student list in Student Management, preview new / updated / unchanged / invalid rows, then import the valid rows.

**Architecture:** A `student_import` backend package with four parts: shared column definitions, a file reader (bytes → raw rows, with size and safety limits), value normalisation, and an importer (validate with `StudentCreate`, diff against the DB, save in one transaction). Two Admin routes: `POST /api/students/import?commit=` (the same file uploaded twice, preview then commit, no server state) and `GET /api/students/import-template.xlsx`. The frontend adds a three-step modal and a browser-side "rows with errors" CSV with a formula-injection guard.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, Pydantic v2, openpyxl (+ defusedxml), XlsxWriter (already used), Vue 3 + Pinia + Tailwind, pytest, Vitest.

**Spec:** `docs/superpowers/specs/2026-10-16-student-file-import-design.md`

## Global Constraints

- Admin only: `require_role(UserRole.ADMIN)` on both routes; the UI button shows only for `currentUser.role === 'admin'`.
- Limits: **2 MB** per file (`413` "The file is larger than 2 MB."), **2,000** student rows, **25 MB** total uncompressed for .xlsx.
- File type by content: `PK\x03\x04` → xlsx; `D0 CF 11 E0` → old .xls (rejected with the Save As message); anything else must decode as text → CSV.
- openpyxl opens with `read_only=True, data_only=True`, first worksheet only; `defusedxml` must be installed.
- Email on import: format only (`EmailStr`); **never** call `validate_email_deliverable`.
- Flags: column absent or cell blank → keep the existing value (new students: No); only an explicit No clears one.
- Commit: all new + update rows in **one** transaction; invalid rows are never written.
- Audit on commit only: `student.bulk_imported`, `detail="new=…, updated=…, unchanged=…, invalid=…, file=xlsx|csv"`. No names, numbers or file names anywhere in logs.
- Remove the old JSON `POST /students/bulk-import`.
- Dependencies pinned with `==` in `backend/requirements.txt`: `openpyxl==3.1.5`, `et_xmlfile==<resolved>`, `defusedxml==0.7.1`. No new frontend dependency.
- Error CSV cells starting with `=`, `+`, `-`, `@`, tab or CR get a leading `'`.
- Never run `alembic upgrade head` against `DATABASE_URL` (the shared production DB). No migration is needed here.
- Backend tests run from `backend/` with `.venv/Scripts/python.exe -m pytest` (the DB is the disposable `bsu_queue_test`); frontend tests with `npm test` in `frontend/`.
- Several repo files use CRLF line endings. Keep each file's existing endings when editing.

---

## File Structure

| File | Responsibility |
|---|---|
| `backend/app/services/student_import/__init__.py` | Package exports |
| `backend/app/services/student_import/columns.py` | Canonical columns, labels, header aliases, `key()`, template example row |
| `backend/app/services/student_import/normalize.py` | Friendly value → enum / bool (pure) |
| `backend/app/services/student_import/reader.py` | Bytes → `ReadResult` (limits, xlsx/csv, headers, raw rows) |
| `backend/app/services/student_import/importer.py` | Validate, diff, commit → `StudentImportReport` |
| `backend/app/services/student_import/template.py` | Template .xlsx bytes |
| `backend/app/models/student_import.py` | Report response models |
| `backend/app/api/students.py` | New routes; remove `/bulk-import` |
| `backend/tests/test_student_import_*.py` | Tests per unit + API |
| `frontend/src/services/studentImportCsv.js` | Error-rows CSV with formula guard |
| `frontend/src/components/StudentImportModal.vue` | Three-step modal |
| `frontend/src/views/StudentManagementView.vue` | Admin button + modal wiring |
| `frontend/src/stores/queue.js` | `previewStudentImport` / `commitStudentImport` |

---

### Task 1: Dependencies, column definitions and value normalisation

**Files:**
- Modify: `backend/requirements.txt`
- Create: `backend/app/services/student_import/__init__.py`, `columns.py`, `normalize.py`
- Test: `backend/tests/test_student_import_normalize.py`

**Interfaces:**
- Produces: `columns.key(value) -> str`; `columns.COLUMNS: list[str]`, `REQUIRED: list[str]`, `FLAG_COLUMNS: list[str]`, `LABELS: dict[str,str]`, `ALIASES: dict[str,str]`, `EXAMPLE_ROW: dict[str,str]`; `normalize.NormalizeError(ValueError)`; `normalize.course(raw) -> Course`, `major(raw) -> Optional[Major]`, `student_type(raw) -> StudentType`, `year_level(raw) -> YearLevel`, `flag(raw) -> Optional[bool]` (enums from `app.models.student`).

- [ ] **Step 1: Pin the dependencies**

Add after the `XlsxWriter==…` line in `backend/requirements.txt`:

```
openpyxl==3.1.5  # read .xlsx student import files
et_xmlfile==2.0.0  # openpyxl dependency (pinned)
defusedxml==0.7.1  # openpyxl uses it automatically to block XML entity attacks
```

Run: `cd backend && .venv/Scripts/python.exe -m pip install openpyxl==3.1.5 defusedxml==0.7.1 && .venv/Scripts/python.exe -m pip show et_xmlfile`
If `et_xmlfile`'s version is not `2.0.0`, change the pin to the version shown.

- [ ] **Step 2: Write the failing tests**

`backend/tests/test_student_import_normalize.py`:

```python
import pytest

from app.models.student import Course, Major, StudentType, YearLevel
from app.services.student_import import columns, normalize


@pytest.mark.parametrize("raw, expected", [
    ("BSIT", Course.BSIT), ("bsit", Course.BSIT), ("B.S.I.T.", Course.BSIT),
    ("Bachelor of Science in Information Technology", Course.BSIT),
    ("BSCpE", Course.BSCPE), ("BSCPE", Course.BSCPE), ("BSEd", Course.BSED),
    ("BSHM", Course.BSHM), ("BSBA", Course.BSBA), ("BIT", Course.BIT),
])
def test_course(raw, expected):
    assert normalize.course(raw) == expected


@pytest.mark.parametrize("raw, expected", [
    ("1", YearLevel.FIRST), ("1st", YearLevel.FIRST), ("1st Year", YearLevel.FIRST),
    ("First Year", YearLevel.FIRST), ("1st_year", YearLevel.FIRST),
    ("3rd year", YearLevel.THIRD), ("5", YearLevel.FIFTH), ("Graduate", YearLevel.GRADUATE),
])
def test_year_level(raw, expected):
    assert normalize.year_level(raw) == expected


@pytest.mark.parametrize("raw, expected", [
    ("Undergraduate", StudentType.UNDERGRADUATE), ("undergrad", StudentType.UNDERGRADUATE),
    ("Graduate", StudentType.GRADUATE), ("grad", StudentType.GRADUATE),
    ("Alumni", StudentType.ALUMNI), ("alumnus", StudentType.ALUMNI),
])
def test_student_type(raw, expected):
    assert normalize.student_type(raw) == expected


@pytest.mark.parametrize("raw, expected", [
    ("", None), ("  ", None), ("CT", Major.COMPUTER_TECHNOLOGY),
    ("Computer Technology", Major.COMPUTER_TECHNOLOGY),
    ("BIT Computer Technology", Major.COMPUTER_TECHNOLOGY),
    ("FPT", Major.FOOD_PROCESSING_TECHNOLOGY), ("food processing technology", Major.FOOD_PROCESSING_TECHNOLOGY),
])
def test_major(raw, expected):
    assert normalize.major(raw) == expected


@pytest.mark.parametrize("raw, expected", [
    ("Yes", True), ("y", True), ("TRUE", True), ("1", True), ("✓", True),
    ("No", False), ("n", False), ("false", False), ("0", False),
    ("", None), ("   ", None),
])
def test_flag(raw, expected):
    assert normalize.flag(raw) is expected


@pytest.mark.parametrize("fn, raw", [
    (normalize.course, "BS Nursing"), (normalize.course, ""),
    (normalize.year_level, "6th year"), (normalize.student_type, "freshman"),
    (normalize.major, "Welding"), (normalize.flag, "maybe"),
])
def test_rejects_unknown_values(fn, raw):
    with pytest.raises(normalize.NormalizeError):
        fn(raw)


def test_header_aliases_resolve_to_canonical_columns():
    assert columns.ALIASES[columns.key("Student No.")] == "student_number"
    assert columns.ALIASES[columns.key("Email Address")] == "email"
    assert columns.ALIASES[columns.key("Year Level*")] == "year_level"
    assert columns.ALIASES[columns.key("Surname")] == "last_name"
    assert set(columns.REQUIRED) <= set(columns.COLUMNS)
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_student_import_normalize.py -q -p no:warnings`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.student_import'`.

- [ ] **Step 4: Implement**

`backend/app/services/student_import/__init__.py`:

```python
"""Admin student file import (.xlsx / .csv): read -> normalise -> validate -> diff -> save."""
```

`backend/app/services/student_import/columns.py`:

```python
"""Column definitions shared by the reader, importer and template."""
import re

# Canonical column keys, in template order.
COLUMNS = [
    "student_number", "first_name", "last_name", "email", "student_type",
    "course", "major", "year_level", "is_scholar", "is_varsity", "is_graduating",
]
REQUIRED = ["student_number", "first_name", "last_name", "email", "student_type", "course", "year_level"]
FLAG_COLUMNS = ["is_scholar", "is_varsity", "is_graduating"]

LABELS = {
    "student_number": "Student Number", "first_name": "First Name", "last_name": "Last Name",
    "email": "Email", "student_type": "Student Type", "course": "Course", "major": "Major",
    "year_level": "Year Level", "is_scholar": "Scholar", "is_varsity": "Varsity",
    "is_graduating": "Graduating",
}


def key(value) -> str:
    """Comparison key: lowercase letters and digits only ("Student No.*" -> "studentno")."""
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


ALIASES = {key(label): column for column, label in LABELS.items()}
ALIASES.update({
    key("Student No"): "student_number", key("Student ID"): "student_number",
    key("ID Number"): "student_number", key("Given Name"): "first_name",
    key("Surname"): "last_name", key("Family Name"): "last_name",
    key("Email Address"): "email", key("Type"): "student_type",
    key("Program"): "course", key("Year"): "year_level",
})

# The template's example row. The reader skips a data row equal to this.
EXAMPLE_ROW = {
    "student_number": "2026000001", "first_name": "Juan", "last_name": "Dela Cruz",
    "email": "juan.delacruz@example.com", "student_type": "Undergraduate", "course": "BSIT",
    "major": "", "year_level": "1st Year", "is_scholar": "No", "is_varsity": "No",
    "is_graduating": "No",
}
```

`backend/app/services/student_import/normalize.py`:

```python
"""Friendly spreadsheet values -> the system's enum values. Pure functions."""
from typing import Optional

from ...models.student import Course, Major, StudentType, YearLevel
from .columns import key


class NormalizeError(ValueError):
    pass


_COURSES = {key(c.value): c for c in Course}
_COURSES.update({key(code): course for code, course in {
    "BSIT": Course.BSIT, "BSHM": Course.BSHM, "BSBA": Course.BSBA,
    "BSCpE": Course.BSCPE, "BSEd": Course.BSED, "BIT": Course.BIT,
}.items()})

_MAJORS = {key(m.value): m for m in Major}
_MAJORS.update({
    key("CT"): Major.COMPUTER_TECHNOLOGY, key("Computer Technology"): Major.COMPUTER_TECHNOLOGY,
    key("FPT"): Major.FOOD_PROCESSING_TECHNOLOGY,
})

_TYPES = {
    "undergraduate": StudentType.UNDERGRADUATE, "undergrad": StudentType.UNDERGRADUATE,
    "graduate": StudentType.GRADUATE, "grad": StudentType.GRADUATE,
    "alumni": StudentType.ALUMNI, "alumnus": StudentType.ALUMNI, "alumna": StudentType.ALUMNI,
}

_YEARS = {"graduate": YearLevel.GRADUATE}
for _n, (_ord, _word, _level) in enumerate([
    ("1st", "first", YearLevel.FIRST), ("2nd", "second", YearLevel.SECOND),
    ("3rd", "third", YearLevel.THIRD), ("4th", "fourth", YearLevel.FOURTH),
    ("5th", "fifth", YearLevel.FIFTH),
], start=1):
    for _alias in (str(_n), _ord, f"{_ord}year", _word, f"{_word}year", f"year{_n}"):
        _YEARS[_alias] = _level

_YES = {"yes", "y", "true", "1"}
_NO = {"no", "n", "false", "0"}
_CHECKMARKS = {"✓", "✔"}


def _lookup(table, raw, message):
    found = table.get(key(raw))
    if found is None:
        raise NormalizeError(message.format(raw=str(raw).strip()))
    return found


def course(raw) -> Course:
    return _lookup(_COURSES, raw, "'{raw}' is not a course offered here.")


def major(raw) -> Optional[Major]:
    if not str(raw or "").strip():
        return None
    return _lookup(_MAJORS, raw, "'{raw}' is not a BIT major.")


def student_type(raw) -> StudentType:
    return _lookup(_TYPES, raw, "'{raw}' is not a student type (Undergraduate, Graduate or Alumni).")


def year_level(raw) -> YearLevel:
    return _lookup(_YEARS, raw, "'{raw}' is not a year level (1st–5th Year or Graduate).")


def flag(raw) -> Optional[bool]:
    """True / False, or None for a blank cell (meaning: keep the current value)."""
    text = str(raw or "").strip()
    if not text:
        return None
    if text in _CHECKMARKS or key(text) in _YES:
        return True
    if key(text) in _NO:
        return False
    raise NormalizeError(f"'{text}' should be Yes or No.")
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_student_import_normalize.py -q -p no:warnings`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add backend/requirements.txt backend/app/services/student_import backend/tests/test_student_import_normalize.py
git commit -m "Add student import column definitions and value normalisation"
```

---

### Task 2: File reader with limits and safety checks

**Files:**
- Create: `backend/app/services/student_import/reader.py`
- Test: `backend/tests/test_student_import_reader.py`

**Interfaces:**
- Consumes: `columns.COLUMNS`, `REQUIRED`, `LABELS`, `ALIASES`, `EXAMPLE_ROW`, `key()` (Task 1).
- Produces: `reader.MAX_BYTES = 2*1024*1024`, `MAX_ROWS = 2000`, `MAX_UNZIPPED = 25*1024*1024`; `class ImportFileError(ValueError)` with `.status: int` (400 or 413); `@dataclass RawRow(row: int, values: dict[str, str], original: dict[str, str])` where `values` is keyed by canonical column (missing optional columns are absent) and `original` by the file's header text; `@dataclass ReadResult(file_type: str, headers: list[str], ignored_columns: list[str], rows: list[RawRow])`; `read_upload(data: bytes) -> ReadResult`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_student_import_reader.py`:

```python
import io
import zipfile

import openpyxl.xml
import pytest
import xlsxwriter

from app.services.student_import import reader
from app.services.student_import.columns import EXAMPLE_ROW, LABELS

HEADER = ["Student Number", "First Name", "Last Name", "Email", "Student Type", "Course", "Year Level"]
ROW = ["2021000001", "Juan", "Dela Cruz", "juan@example.com", "Undergraduate", "BSIT", "1st Year"]


def make_xlsx(rows) -> bytes:
    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True})
    ws = wb.add_worksheet()
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            ws.write(r, c, value)
    wb.close()
    return buf.getvalue()


def make_csv(rows, sep=",", encoding="utf-8") -> bytes:
    return "\r\n".join(sep.join(r) for r in rows).encode(encoding)


def test_defusedxml_is_active():
    assert openpyxl.xml.DEFUSEDXML is True


@pytest.mark.parametrize("data, file_type", [
    (make_xlsx([HEADER, ROW]), "xlsx"),
    (make_csv([HEADER, ROW]), "csv"),
    (make_csv([HEADER, ROW], sep=";"), "csv"),
    (b"\xef\xbb\xbf" + make_csv([HEADER, ROW]), "csv"),
])
def test_xlsx_and_csv_read_the_same_rows(data, file_type):
    result = reader.read_upload(data)
    assert result.file_type == file_type
    assert len(result.rows) == 1
    row = result.rows[0]
    assert row.row == 2
    assert row.values["student_number"] == "2021000001"
    assert row.values["course"] == "BSIT"
    assert row.original["First Name"] == "Juan"


def test_cp1252_csv_is_decoded():
    data = make_csv([HEADER, ["2021000001", "José", "Peña", "j@example.com", "Undergraduate", "BSIT", "1"]],
                    encoding="cp1252")
    assert reader.read_upload(data).rows[0].values["first_name"] == "José"


def test_header_aliases_star_and_case_and_ignored_columns():
    header = ["student no.*", "FIRST NAME*", "Surname", "Email Address", "Type", "Program", "Year", "Section"]
    result = reader.read_upload(make_csv([header, ROW + ["A"]]))
    assert result.rows[0].values["last_name"] == "Dela Cruz"
    assert result.ignored_columns == ["Section"]


def test_missing_required_column_names_it():
    with pytest.raises(reader.ImportFileError, match="Email") as e:
        reader.read_upload(make_csv([[h for h in HEADER if h != "Email"], ROW[:3] + ROW[4:]]))
    assert e.value.status == 400


def test_blank_rows_and_template_example_are_skipped():
    example = [EXAMPLE_ROW[c] for c in ["student_number", "first_name", "last_name", "email",
                                         "student_type", "course", "year_level"]]
    result = reader.read_upload(make_csv([HEADER, example, ["", "", ""], ROW]))
    assert [r.row for r in result.rows] == [4]


def test_numeric_student_number_from_excel_becomes_ten_digit_text():
    result = reader.read_upload(make_xlsx([HEADER, [2021000001] + ROW[1:]]))
    assert result.rows[0].values["student_number"] == "2021000001"


def test_formula_cells_are_never_evaluated():
    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True})
    ws = wb.add_worksheet()
    ws.write_row(0, 0, HEADER)
    ws.write_row(1, 0, ROW)
    ws.write_formula(1, 1, '=HYPERLINK("http://evil","x")', None, "Juan")
    wb.close()
    assert reader.read_upload(buf.getvalue()).rows[0].values["first_name"] == "Juan"


def test_too_many_rows():
    rows = [HEADER] + [[f"{2021000000 + i}"] + ROW[1:] for i in range(reader.MAX_ROWS + 1)]
    with pytest.raises(reader.ImportFileError, match="2,000"):
        reader.read_upload(make_csv(rows))


def test_too_large():
    with pytest.raises(reader.ImportFileError) as e:
        reader.read_upload(b"a" * (reader.MAX_BYTES + 1))
    assert e.value.status == 413


@pytest.mark.parametrize("data, message", [
    (b"", "empty"),
    (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 100, "Excel 97"),
    (b"PK\x03\x04garbage", "valid Excel"),
    (b"\x00\x01\x02\x03binary", "Excel or CSV"),
])
def test_unreadable_files_get_clear_messages(data, message):
    with pytest.raises(reader.ImportFileError, match=message):
        reader.read_upload(data)


def test_zip_bomb_is_rejected():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("xl/huge.xml", b"0" * (reader.MAX_UNZIPPED + 1))
    with pytest.raises(reader.ImportFileError, match="too large"):
        reader.read_upload(buf.getvalue())
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_student_import_reader.py -q -p no:warnings`
Expected: FAIL with `ImportError: cannot import name 'reader'`.

- [ ] **Step 3: Implement**

`backend/app/services/student_import/reader.py`:

```python
"""Uploaded bytes -> raw rows. Knows file formats and limits, not students.

Safety: the type is decided by content, not the file name; .xlsx is
checked for a zip bomb before openpyxl opens it; openpyxl uses defusedxml
(installed) against XML entity attacks and is opened read-only with
data_only=True, so formulas are never evaluated.
"""
import csv
import datetime as dt
import io
import zipfile
from dataclasses import dataclass, field

import openpyxl

from .columns import ALIASES, EXAMPLE_ROW, LABELS, REQUIRED, key

MAX_BYTES = 2 * 1024 * 1024
MAX_ROWS = 2000
MAX_UNZIPPED = 25 * 1024 * 1024
# Stop collecting once this many non-blank rows are seen - enough to know
# the file is over the limit (header + example + MAX_ROWS + 1).
_COLLECT_LIMIT = MAX_ROWS + 3


class ImportFileError(ValueError):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


@dataclass
class RawRow:
    row: int                                   # 1-based row number in the sheet
    values: dict[str, str]                     # canonical column -> cell text
    original: dict[str, str] = field(default_factory=dict)  # file header -> cell text


@dataclass
class ReadResult:
    file_type: str
    headers: list[str]
    ignored_columns: list[str]
    rows: list[RawRow]


def read_upload(data: bytes) -> ReadResult:
    if len(data) > MAX_BYTES:
        raise ImportFileError("The file is larger than 2 MB.", status=413)
    if not data.strip():
        raise ImportFileError("The file is empty.")
    if data[:4] == b"PK\x03\x04":
        return _to_result(_read_xlsx(data), "xlsx")
    if data[:4] == b"\xd0\xcf\x11\xe0":
        raise ImportFileError(
            "This is an old Excel 97–2003 file. Open it in Excel and Save As .xlsx or .csv.")
    return _to_result(_read_csv(data), "csv")


def _cell_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else str(value)
    if isinstance(value, (dt.datetime, dt.date)):
        return value.isoformat()
    return str(value).strip()


def _collect(rows_iter) -> list[list[str]]:
    table, nonblank = [], 0
    for row in rows_iter:
        cells = [_cell_text(v) for v in row]
        table.append(cells)
        if any(cells):
            nonblank += 1
            if nonblank >= _COLLECT_LIMIT:
                break
    return table


def _read_xlsx(data: bytes) -> list[list[str]]:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            if sum(info.file_size for info in z.infolist()) > MAX_UNZIPPED:
                raise ImportFileError("This Excel file is too large once unpacked.")
    except zipfile.BadZipFile:
        raise ImportFileError("This file isn't a valid Excel (.xlsx) file.")
    try:
        wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception:
        raise ImportFileError("This file isn't a valid Excel (.xlsx) file.")
    try:
        return _collect(wb.worksheets[0].iter_rows(values_only=True))
    finally:
        wb.close()


def _read_csv(data: bytes) -> list[list[str]]:
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            text = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ImportFileError("Couldn't read this file as Excel or CSV.")
    if "\x00" in text:
        raise ImportFileError("Couldn't read this file as Excel or CSV.")
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    return _collect(csv.reader(io.StringIO(text), dialect))


def _to_result(table: list[list[str]], file_type: str) -> ReadResult:
    numbered = [(i + 1, cells) for i, cells in enumerate(table) if any(cells)]
    if not numbered:
        raise ImportFileError("The file is empty.")
    _, header = numbered[0]

    columns, seen, ignored, headers = [], set(), [], []
    for i, title in enumerate(header):
        headers.append(title or f"Column {i + 1}")
        canonical = ALIASES.get(key(title))
        if canonical and canonical not in seen:
            columns.append(canonical)
            seen.add(canonical)
        else:
            columns.append(None)
            if title:
                ignored.append(title)
    missing = [LABELS[c] for c in REQUIRED if c not in seen]
    if missing:
        raise ImportFileError(f"Missing required column(s): {', '.join(missing)}. "
                              "Download the template to see the expected headers.")

    rows = []
    for row_number, cells in numbered[1:]:
        cells = cells + [""] * (len(columns) - len(cells))
        values = {c: cells[i] for i, c in enumerate(columns) if c}
        if all(values.get(c, "") == EXAMPLE_ROW[c] for c in values):
            continue
        rows.append(RawRow(row=row_number, values=values,
                           original={headers[i]: cells[i] for i in range(len(headers))}))
    if len(rows) > MAX_ROWS:
        raise ImportFileError(
            "The file has more than 2,000 students; the limit is 2,000 per import. "
            "Split it into smaller files.")
    return ReadResult(file_type=file_type, headers=headers, ignored_columns=ignored, rows=rows)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_student_import_reader.py -q -p no:warnings`
Expected: all pass. If `test_defusedxml_is_active` fails, `defusedxml` isn't installed in the venv; redo Task 1 Step 1.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/student_import/reader.py backend/tests/test_student_import_reader.py
git commit -m "Read student import files (.xlsx/.csv) with size, row and zip limits"
```

---

### Task 3: Report models and the importer

**Files:**
- Create: `backend/app/models/student_import.py`, `backend/app/services/student_import/importer.py`
- Test: `backend/tests/test_student_import_importer.py`

**Interfaces:**
- Consumes: `ReadResult`, `RawRow` (Task 2); `normalize.*`, `NormalizeError` (Task 1); `StudentCreate` (`app.models.student`); `StudentDB`, `StudentDBType`, `Course`, `Major`, `YearLevel` (`app.db_models`).
- Produces: `ImportRowProblem(row: int, student_number: str, column: str, message: str, values: dict[str, str])`; `ImportChange(row: int, student_number: str, name: str, action: Literal["new","update"], fields: dict[str, list[str]])`; `StudentImportReport(committed: bool, file_type: str, total_rows: int, new: int, updated: int, unchanged: int, invalid: int, columns: list[str], ignored_columns: list[str], problems: list[ImportRowProblem], changes: list[ImportChange])`; `StudentImporter(db).run(read: ReadResult, commit: bool) -> StudentImportReport`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_student_import_importer.py`:

```python
import pytest

from app.db_models import Course, StudentDB, StudentDBType, YearLevel
from app.services import student_service
from app.services.student_import.importer import StudentImporter
from app.services.student_import.reader import RawRow, ReadResult

BASE = {
    "student_number": "2031000001", "first_name": "Ana", "last_name": "Reyes",
    "email": "ana.reyes@example.com", "student_type": "Undergraduate", "course": "BSIT",
    "year_level": "1st Year",
}


def read(*rows) -> ReadResult:
    raw = [RawRow(row=i + 2, values=dict(r), original={k: v for k, v in r.items()})
           for i, r in enumerate(rows)]
    return ReadResult(file_type="csv", headers=list(BASE), ignored_columns=[], rows=raw)


@pytest.fixture(autouse=True)
def no_mx_check(monkeypatch):
    def fail(email):
        raise AssertionError("imports must not run the live MX check")
    monkeypatch.setattr(student_service, "validate_email_deliverable", fail)


def count(db):
    return db.query(StudentDB).filter(StudentDB.student_id.like("2031%")).count()


def existing(db, number, first="Ana", last="Reyes", email="ana.reyes@example.com", **extra):
    """An existing student, inserted directly - make_student would run the
    live MX check, which the no_mx_check fixture deliberately breaks."""
    row = StudentDB(student_id=number, first_name=first, last_name=last, email=email,
                    student_type=StudentDBType.UNDERGRADUATE, course=Course.BSIT,
                    year_level=YearLevel.FIRST, **extra)
    db.add(row)
    db.commit()
    return row


def test_preview_classifies_and_writes_nothing(db_session):
    existing(db_session, "2031000002", first="Ben", last="Cruz", email="ben@gmail.com")
    existing(db_session, "2031000003", first="Cy", last="Lim", email="cy@gmail.com")
    report = StudentImporter(db_session).run(read(
        BASE,                                                         # new
        {**BASE, "student_number": "2031000002", "first_name": "Ben", "last_name": "Cruz",
         "email": "ben@gmail.com", "year_level": "2nd Year"},          # update
        {**BASE, "student_number": "2031000003", "first_name": "Cy", "last_name": "Lim",
         "email": "cy@gmail.com"},                                     # unchanged
        {**BASE, "student_number": "123"},                             # invalid
    ), commit=False)

    assert (report.new, report.updated, report.unchanged, report.invalid) == (1, 1, 1, 1)
    assert report.committed is False
    assert report.total_rows == 4
    update = next(c for c in report.changes if c.action == "update")
    assert update.fields == {"year_level": ["1st Year", "2nd Year"]}
    problem = report.problems[0]
    assert (problem.row, problem.column) == (5, "Student Number")
    assert problem.values["student_number"] == "123"
    assert count(db_session) == 2


def test_commit_saves_new_and_updated_rows(db_session):
    existing(db_session, "2031000002", email="ben@gmail.com")
    report = StudentImporter(db_session).run(read(
        BASE, {**BASE, "student_number": "2031000002", "email": "ben@gmail.com", "course": "BSHM"},
    ), commit=True)

    assert report.committed is True and (report.new, report.updated) == (1, 1)
    db_session.expire_all()
    updated = db_session.query(StudentDB).filter_by(student_id="2031000002").one()
    assert updated.course.value == "Bachelor of Science in Hospitality Management"
    assert db_session.query(StudentDB).filter_by(student_id="2031000001").one().first_name == "Ana"


def test_duplicate_student_number_points_to_first_row(db_session):
    report = StudentImporter(db_session).run(read(BASE, BASE), commit=False)
    assert report.new == 1 and report.invalid == 1
    assert report.problems[0].message == "Student number also appears in row 2."


@pytest.mark.parametrize("row, column, fragment", [
    ({**BASE, "course": "BS Nursing"}, "Course", "not a course"),
    ({**BASE, "email": "not-an-email"}, "Email", "valid email"),
    ({**BASE, "first_name": ""}, "First Name", "Required"),
    ({**BASE, "course": "BIT"}, "Major", "major is required"),
    ({**BASE, "major": "CT"}, "Major", "only applicable"),
    ({**BASE, "student_number": "2.031E+09"}, "Student Number", "changed by Excel"),
    ({**BASE, "is_scholar": "maybe"}, "Scholar", "Yes or No"),
])
def test_row_errors_name_the_column(db_session, row, column, fragment):
    report = StudentImporter(db_session).run(read(row), commit=False)
    assert report.invalid == 1
    assert report.problems[0].column == column
    assert fragment in report.problems[0].message


def test_flag_rules(db_session):
    existing(db_session, "2031000002", email="ben@gmail.com", is_scholar=True)
    base = {**BASE, "student_number": "2031000002", "email": "ben@gmail.com"}

    # Column absent / blank cell: keep the current value -> unchanged.
    assert StudentImporter(db_session).run(read(base), commit=False).unchanged == 1
    assert StudentImporter(db_session).run(read({**base, "is_scholar": ""}), commit=False).unchanged == 1
    # Explicit No clears it.
    report = StudentImporter(db_session).run(read({**base, "is_scholar": "No"}), commit=True)
    assert report.changes[0].fields == {"is_scholar": ["Yes", "No"]}
    # New students default to No; Yes sets it.
    report = StudentImporter(db_session).run(read({**BASE, "is_graduating": "Yes"}), commit=True)
    db_session.expire_all()
    new = db_session.query(StudentDB).filter_by(student_id="2031000001").one()
    assert (new.is_graduating, new.is_scholar) == (True, False)


def test_commit_is_all_or_nothing(db_session, monkeypatch):
    def boom():
        raise RuntimeError("connection lost")
    monkeypatch.setattr(db_session, "commit", boom)
    with pytest.raises(RuntimeError):
        StudentImporter(db_session).run(read(BASE, {**BASE, "student_number": "2031000009"}), commit=True)
    monkeypatch.undo()
    assert count(db_session) == 0
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_student_import_importer.py -q -p no:warnings`
Expected: FAIL with `ModuleNotFoundError: ... importer`.

- [ ] **Step 3: Implement the report models**

`backend/app/models/student_import.py`:

```python
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
```

- [ ] **Step 4: Implement the importer**

`backend/app/services/student_import/importer.py`:

```python
"""Validate raw rows with the app's own StudentCreate rules, diff against the
database, and (on commit) save every new/updated row in one transaction.

The live MX email check (student_service.validate_email_deliverable) is
deliberately NOT used: the file is the registrar's own record, and 2,000
DNS lookups would take ~30 minutes. Format is still checked (EmailStr).
"""
import re
from typing import Optional

from pydantic import ValidationError
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
        except Exception:
            self.db.rollback()
            raise
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_student_import_importer.py -q -p no:warnings`
Expected: all pass. (`no_mx_check` makes any call to the live MX check fail the test, proving imports never use it.)

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/student_import.py backend/app/services/student_import/importer.py backend/tests/test_student_import_importer.py
git commit -m "Validate, diff and save imported students in one transaction"
```

---

### Task 4: Downloadable template

**Files:**
- Create: `backend/app/services/student_import/template.py`
- Test: `backend/tests/test_student_import_template.py`

**Interfaces:**
- Consumes: `COLUMNS`, `REQUIRED`, `LABELS`, `EXAMPLE_ROW` (Task 1); `read_upload` (Task 2).
- Produces: `template.build_template() -> bytes` (.xlsx).

- [ ] **Step 1: Write the failing test**

`backend/tests/test_student_import_template.py`:

```python
import io

import openpyxl

from app.services.student_import import reader, template
from app.services.student_import.columns import COLUMNS, LABELS, REQUIRED


def test_template_has_headers_example_and_dropdowns():
    data = template.build_template()
    wb = openpyxl.load_workbook(io.BytesIO(data))
    ws = wb["Students"]
    headers = [c.value for c in ws[1]]
    assert headers == [LABELS[c] + ("*" if c in REQUIRED else "") for c in COLUMNS]
    assert ws.cell(row=2, column=1).value == "2026000001"
    assert ws.cell(row=2, column=1).number_format == "@"
    sqrefs = " ".join(str(dv.sqref) for dv in ws.data_validations.dataValidation)
    assert "F2" in sqrefs and "H2" in sqrefs            # Course, Year Level dropdowns
    assert "Instructions" in wb.sheetnames


def test_untouched_template_imports_as_zero_rows():
    assert reader.read_upload(template.build_template()).rows == []
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_student_import_template.py -q -p no:warnings`
Expected: FAIL with `ImportError: cannot import name 'template'`.

- [ ] **Step 3: Implement**

`backend/app/services/student_import/template.py`:

```python
"""The downloadable student import template (.xlsx)."""
import io

import xlsxwriter

from .columns import COLUMNS, EXAMPLE_ROW, LABELS, REQUIRED

_DROPDOWNS = {
    "student_type": ["Undergraduate", "Graduate", "Alumni"],
    "course": ["BSIT", "BSHM", "BSBA", "BSCpE", "BSEd", "BIT"],
    "major": ["Computer Technology", "Food Processing Technology"],
    "year_level": ["1st Year", "2nd Year", "3rd Year", "4th Year", "5th Year", "Graduate"],
    "is_scholar": ["Yes", "No"], "is_varsity": ["Yes", "No"], "is_graduating": ["Yes", "No"],
}
_WIDTHS = {"student_number": 16, "email": 30, "course": 12, "major": 26, "year_level": 12}
_INSTRUCTIONS = [
    ("How to use", "Fill one student per row on the Students sheet, delete the grey example row, "
                   "then upload the file in Student Management → Import Students."),
    ("Limits", "Up to 2,000 students and 2 MB per file. Save as .xlsx or .csv."),
    ("Required (*)", "Student Number, First Name, Last Name, Email, Student Type, Course, Year Level."),
    ("Student Number", "Exactly 10 digits. Keep this column formatted as Text."),
    ("Student Type", "Undergraduate, Graduate or Alumni."),
    ("Course", "BSIT, BSHM, BSBA, BSCpE, BSEd or BIT (full course names also work)."),
    ("Major", "Only for BIT: Computer Technology or Food Processing Technology. Leave blank otherwise."),
    ("Year Level", "1st–5th Year (or 1–5), or Graduate."),
    ("Scholar / Varsity / Graduating", "Optional. Yes or No. A blank cell keeps the student's current "
                                       "value (No for new students); only No removes a priority."),
    ("Existing students", "A student number already in the system updates that student with "
                          "the values in this file. Students missing from the file are not changed."),
]


def build_template() -> bytes:
    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True, "strings_to_numbers": False,
                                   "strings_to_formulas": False, "strings_to_urls": False})
    ws = wb.add_worksheet("Students")
    head = wb.add_format({"bold": True, "bg_color": "#F2A0BC", "border": 1})
    text = wb.add_format({"num_format": "@"})
    example = wb.add_format({"italic": True, "font_color": "#808080", "num_format": "@"})

    for col, column in enumerate(COLUMNS):
        ws.set_column(col, col, _WIDTHS.get(column, 14), text)
        ws.write_string(0, col, LABELS[column] + ("*" if column in REQUIRED else ""), head)
        ws.write_string(1, col, EXAMPLE_ROW[column], example)
        if column in _DROPDOWNS:
            ws.data_validation(1, col, 2001, col, {"validate": "list", "source": _DROPDOWNS[column]})
    ws.write_comment(1, 0, "Example row - delete it before importing.")
    ws.freeze_panes(1, 0)

    info = wb.add_worksheet("Instructions")
    bold = wb.add_format({"bold": True, "valign": "top"})
    wrap = wb.add_format({"text_wrap": True, "valign": "top"})
    info.set_column(0, 0, 28)
    info.set_column(1, 1, 90)
    for r, (label, body) in enumerate(_INSTRUCTIONS):
        info.write_string(r, 0, label, bold)
        info.write_string(r, 1, body, wrap)
    wb.close()
    return buf.getvalue()
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_student_import_template.py -q -p no:warnings`
Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/student_import/template.py backend/tests/test_student_import_template.py
git commit -m "Add the downloadable student import template"
```

---

### Task 5: API routes (and removal of the JSON bulk import)

**Files:**
- Modify: `backend/app/api/students.py` (add the routes **above** `@router.get("/{student_id}")` at line ~63; delete `bulk_import_students`, lines ~150–179)
- Modify: `backend/app/models/student.py` (docstrings that mention "bulk-import"), `backend/tests/test_student_priority_trust.py` (module docstring)
- Test: `backend/tests/test_student_import_api.py`

**Interfaces:**
- Consumes: `read_upload`, `ImportFileError`, `MAX_BYTES` (Task 2); `StudentImporter` (Task 3); `build_template` (Task 4); `StudentImportReport` (Task 3).
- Produces: `POST /api/students/import?commit=false|true` (multipart field `file`) → `StudentImportReport`; `GET /api/students/import-template.xlsx` → .xlsx.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_student_import_api.py`:

```python
import json
import logging

import pytest

from app.db_models import StudentDB, UserRole
from app.services import student_service

CSV = ("Student Number,First Name,Last Name,Email,Student Type,Course,Year Level\r\n"
       "2032000001,Ana,Reyes,ana@example.com,Undergraduate,BSIT,1st Year\r\n"
       "123,Bad,Row,bad@example.com,Undergraduate,BSIT,1st Year\r\n").encode()


def _login(client, user):
    return client.post("/api/auth/login", data={"username": user.username, "password": user._plain_password})


def _upload(client, commit, data=CSV, name="students.csv"):
    return client.post("/api/students/import", params={"commit": str(commit).lower()},
                       files={"file": (name, data, "text/csv")})


@pytest.fixture(autouse=True)
def no_mx(monkeypatch):
    monkeypatch.setattr(student_service, "validate_email_deliverable",
                        lambda e: (_ for _ in ()).throw(AssertionError("no MX on import")))


def test_admin_previews_then_commits(client, db_session, make_user):
    _login(client, make_user(role=UserRole.ADMIN))

    preview = _upload(client, False)
    assert preview.status_code == 200
    assert (preview.json()["new"], preview.json()["invalid"]) == (1, 1)
    assert db_session.query(StudentDB).filter_by(student_id="2032000001").count() == 0

    logger = logging.getLogger("bsu.security")
    messages = []
    handler = logging.Handler()
    handler.emit = lambda record: messages.append(record.getMessage())
    logger.addHandler(handler)
    try:
        committed = _upload(client, True)
    finally:
        logger.removeHandler(handler)
    assert committed.status_code == 200 and committed.json()["committed"] is True
    assert db_session.query(StudentDB).filter_by(student_id="2032000001").count() == 1
    events = [json.loads(m) for m in messages]
    imported = [e for e in events if e["event"] == "student.bulk_imported"]
    assert imported and imported[0]["detail"] == "new=1, updated=0, unchanged=0, invalid=1, file=csv"
    assert "Reyes" not in json.dumps(imported) and "students.csv" not in json.dumps(imported)


@pytest.mark.parametrize("role", [UserRole.REGISTRAR, UserRole.STAFF])
def test_non_admins_are_refused(client, make_user, role):
    _login(client, make_user(role=role))
    assert _upload(client, False).status_code == 403
    assert client.get("/api/students/import-template.xlsx").status_code == 403


def test_anonymous_is_refused(client):
    assert _upload(client, False).status_code == 401


def test_file_errors_use_detail(client, make_user):
    _login(client, make_user(role=UserRole.ADMIN))
    too_big = _upload(client, False, data=b"a" * (2 * 1024 * 1024 + 1))
    assert too_big.status_code == 413 and too_big.json()["detail"] == "The file is larger than 2 MB."
    missing = _upload(client, False, data=b"Name\r\nAna\r\n")
    assert missing.status_code == 400 and "Missing required column" in missing.json()["detail"]


def test_template_download(client, make_user):
    _login(client, make_user(role=UserRole.ADMIN))
    r = client.get("/api/students/import-template.xlsx")
    assert r.status_code == 200
    assert r.content[:4] == b"PK\x03\x04"
    assert 'filename="students_import_template.xlsx"' in r.headers["content-disposition"]


def test_old_json_bulk_import_is_gone(client, make_user):
    _login(client, make_user(role=UserRole.ADMIN))
    assert client.post("/api/students/bulk-import", json=[]).status_code in (404, 405)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_student_import_api.py -q -p no:warnings`
Expected: FAIL (`/api/students/import` returns 405/422; the template path returns 422 because `/{student_id}` catches it).

- [ ] **Step 3: Implement the routes**

In `backend/app/api/students.py`, change the imports:

```python
from fastapi import APIRouter, Depends, File, HTTPException, Path, Query, Request, Response, UploadFile
```

and add:

```python
from ..models.student_import import StudentImportReport
from ..services.student_import.importer import StudentImporter
from ..services.student_import.reader import MAX_BYTES, ImportFileError, read_upload
from ..services.student_import.template import build_template
```

Insert **immediately above** `@router.get("/{student_id}", response_model=Student)`:

```python
@router.post("/import", response_model=StudentImportReport)
@limiter.limit("20/minute")
def import_students(
    request: Request,
    file: UploadFile = File(...),
    commit: bool = Query(False, description="false: preview only; true: save the valid rows"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Import students from an .xlsx/.csv file (admin only).

    The same file is sent twice: commit=false returns the preview and saves
    nothing; commit=true re-checks it and saves the valid rows."""
    data = file.file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="The file is larger than 2 MB.")
    try:
        table = read_upload(data)
    except ImportFileError as e:
        raise HTTPException(status_code=e.status, detail=str(e))

    report = StudentImporter(db).run(table, commit=commit)
    if commit:
        # Counts only - never names, student numbers or the file name.
        log_security_event(
            "student.bulk_imported", outcome="success", request=request,
            actor=current_user.username,
            detail=(f"new={report.new}, updated={report.updated}, unchanged={report.unchanged}, "
                    f"invalid={report.invalid}, file={report.file_type}"),
        )
    return report


@router.get("/import-template.xlsx")
def download_import_template(
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """The student import template (admin only)."""
    return Response(
        content=build_template(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="students_import_template.xlsx"'},
    )
```

Delete the whole `@router.post("/bulk-import")` route (`bulk_import_students`). If `List` or `StudentCreate` become unused in `students.py`, remove them from the imports.

- [ ] **Step 4: Update the docstrings that mention bulk-import**

In `backend/app/models/student.py`, `StudentBase`'s docstring: replace `the registrar-gated PATCH and the admin-only bulk-import` with `the registrar-gated PATCH and the admin-only file import`.
In `backend/tests/test_student_priority_trust.py`, line 4: replace `or an admin bulk-import.` with `or the admin file import.`

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_student_import_api.py tests/test_student_priority_trust.py -q -p no:warnings`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/students.py backend/app/models/student.py backend/tests/test_student_import_api.py backend/tests/test_student_priority_trust.py
git commit -m "Add admin student file import and template routes; drop the JSON bulk import"
```

---

### Task 6: Error-rows CSV builder (frontend)

**Files:**
- Create: `frontend/src/services/studentImportCsv.js`
- Test: `frontend/src/services/__tests__/studentImportCsv.spec.js`

**Interfaces:**
- Consumes: `StudentImportReport.columns` and `.problems[]` (`{row, column, message, values}`) from Task 3.
- Produces: `csvCell(value) -> string`; `buildErrorCsv(columns: string[], problems: object[]) -> string` (starts with a UTF-8 BOM, CRLF line endings).

- [ ] **Step 1: Write the failing test**

`frontend/src/services/__tests__/studentImportCsv.spec.js`:

```js
import { describe, expect, it } from 'vitest'
import { buildErrorCsv, csvCell } from '../studentImportCsv'

describe('csvCell', () => {
  it('guards formula-like cells', () => {
    for (const v of ['=SUM(A1)', '+1', '-1', '@x', '\tx', '\rx']) {
      expect(csvCell(v).startsWith("'") || csvCell(v).startsWith(`"'`)).toBe(true)
    }
    expect(csvCell('Juan')).toBe('Juan')
  })

  it('quotes commas, quotes and newlines', () => {
    expect(csvCell('Dela Cruz, Jr.')).toBe('"Dela Cruz, Jr."')
    expect(csvCell('say "hi"')).toBe('"say ""hi"""')
    expect(csvCell('a\nb')).toBe('"a\nb"')
  })
})

describe('buildErrorCsv', () => {
  it('keeps the original columns and adds Row and Error', () => {
    const csv = buildErrorCsv(['Student Number', 'First Name'], [
      { row: 5, column: 'Student Number', message: 'Must be exactly 10 digits.',
        values: { 'Student Number': '123', 'First Name': '=HYPERLINK("x")' } },
    ])
    const lines = csv.replace(/^﻿/, '').split('\r\n')
    expect(lines[0]).toBe('Student Number,First Name,Row,Error')
    expect(lines[1]).toBe(`123,"'=HYPERLINK(""x"")",5,Student Number: Must be exactly 10 digits.`)
    expect(csv.startsWith('﻿')).toBe(true)
  })
})
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd frontend && npx vitest run src/services/__tests__/studentImportCsv.spec.js`
Expected: FAIL (module not found).

- [ ] **Step 3: Implement**

`frontend/src/services/studentImportCsv.js`:

```js
// "Rows with errors" download for the student import. Built in the browser
// from the import report, meant to be opened in Excel - so any cell Excel
// would treat as a formula (= + - @ tab CR) gets a leading ' (CSV injection
// guard), and cells with commas/quotes/newlines are quoted.

const FORMULA_START = /^[=+\-@\t\r]/

export function csvCell(value) {
  let text = value == null ? '' : String(value)
  if (FORMULA_START.test(text)) text = `'${text}`
  return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text
}

export function buildErrorCsv(columns, problems) {
  const header = [...columns, 'Row', 'Error']
  const lines = [header.map(csvCell).join(',')]
  for (const p of problems) {
    const cells = columns.map((c) => p.values?.[c] ?? '')
    lines.push([...cells, p.row, `${p.column}: ${p.message}`].map(csvCell).join(','))
  }
  // BOM so Excel opens UTF-8 names (ñ, é) correctly.
  return '﻿' + lines.join('\r\n')
}
```

- [ ] **Step 4: Run it to verify it passes**

Run: `cd frontend && npx vitest run src/services/__tests__/studentImportCsv.spec.js`
Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/services/studentImportCsv.js frontend/src/services/__tests__/studentImportCsv.spec.js
git commit -m "Build the student import error CSV with a formula-injection guard"
```

---

### Task 7: Store actions

**Files:**
- Modify: `frontend/src/stores/queue.js` (STUDENT ACTIONS section)
- Test: `frontend/src/stores/__tests__/queue.spec.js`

**Interfaces:**
- Produces: `previewStudentImport(file: File) -> Promise<StudentImportReport>`, `commitStudentImport(file: File) -> Promise<StudentImportReport>`.

- [ ] **Step 1: Write the failing test**

Append to `frontend/src/stores/__tests__/queue.spec.js` (it already defines `mockApi`, `ok`, `useQueueStore`):

```js
describe('student import actions', () => {
  it('previewStudentImport posts the file with commit=false and a long timeout', async () => {
    mockApi.post.mockReturnValueOnce(ok({ new: 2 }))
    const store = useQueueStore()
    const file = new File(['a,b'], 'students.csv', { type: 'text/csv' })

    const report = await store.previewStudentImport(file)

    const [url, body, config] = mockApi.post.mock.calls.at(-1)
    expect(url).toBe('/students/import')
    expect(body).toBeInstanceOf(FormData)
    expect(body.get('file').name).toBe('students.csv')
    expect(config).toEqual({ params: { commit: false }, timeout: 120000 })
    expect(report.new).toBe(2)
  })

  it('commitStudentImport sends commit=true and surfaces the detail on error', async () => {
    mockApi.post.mockReturnValueOnce(Promise.reject({ response: { data: { detail: 'The file is larger than 2 MB.' } } }))
    const store = useQueueStore()

    await expect(store.commitStudentImport(new File(['x'], 's.csv'))).rejects.toBeTruthy()
    expect(mockApi.post.mock.calls.at(-1)[2].params.commit).toBe(true)
    expect(store.error).toBe('The file is larger than 2 MB.')
  })
})
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd frontend && npx vitest run src/stores/__tests__/queue.spec.js`
Expected: FAIL (`store.previewStudentImport is not a function`).

- [ ] **Step 3: Implement**

In `frontend/src/stores/queue.js`, inside the `// ============ STUDENT ACTIONS ============` section, add:

```js
    // Admin student file import. The same file is sent twice: commit=false
    // previews (nothing saved), commit=true saves the valid rows. 2,000 rows
    // can take longer than the client's default 10 s timeout.
    async _uploadStudentImport(file, commit) {
      this.error = null
      const form = new FormData()
      form.append('file', file)
      try {
        const response = await api.post('/students/import', form, {
          params: { commit },
          timeout: 120000,
        })
        return response.data
      } catch (err) {
        this.error = err.response?.data?.detail || 'Failed to read the student file'
        throw err
      }
    },

    previewStudentImport(file) {
      return this._uploadStudentImport(file, false)
    },

    commitStudentImport(file) {
      return this._uploadStudentImport(file, true)
    },
```

- [ ] **Step 4: Run it to verify it passes**

Run: `cd frontend && npx vitest run src/stores/__tests__/queue.spec.js`
Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/stores/queue.js frontend/src/stores/__tests__/queue.spec.js
git commit -m "Add student import store actions"
```

---

### Task 8: Import modal and Student Management wiring

**Files:**
- Create: `frontend/src/components/StudentImportModal.vue`
- Modify: `frontend/src/views/StudentManagementView.vue` (header button, modal, `isAdmin`)

**Interfaces:**
- Consumes: `previewStudentImport`, `commitStudentImport` (Task 7); `buildErrorCsv` (Task 6); report shape (Task 3).
- Produces: `<StudentImportModal v-model="open" @imported="reload" />` (props `modelValue: Boolean`; emits `update:modelValue`, `imported`).

- [ ] **Step 1: Create the modal**

`frontend/src/components/StudentImportModal.vue`:

```vue
<template>
  <div v-if="modelValue" class="fixed inset-0 bg-bsu-ink/50 flex items-center justify-center z-50 p-4">
    <div class="bg-white rounded-2xl shadow-soft-lg w-full max-w-3xl max-h-full flex flex-col">
      <div class="px-6 py-4 border-b border-gray-100 flex items-center justify-between gap-4">
        <h3 class="text-lg font-bold text-bsu-ink">Import Students</h3>
        <button type="button" class="text-gray-400 hover:text-gray-600" aria-label="Close" @click="close">✕</button>
      </div>

      <div class="px-6 py-4 overflow-y-auto space-y-4">
        <div v-if="error" class="p-3 bg-red-50 border border-red-100 rounded-xl">
          <p class="text-sm text-red-700">{{ error }}</p>
        </div>

        <!-- Step 1: choose a file -->
        <template v-if="step === 'choose'">
          <p class="text-sm text-gray-600">
            Upload an Excel (.xlsx) or CSV file with one student per row. You'll see a preview before anything is saved.
            Up to 2,000 students and 2 MB per file.
          </p>
          <a href="/api/students/import-template.xlsx" class="btn-secondary btn-md inline-flex">Download template</a>
          <label class="block">
            <span class="block text-sm font-medium text-gray-700 mb-1.5">Student file</span>
            <input
              ref="fileInput"
              type="file"
              accept=".xlsx,.csv"
              class="field"
              :disabled="busy"
              @change="onFileChosen"
            />
          </label>
          <p v-if="busy" class="text-sm text-gray-500">Checking the file…</p>
        </template>

        <!-- Step 2 & 3: preview / result -->
        <template v-else>
          <p class="text-sm text-gray-600">
            <span class="font-semibold text-bsu-ink">{{ fileName }}</span> ·
            {{ report.total_rows }} row{{ report.total_rows === 1 ? '' : 's' }}
            <span v-if="step === 'done'"> · import finished</span>
          </p>

          <div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div v-for="tile in tiles" :key="tile.label" class="rounded-xl border p-3" :class="tile.classes">
              <p class="text-2xl font-bold">{{ tile.value }}</p>
              <p class="text-xs font-semibold uppercase tracking-wide">{{ tile.label }}</p>
            </div>
          </div>

          <p v-if="report.ignored_columns.length" class="text-xs text-gray-500">
            Ignored columns: {{ report.ignored_columns.join(', ') }}
          </p>

          <div v-if="report.problems.length">
            <p class="text-sm font-semibold text-bsu-ink mb-1.5">
              {{ step === 'done' ? 'Not imported' : 'Rows that will be skipped' }}
            </p>
            <div class="overflow-x-auto border border-gray-200 rounded-xl max-h-64">
              <table class="min-w-full text-sm">
                <thead class="bg-bsu-surface text-xs uppercase text-gray-500">
                  <tr>
                    <th class="px-3 py-2 text-left">Row</th>
                    <th class="px-3 py-2 text-left">Student No.</th>
                    <th class="px-3 py-2 text-left">Column</th>
                    <th class="px-3 py-2 text-left">Problem</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-gray-100">
                  <tr v-for="p in report.problems" :key="p.row">
                    <td class="px-3 py-2 whitespace-nowrap">{{ p.row }}</td>
                    <td class="px-3 py-2 whitespace-nowrap">{{ p.student_number || '—' }}</td>
                    <td class="px-3 py-2 whitespace-nowrap">{{ p.column }}</td>
                    <td class="px-3 py-2">{{ p.message }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <details v-if="report.changes.length" class="border border-gray-200 rounded-xl">
            <summary class="px-3 py-2 text-sm font-semibold text-bsu-ink cursor-pointer">
              {{ step === 'done' ? 'Saved changes' : 'Changes to be saved' }} ({{ report.changes.length }})
            </summary>
            <ul class="divide-y divide-gray-100 max-h-64 overflow-y-auto text-sm">
              <li v-for="c in report.changes" :key="c.row" class="px-3 py-2">
                <span class="font-medium text-bsu-ink">{{ c.student_number }} · {{ c.name }}</span>
                <span class="ml-2 text-xs uppercase font-semibold" :class="c.action === 'new' ? 'text-green-700' : 'text-bsu-gold-dark'">
                  {{ c.action === 'new' ? 'New' : 'Update' }}
                </span>
                <span v-for="(pair, field) in c.fields" :key="field" class="block text-xs text-gray-500">
                  {{ field.replace(/_/g, ' ') }}: {{ pair[0] }} → {{ pair[1] }}
                </span>
              </li>
            </ul>
          </details>
        </template>
      </div>

      <div class="px-6 py-4 border-t border-gray-100 flex flex-wrap justify-end gap-3">
        <template v-if="step === 'preview'">
          <button type="button" class="btn-secondary btn-md" :disabled="busy" @click="reset">Choose another file</button>
          <button type="button" class="btn-primary btn-md" :disabled="busy || !toSave" @click="commit">
            {{ busy ? 'Importing…' : `Import ${toSave} student${toSave === 1 ? '' : 's'}` }}
          </button>
        </template>
        <template v-else-if="step === 'done'">
          <button v-if="report.problems.length" type="button" class="btn-secondary btn-md" @click="downloadErrors">
            Download rows with errors (.csv)
          </button>
          <button type="button" class="btn-primary btn-md" @click="close">Close</button>
        </template>
        <button v-else type="button" class="btn-secondary btn-md" @click="close">Cancel</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useQueueStore } from '@/stores/queue'
import { buildErrorCsv } from '@/services/studentImportCsv'

const props = defineProps({ modelValue: { type: Boolean, default: false } })
const emit = defineEmits(['update:modelValue', 'imported'])
const queueStore = useQueueStore()

const step = ref('choose') // choose | preview | done
const file = ref(null)
const fileInput = ref(null)
const report = ref(null)
const busy = ref(false)
const error = ref('')

const fileName = computed(() => file.value?.name || '')
const toSave = computed(() => (report.value ? report.value.new + report.value.updated : 0))
const tiles = computed(() => [
  { label: 'New', value: report.value.new, classes: 'border-green-100 bg-green-50 text-green-800' },
  { label: 'Updated', value: report.value.updated, classes: 'border-bsu-gold/40 bg-bsu-gold/10 text-bsu-gold-dark' },
  { label: 'Unchanged', value: report.value.unchanged, classes: 'border-gray-200 bg-gray-50 text-gray-600' },
  { label: 'Invalid', value: report.value.invalid, classes: 'border-red-100 bg-red-50 text-red-700' },
])

const reset = () => {
  step.value = 'choose'
  file.value = null
  report.value = null
  error.value = ''
  if (fileInput.value) fileInput.value.value = ''
}

const close = () => {
  const imported = step.value === 'done'
  reset()
  emit('update:modelValue', false)
  if (imported) emit('imported')
}

const onFileChosen = async (event) => {
  const chosen = event.target.files?.[0]
  if (!chosen) return
  file.value = chosen
  error.value = ''
  busy.value = true
  try {
    report.value = await queueStore.previewStudentImport(chosen)
    step.value = 'preview'
  } catch (err) {
    error.value = err.response?.data?.detail || 'Could not read this file.'
    if (fileInput.value) fileInput.value.value = ''
  } finally {
    busy.value = false
  }
}

const commit = async () => {
  error.value = ''
  busy.value = true
  try {
    report.value = await queueStore.commitStudentImport(file.value)
    step.value = 'done'
  } catch (err) {
    error.value = err.response?.data?.detail || 'The import failed. Nothing was saved - please try again.'
  } finally {
    busy.value = false
  }
}

const downloadErrors = () => {
  const blob = new Blob([buildErrorCsv(report.value.columns, report.value.problems)], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'students_import_errors.csv'
  a.click()
  URL.revokeObjectURL(url)
}
</script>
```

- [ ] **Step 2: Wire it into Student Management**

In `frontend/src/views/StudentManagementView.vue`:

Replace the header's single button with a button group (keep the existing Add Student button exactly as it is inside the group):

```vue
      <div class="flex flex-wrap gap-2">
        <button v-if="isAdmin" type="button" class="btn-secondary btn-md" @click="showImport = true">
          <svg class="mr-2 -ml-1 w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2M12 4v12m0-12l-4 4m4-4l4 4" />
          </svg>
          Import Students
        </button>
        <!-- existing Add Student button stays here unchanged -->
      </div>
```

Change the header container from `mb-8 flex items-center justify-between` to `mb-8 flex flex-wrap items-center justify-between gap-4`.

Before the template's closing root `</div>`, add:

```vue
    <StudentImportModal v-model="showImport" @imported="loadStudents" />
```

In `<script setup>`, add the import and state:

```js
import StudentImportModal from '@/components/StudentImportModal.vue'
```

```js
const isAdmin = computed(() => queueStore.currentUser?.role === 'admin')
const showImport = ref(false)
```

(`loadStudents` already exists at line ~384.)

- [ ] **Step 3: Build and run the suite**

Run: `cd frontend && npm test && npm run build`
Expected: all Vitest files pass; build succeeds.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/StudentImportModal.vue frontend/src/views/StudentManagementView.vue
git commit -m "Add the Import Students modal to Student Management"
```

---

### Task 9: Docs, full suites and end-to-end check

**Files:**
- Modify: `CLAUDE.md` (repo root, CRLF)

- [ ] **Step 1: Update CLAUDE.md**

1. API Endpoints table: add
   `| POST | /api/students/import?commit= | Admin | Preview (commit=false) or save (commit=true) an .xlsx/.csv student file |` and
   `| GET | /api/students/import-template.xlsx | Admin | Student import template |`.
2. **Avoid Trusting User Input**: replace `the admin-only POST /students/bulk-import` with `the admin-only file import (POST /students/import, app/services/student_import/)`.
3. Input Validation table: add a row `| Student import file | upload | ≤ 2 MB, ≤ 2,000 rows, .xlsx (zip ≤ 25 MB unpacked, defusedxml, data_only) or .csv; rows validated with StudentCreate; email format only (no MX check) |`.
4. Audit events: change `student.bulk_imported` to `student.bulk_imported (counts + file type only)`.

- [ ] **Step 2: Run the full backend suite**

Run: `cd backend && .venv/Scripts/python.exe -m pytest -q -p no:warnings`
Expected: all pass. (Two student-email tests do live DNS lookups and can fail on a flaky network; rerun them alone before treating that as a regression.)

- [ ] **Step 3: Run the frontend suite and build**

Run: `cd frontend && npm test && npm run build`
Expected: pass.

- [ ] **Step 4: End-to-end on the disposable test DB**

Start the backend against `bsu_queue_test` (set `DATABASE_URL` in the process environment, as the run skill describes), with `DEBUG=True`, then start the frontend. As `admin`:
1. Student Management → Import Students → Download template.
2. Fill in about 20 rows: some new, one existing student with a changed year level, and three deliberately bad rows (a 9-digit number, course "BS Nursing", a BIT row without a major).
3. Upload: the preview shows the right counts and problems. Import. Close: the list shows the new students.
4. Download rows with errors: the CSV opens in Excel with the original columns, Row and Error.
5. Log in as `registrar`: there is no Import Students button.

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md
git commit -m "Document the student file import"
```
