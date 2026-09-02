"""Admin-only reports API: history + calendar endpoints."""
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
