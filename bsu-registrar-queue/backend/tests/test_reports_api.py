"""Admin-only reports API: history + calendar endpoints."""
import json
import logging
from datetime import datetime, timezone

from app.db_models import TicketDB, TicketDBStatus, UserRole

UTC = timezone.utc


def _login(client, user):
    return client.post("/api/auth/login",
                       data={"username": user.username,
                             "password": user._plain_password})


def _seed_completed_ticket(db_session, student, queue, when):
    row = TicketDB(
        ticket_number=1, student_id=student.id, queue_id=queue.id,
        purpose="Clearance", status=TicketDBStatus.COMPLETED, position=0,
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


def test_csv_export_returns_csv_and_logs_audit_event(client, db_session, make_user, make_queue, make_student):
    admin = make_user(role=UserRole.ADMIN)
    _seed_completed_ticket(db_session, make_student(), make_queue(),
                           datetime(2026, 6, 10, 3, 0, tzinfo=UTC))
    _login(client, admin)

    handler, events = _audit_capture()
    try:
        r = client.get("/api/reports/transactions.csv",
                       params={"date_from": "2026-06-01", "date_to": "2026-06-30"})
    finally:
        logging.getLogger("bsu.security").removeHandler(handler)

    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "attachment; filename=" in r.headers["content-disposition"]
    lines = [ln for ln in r.text.splitlines() if ln.strip()]
    assert lines[0].startswith("kind,reference,student_number")
    assert len(lines) == 2  # header + 1 data row

    exported = [e for e in events() if e["event"] == "report.exported"]
    assert len(exported) == 1
    assert exported[0]["actor"] == admin.username
    assert exported[0]["outcome"] == "success"


def test_csv_export_is_admin_only(client, make_user):
    _login(client, make_user(role=UserRole.REGISTRAR))
    assert client.get("/api/reports/transactions.csv").status_code == 403
