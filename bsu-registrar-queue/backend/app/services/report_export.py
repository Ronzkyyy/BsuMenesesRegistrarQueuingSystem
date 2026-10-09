"""Build the admin transaction-history export as a branded .xlsx workbook.

Layout follows the registrar's print template: A4 landscape, BSU logo /
university address / Meneses logo in the page header, the registrar's name
and title in the page footer, then a title block and the transaction table.

Every text cell is written with `write_string` (and the workbook has formula
and URL auto-conversion off), so a student name such as "=HYPERLINK(...)"
from the public kiosk is stored as plain text and never run as a formula.
"""
import io
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import xlsxwriter

from ..core import campus_time
from ..core.config import settings
from ..models.report import TransactionRow

_ASSETS = Path(__file__).resolve().parent.parent / "assets"
# The PNGs carry a pHYs DPI chosen so they print at the template's size
# (BSU 162.75 x 111 pt, Meneses 112.5 pt square); XlsxWriter sizes header
# images from the DPI alone.
BSU_LOGO = _ASSETS / "BSUlogo.png"
MENESES_LOGO = _ASSETS / "MENESESlogo.png"

COLUMNS = [
    # (header, width)
    ("Kind of Transaction", 20),
    ("Reference No.", 14),
    ("Student Number", 16),
    ("Student Name", 30),
    ("Queue", 22),
    ("Document Type", 20),
    ("Status", 13),
    ("Priority", 11),
    ("Date Created", 22),
    ("Date Processed", 22),
    ("Appointment Date", 18),
]
LAST_COL = len(COLUMNS) - 1

_STATUS_LABELS = {
    "waiting": "Waiting", "serving": "Serving", "completed": "Completed",
    "cancelled": "Cancelled", "no_show": "No-Show", "booked": "Booked",
    "checked_in": "Checked In", "expired": "Expired",
}
_KIND_LABELS = {"ticket": "Ticket", "appointment": "Appointment"}


@dataclass
class ExportContext:
    """What the title block says about how this export was produced."""
    date_from: date
    date_to: date
    kinds: list[str]
    statuses: Optional[list[str]]
    queue_name: Optional[str]
    priority: Optional[str]
    student_number: Optional[str]
    generated_by: str
    generated_at: datetime  # aware, campus time


def _label(value: Optional[str], labels: Optional[dict] = None) -> str:
    if not value:
        return ""
    if labels and value in labels:
        return labels[value]
    return value.replace("_", " ").title()


def _campus_naive(value: datetime) -> datetime:
    """Aware DB timestamp -> naive campus wall-clock time for an Excel cell."""
    if value.tzinfo is not None:
        value = value.astimezone(campus_time.campus_tz())
    return value.replace(tzinfo=None)


def _header_text(text: str) -> str:
    # "&" starts a control code in Excel header/footer strings.
    return text.replace("&", "&&")


def _long_date(d: date) -> str:
    return f"{d:%B} {d.day}, {d.year}"


def _filters_summary(ctx: ExportContext) -> str:
    kinds = ", ".join(_label(k, _KIND_LABELS) + "s" for k in ctx.kinds) or "All"
    statuses = ", ".join(_label(s, _STATUS_LABELS) for s in ctx.statuses) if ctx.statuses else "All"
    return "   ·   ".join([
        f"Type: {kinds}",
        f"Status: {statuses}",
        f"Queue: {ctx.queue_name or 'All'}",
        f"Priority: {_label(ctx.priority) or 'All'}",
        f"Student: {ctx.student_number or 'All'}",
    ])


