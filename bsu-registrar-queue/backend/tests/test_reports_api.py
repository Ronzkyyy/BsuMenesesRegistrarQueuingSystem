"""Admin-only reports API: history + calendar endpoints."""
import io
import json
import logging
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from app.core.config import settings
from app.db_models import TicketDB, TicketDBStatus, UserRole

UTC = timezone.utc


def _login(client, user):
    return client.post("/api/auth/login",
                       data={"username": user.username,
                             "password": user._plain_password})


def _seed_completed_ticket(db_session, student, queue, when):
    row = TicketDB(
        ticket_number=1, student_id=student.id, queue_id=queue.id,
        status=TicketDBStatus.COMPLETED, position=0,
        created_at=when, completed_at=when,
    )
    db_session.add(row)
    db_session.commit()


def test_admin_can_list_transactions(client, db_session, make_user, make_queue, make_student):
    admin = make_user(role=UserRole.ADMIN)
    _seed_completed_ticket(db_session, make_student(), make_queue(),
                           datetime(2026, 6, 10, 3, 0, tzinfo=UTC))
    _login(client, admin)

    r = client.get("/api/reports/transactions",
                   params={"date_from": "2026-06-01", "date_to": "2026-06-30"})

    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["kind"] == "ticket"


def test_admin_can_get_calendar(client, db_session, make_user, make_queue, make_student):
    admin = make_user(role=UserRole.ADMIN)
    _seed_completed_ticket(db_session, make_student(), make_queue(),
                           datetime(2026, 6, 10, 3, 0, tzinfo=UTC))
    _login(client, admin)

    r = client.get("/api/reports/calendar", params={"year": 2026, "month": 6})

    assert r.status_code == 200
    body = r.json()
    assert body["month_total"] == 1
    assert body["peak_day"] == "2026-06-10"
    assert len(body["busiest_hours"]) == 24
    assert len(body["days"]) == 30


def test_registrar_is_forbidden(client, make_user):
    registrar = make_user(role=UserRole.REGISTRAR)
    _login(client, registrar)
    assert client.get("/api/reports/transactions").status_code == 403
    assert client.get("/api/reports/calendar",
                      params={"year": 2026, "month": 6}).status_code == 403


def test_staff_is_forbidden(client, make_user):
    staff = make_user(role=UserRole.STAFF)
    _login(client, staff)
    assert client.get("/api/reports/transactions").status_code == 403


def test_unauthenticated_is_401(client):
    assert client.get("/api/reports/transactions").status_code == 401


def test_bad_params_are_422(client, make_user):
    admin = make_user(role=UserRole.ADMIN)
    _login(client, admin)
    assert client.get("/api/reports/transactions",
                      params={"limit": 0}).status_code == 422
    assert client.get("/api/reports/transactions",
                      params={"student_number": "abc"}).status_code == 422
    assert client.get("/api/reports/transactions",
                      params={"status": "nonsense"}).status_code == 422
    assert client.get("/api/reports/calendar",
                      params={"year": 2026, "month": 13}).status_code == 422


def test_date_from_after_date_to_is_400(client, make_user):
    admin = make_user(role=UserRole.ADMIN)
    _login(client, admin)
    r = client.get("/api/reports/transactions",
                   params={"date_from": "2026-06-30", "date_to": "2026-06-01"})
    assert r.status_code == 400


def _audit_capture():
    logger = logging.getLogger("bsu.security")
    messages: list[str] = []

    class _Cap(logging.Handler):
        def emit(self, record):
            messages.append(record.getMessage())

    handler = _Cap()
    handler.setLevel(logging.INFO)
    logger.addHandler(handler)
    return handler, lambda: [json.loads(m) for m in messages]


