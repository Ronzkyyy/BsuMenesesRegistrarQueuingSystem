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
