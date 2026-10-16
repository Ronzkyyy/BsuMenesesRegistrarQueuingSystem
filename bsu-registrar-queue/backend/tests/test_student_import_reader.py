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


def test_counts_real_bytes_not_declared_size(monkeypatch):
    """A member whose declared size is tiny but whose data is huge must still be caught."""

    class LyingZip(zipfile.ZipFile):
        def __init__(self, *args, **kwargs):
            pass

        def close(self):
            pass

        def infolist(self):
            info = zipfile.ZipInfo("xl/huge.xml")
            info.file_size = 1024
            return [info]

        def open(self, name, mode="r", pwd=None, *, force_zip64=False):
            return io.BytesIO(b"0" * (reader.MAX_UNZIPPED + 1))

    monkeypatch.setattr(reader.zipfile, "ZipFile", LyingZip)
    with pytest.raises(reader.ImportFileError, match="too large once unpacked"):
        reader.read_upload(b"PK\x03\x04" + b"x" * 100)


def test_malformed_sheet_xml_is_a_clean_error():
    src = zipfile.ZipFile(io.BytesIO(make_xlsx([HEADER, ROW])))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            body = src.read(info)
            if info.filename == "xl/worksheets/sheet1.xml":
                body = b"<not-xml"
            dst.writestr(info.filename, body)
    with pytest.raises(reader.ImportFileError, match="valid Excel"):
        reader.read_upload(out.getvalue())


def test_csv_field_over_csv_limit_is_a_clean_error():
    data = make_csv([HEADER, [ROW[0], "a" * 140000] + ROW[2:]])
    with pytest.raises(reader.ImportFileError, match="Excel or CSV"):
        reader.read_upload(data)


def test_far_away_cell_does_not_blow_up_time_or_memory():
    import tracemalloc
    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True})
    ws = wb.add_worksheet()
    for c, value in enumerate(HEADER):
        ws.write(0, c, value)
    for c, value in enumerate(ROW):
        ws.write(1, c, value)
    ws.write(1048574, 0, "x")
    wb.close()
    tracemalloc.start()
    try:
        result = reader.read_upload(buf.getvalue())
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    assert peak < 40 * 1024 * 1024
    assert [r.row for r in result.rows] == [2, 1048575]
    assert result.rows[0].values["first_name"] == "Juan"


def test_csv_of_blank_lines_is_bounded():
    data = make_csv([HEADER, ROW]) + b"\r\n" * 200_000
    result = reader.read_upload(data)
    assert [r.row for r in result.rows] == [2]