def _xlsx_parts(content):
    """(cell text by ref, sheet xml, header/footer xml) of an exported workbook,
    read with the stdlib so the tests need no spreadsheet library."""
    z = zipfile.ZipFile(io.BytesIO(content))
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    shared = [si.findtext("m:t", namespaces=ns) or ""
              for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", ns)]
    sheet_xml = z.read("xl/worksheets/sheet1.xml").decode()
    cells = {}
    for c in ET.fromstring(sheet_xml).iter(f"{{{ns['m']}}}c"):
        v = c.findtext("m:v", namespaces=ns)
        if v is not None:
            cells[c.get("r")] = shared[int(v)] if c.get("t") == "s" else v
    return cells, sheet_xml, z.namelist()


def test_xlsx_export_returns_workbook_and_logs_audit_event(client, db_session, make_user, make_queue, make_student):
    admin = make_user(role=UserRole.ADMIN)
    _seed_completed_ticket(db_session, make_student(), make_queue(),
                           datetime(2026, 6, 10, 3, 0, tzinfo=UTC))
    _login(client, admin)

    handler, events = _audit_capture()
    try:
        r = client.get("/api/reports/transactions.xlsx",
                       params={"date_from": "2026-06-01", "date_to": "2026-06-30"})
    finally:
        logging.getLogger("bsu.security").removeHandler(handler)

    assert r.status_code == 200
    assert r.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    assert 'filename="transactions_2026-06-01_2026-06-30.xlsx"' in r.headers["content-disposition"]

    cells, sheet_xml, names = _xlsx_parts(r.content)
    assert cells["A1"] == "TRANSACTION HISTORY REPORT"
    assert cells["A2"] == "June 1, 2026 – June 30, 2026"
    assert cells["B5"] == f"{admin.full_name} ({admin.username})"
    assert cells["B7"] == "1"  # total records
    assert cells["A9"] == "Kind of Transaction"
    assert cells["J9"] == "Date Processed"
    assert cells["A10"] == "Ticket"
    assert cells["G10"] == "Completed"
    assert "A11" not in cells  # exactly one data row

    # Created 03:00 UTC = 11:00 Manila: the Excel serial carries campus time.
    assert abs(float(cells["I10"]) % 1 - 11 / 24) < 1e-6

    # Branding from the registrar's template: A4 landscape, both logos and
    # the university address in the header, the registrar in the footer.
    assert 'paperSize="9"' in sheet_xml and 'orientation="landscape"' in sheet_xml
    assert "BULACAN STATE UNIVERSITY" in sheet_xml and "MENESES CAMPUS" in sheet_xml
    assert settings.REGISTRAR_NAME.upper() in sheet_xml
    assert sum(n.startswith("xl/media/") for n in names) == 2

    exported = [e for e in events() if e["event"] == "report.exported"]
    assert len(exported) == 1
    assert exported[0]["actor"] == admin.username
    assert exported[0]["outcome"] == "success"


def test_xlsx_export_stores_formula_like_names_as_text(client, db_session, make_user, make_queue, make_student):
    admin = make_user(role=UserRole.ADMIN)
    queue = make_queue()
    # first_name is attacker-controlled free text via the public kiosk; it
    # must land in the workbook as a string cell, never a formula.
    student = make_student(first_name="=HYPERLINK(0)")
    _seed_completed_ticket(db_session, student, queue,
                           datetime(2026, 6, 10, 3, 0, tzinfo=UTC))
    _login(client, admin)

    r = client.get("/api/reports/transactions.xlsx",
                   params={"date_from": "2026-06-01", "date_to": "2026-06-30"})
    assert r.status_code == 200
    cells, sheet_xml, _ = _xlsx_parts(r.content)
    assert cells["D10"].startswith("=HYPERLINK(0)")
    assert "<f>" not in sheet_xml


def test_xlsx_export_with_no_rows_says_so(client, make_user):
    _login(client, make_user(role=UserRole.ADMIN))
    r = client.get("/api/reports/transactions.xlsx",
                   params={"date_from": "2020-01-01", "date_to": "2020-01-31"})
    assert r.status_code == 200
    cells, _, _ = _xlsx_parts(r.content)
    assert cells["B7"] == "0"
    assert cells["A10"] == "No transactions match these filters."


def test_xlsx_export_is_admin_only(client, make_user):
    _login(client, make_user(role=UserRole.REGISTRAR))
    assert client.get("/api/reports/transactions.xlsx").status_code == 403