def build_transactions_workbook(rows: list[TransactionRow], ctx: ExportContext) -> bytes:
    buffer = io.BytesIO()
    wb = xlsxwriter.Workbook(buffer, {
        "in_memory": True,
        "strings_to_formulas": False,
        "strings_to_urls": False,
        "strings_to_numbers": False,
    })
    ws = wb.add_worksheet("Transactions")

    title = wb.add_format({"bold": True, "font_size": 14, "align": "center"})
    subtitle = wb.add_format({"italic": True, "align": "center"})
    meta_label = wb.add_format({"bold": True})
    meta_value = wb.add_format({"align": "left"})
    head = wb.add_format({
        "bold": True, "border": 1, "bg_color": "#D9D9D9",
        "align": "center", "valign": "vcenter", "text_wrap": True,
    })
    cell = wb.add_format({"border": 1, "valign": "top"})
    when = wb.add_format({"border": 1, "valign": "top", "num_format": "mmm d, yyyy h:mm AM/PM", "align": "left"})
    day = wb.add_format({"border": 1, "valign": "top", "num_format": "mmm d, yyyy", "align": "left"})
    empty = wb.add_format({"border": 1, "italic": True, "align": "center"})

    # --- Page setup: matches the registrar's template ----------------------
    ws.set_landscape()
    ws.set_paper(9)  # A4
    # Top margin leaves room for the ~112pt logos so the header never
    # overlaps the sheet body when printed.
    ws.set_margins(left=0.5, right=0.5, top=2.0, bottom=0.9)
    ws.center_horizontally()
    ws.fit_to_pages(1, 0)  # one page wide, as many tall as needed

    campus = _header_text(settings.CAMPUS_NAME)
    ws.set_header(
        "&L&G"
        "&C&\"-,Regular\"&11Republic of the Philippines\n"
        "&\"-,Bold\"&14BULACAN STATE UNIVERSITY\n"
        "&\"-,Regular\"&11Matungao, Bulakan, Bulacan\n\n"
        "&\"-,Bold\"&13MENESES CAMPUS"
        "&R&G",
        {"image_left": str(BSU_LOGO), "image_right": str(MENESES_LOGO), "margin": 0.3},
    )
    ws.set_footer(
        f"&L&\"-,Bold\"{_header_text(settings.REGISTRAR_NAME.upper())}\n"
        f"&\"-,Regular\"Registrar, {campus}"
        "&RPage &P of &N",
        {"margin": 0.3},
    )

    # --- Title block --------------------------------------------------------
    ws.merge_range(0, 0, 0, LAST_COL, "TRANSACTION HISTORY REPORT", title)
    ws.merge_range(1, 0, 1, LAST_COL,
                   f"{_long_date(ctx.date_from)} – {_long_date(ctx.date_to)}", subtitle)
    generated = _campus_naive(ctx.generated_at)
    meta = [
        ("Filters:", _filters_summary(ctx)),
        ("Generated by:", ctx.generated_by),
        ("Generated on:", f"{_long_date(generated.date())} "
                          f"{generated.hour % 12 or 12}:{generated:%M %p}"),
        ("Total records:", str(len(rows))),
    ]
    for i, (label, value) in enumerate(meta, start=3):
        ws.write_string(i, 0, label, meta_label)
        ws.merge_range(i, 1, i, LAST_COL, "", meta_value)
        ws.write_string(i, 1, value, meta_value)

    # --- Table --------------------------------------------------------------
    head_row = 3 + len(meta) + 1
    for col, (name, width) in enumerate(COLUMNS):
        ws.set_column(col, col, width)
        ws.write_string(head_row, col, name, head)
    ws.repeat_rows(head_row)
    ws.freeze_panes(head_row + 1, 0)

    if not rows:
        ws.merge_range(head_row + 1, 0, head_row + 1, LAST_COL,
                       "No transactions match these filters.", empty)
    for offset, r in enumerate(rows, start=1):
        row = head_row + offset
        ws.write_string(row, 0, _label(r.kind, _KIND_LABELS), cell)
        ws.write_string(row, 1, r.reference, cell)
        ws.write_string(row, 2, r.student_number, cell)
        ws.write_string(row, 3, r.student_name, cell)
        ws.write_string(row, 4, r.queue_name, cell)
        ws.write_string(row, 5, r.document_type or "", cell)
        ws.write_string(row, 6, _label(r.status, _STATUS_LABELS), cell)
        ws.write_string(row, 7, _label(r.priority), cell)
        ws.write_datetime(row, 8, _campus_naive(r.created_at), when)
        if r.occurred_at:
            ws.write_datetime(row, 9, _campus_naive(r.occurred_at), when)
        else:
            ws.write_blank(row, 9, None, cell)
        if r.appointment_date:
            ws.write_datetime(row, 10, datetime.combine(r.appointment_date, datetime.min.time()), day)
        else:
            ws.write_blank(row, 10, None, cell)

    if rows:
        ws.autofilter(head_row, 0, head_row + len(rows), LAST_COL)

    wb.close()
    return buffer.getvalue()
