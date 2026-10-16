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
import zlib
from dataclasses import dataclass, field

import openpyxl

from .columns import ALIASES, EXAMPLE_ROW, LABELS, REQUIRED, key

MAX_BYTES = 2 * 1024 * 1024
MAX_ROWS = 2000
MAX_UNZIPPED = 25 * 1024 * 1024
# Stop collecting once this many non-blank rows are seen - enough to know
# the file is over the limit (header + example + MAX_ROWS + 1).
_COLLECT_LIMIT = MAX_ROWS + 3
_MAX_COLS = 50


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
            "This is an old Excel 97–2003 file or a password-protected workbook. "
            "Open it in Excel, remove any password, and Save As .xlsx or .csv.")
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


def _collect(rows_iter) -> list[tuple[int, list[str]]]:
    """Keep only non-blank rows, each with its true 1-based sheet row number.

    Blank rows are never stored: a sheet can pad millions of empty rows, and
    a few bytes of file must not turn into hundreds of MB of lists. Columns
    past _MAX_COLS are dropped for the same reason.
    """
    table = []
    for number, row in enumerate(rows_iter, start=1):
        row = row[:_MAX_COLS]
        if not any(v not in (None, "") for v in row):
            continue
        table.append((number, [_cell_text(v) for v in row]))
        if len(table) >= _COLLECT_LIMIT:
            break
    return table


_TOO_LARGE = "This Excel file is too large once unpacked."
_NOT_XLSX = "This file isn't a valid Excel (.xlsx) file."
_CHUNK = 64 * 1024


def _measure_unzipped(z: zipfile.ZipFile) -> None:
    """Count the bytes each member actually decompresses to, not the declared sizes."""
    total = 0
    for info in z.infolist():
        with z.open(info) as member:
            while True:
                chunk = member.read(_CHUNK)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_UNZIPPED:
                    raise ImportFileError(_TOO_LARGE)


def _read_xlsx(data: bytes) -> list[tuple[int, list[str]]]:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            # Cheap fast reject on declared sizes; the real check is below.
            if sum(info.file_size for info in z.infolist()) > MAX_UNZIPPED:
                raise ImportFileError(_TOO_LARGE)
            _measure_unzipped(z)
    except ImportFileError:
        raise
    except (zipfile.BadZipFile, zlib.error, EOFError, OSError,
            RuntimeError, NotImplementedError):
        raise ImportFileError(_NOT_XLSX)
    try:
        wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception:
        raise ImportFileError(_NOT_XLSX)
    try:
        return _collect(wb.worksheets[0].iter_rows(values_only=True, max_col=_MAX_COLS))
    except ImportFileError:
        raise
    except Exception:
        raise ImportFileError(_NOT_XLSX)
    finally:
        wb.close()


def _read_csv(data: bytes) -> list[tuple[int, list[str]]]:
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
    try:
        return _collect(csv.reader(io.StringIO(text), dialect))
    except csv.Error:
        raise ImportFileError("Couldn't read this file as Excel or CSV.")


def _to_result(numbered: list[tuple[int, list[str]]], file_type: str) -> ReadResult:
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
