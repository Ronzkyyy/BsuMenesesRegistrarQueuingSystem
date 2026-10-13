"""Appointment emails: booking confirmation, the 5 AM reminder batch, the
secret-gated cron endpoint, staff resend, and the masked public email."""
import json
import logging
import os
import subprocess
import sys
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import text

from app.core import campus_time
from app.core.config import settings
from app.core.database import engine
from app.db_models import (
    AppointmentDB, AppointmentDBStatus, AppointmentDocumentDB, UserRole,
)
from app.models.queue import QueueType
from app.services import appointment_email, email_sender
from app.services.appointment_service import reminder_status
from app.services.email_mask import mask_email

BACKEND_DIR = Path(__file__).resolve().parent.parent
# A Wednesday, 5:00 AM on campus - when the reminder workflow runs.
APPT_DAY = date(2026, 11, 4)
FIVE_AM = datetime(2026, 11, 4, 5, 0, tzinfo=campus_time.campus_tz())
SECRET = "s" * 40


class _NoClose:
    """The test session, for code that opens and closes its own session."""
    def __init__(self, session):
        self._s = session

    def close(self):
        pass

    def __getattr__(self, name):
        return getattr(self._s, name)


@pytest.fixture
def outbox(monkeypatch):
    sent: list[dict] = []
    monkeypatch.setattr(email_sender, "send_email", lambda **m: sent.append(m) or True)
    return sent


@pytest.fixture
def own_session(monkeypatch, db_session):
    monkeypatch.setattr(appointment_email, "SessionLocal", lambda: _NoClose(db_session))


@pytest.fixture
def at_five_am(monkeypatch):
    monkeypatch.setattr(campus_time, "campus_now", lambda: FIVE_AM)


def _queue(make_queue, **kw):
    defaults = dict(booking_enabled=True, operating_start_time=time(8, 0),
                    operating_end_time=time(17, 0), slot_capacity=5, booking_window_days=14)
    defaults.update(kw)
    return make_queue(**defaults)


_ref = iter(range(500000, 999999))


def _appt(db, student, queue, *, day=APPT_DAY, start=time(9, 0), end=time(9, 30),
          status=AppointmentDBStatus.BOOKED, documents=(), **extra):
    n = next(_ref)
    row = AppointmentDB(
        reference_code=f"APT-{n}", student_id=student.id, queue_id=queue.id,
        appointment_date=day, slot_start_time=start, slot_end_time=end,
        qr_token=f"qr-token-{n}", status=status,
        documents=[AppointmentDocumentDB(document_id=d.id, name=d.name, short_name=d.short_name,
                                         fee=d.fee, position=d.display_order) for d in documents],
        **extra,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _login(client, user):
    return client.post("/api/auth/login", data={"username": user.username, "password": user._plain_password})


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


# ---- the email itself ---------------------------------------------------

def test_booking_queues_a_confirmation_with_the_check_in_qr(
        client, db_session, make_queue, make_student, outbox, own_session):
    queue = _queue(make_queue)
    student = make_student(first_name="Maria", last_name="Santos")
    day = campus_time.campus_today() + timedelta(days=1)

    r = client.post("/api/appointments", json={
        "student_id": student.id, "queue_id": queue.id,
        "appointment_date": day.isoformat(), "slot_start_time": "09:00:00",
    })

    assert r.status_code == 200
    booked = r.json()
    assert len(outbox) == 1
    mail = outbox[0]
    assert mail["to"] == student.email
    assert booked["reference_code"] in mail["subject"]
    assert "Maria" not in mail["subject"] and "Santos" not in mail["subject"]
    assert "Hello Maria" in mail["text"]
    assert "9:00 AM – 9:30 AM" in mail["text"]
    assert "from 8:30 AM until 10:00 AM" in mail["text"]
    # One inline PNG, the same QR the booking page shows (encodes qr_token).
    [(cid, png)] = mail["inline_images"]
    assert f'src="cid:{cid}"' in mail["html"]
    assert png == appointment_email.qr_png(booked["qr_token"])
    assert png.startswith(b"\x89PNG")
    db_session.expire_all()
    assert db_session.get(AppointmentDB, booked["id"]).confirmation_sent_at is not None


def test_document_request_email_lists_documents_fees_and_requirements(
        db_session, make_queue, make_student, make_document):
    queue = _queue(make_queue, queue_type=QueueType.DOCUMENT_REQUEST)
    tor = make_document(name="Transcript of Records", fee=Decimal("150.00"),
                        requirements="Clearance form", display_order=1)
    cog = make_document(name="Certificate of Grades", fee=None, display_order=2)
    appt = _appt(db_session, make_student(), queue, documents=[tor, cog])

    mail = appointment_email.build_appointment_email(db_session, appt, "reminder")

    assert "Transcript of Records (₱150.00)" in mail["text"]
    assert "Certificate of Grades" in mail["text"]
    assert "Total of listed fees ₱150.00" in mail["text"]
    assert "Transcript of Records: Clearance form" in mail["text"]
    assert "Requested documents" in mail["html"]
    assert mail["subject"].startswith("Reminder: your registrar appointment is today at 9:00 AM")


def test_other_services_have_no_documents_section(db_session, make_queue, make_student):
    appt = _appt(db_session, make_student(), _queue(make_queue))
    mail = appointment_email.build_appointment_email(db_session, appt, "confirmation")
    assert "Requested documents" not in mail["html"]
    assert "documents" not in mail["text"].lower()


def test_free_text_is_html_escaped(db_session, make_queue, make_student, make_document):
    queue = _queue(make_queue, queue_type=QueueType.DOCUMENT_REQUEST)
    doc = make_document(name="Diploma <i>copy</i>", requirements="<script>alert(1)</script>")
    student = make_student(first_name="<b>Juan</b>")
    appt = _appt(db_session, student, queue, documents=[doc])

    html = appointment_email.build_appointment_email(db_session, appt, "confirmation")["html"]

    assert "<script>" not in html and "<b>Juan</b>" not in html and "<i>copy</i>" not in html
    assert "&lt;script&gt;" in html and "&lt;b&gt;Juan&lt;/b&gt;" in html


def test_confirmation_skips_an_appointment_no_longer_booked(
        db_session, make_queue, make_student, outbox, own_session):
    appt = _appt(db_session, make_student(), _queue(make_queue), status=AppointmentDBStatus.CANCELLED)
    assert appointment_email.send_confirmation(appt.id) is False
    assert outbox == []


# ---- reminder batch -----------------------------------------------------

def test_reminders_go_only_to_todays_booked_unsent_appointments(
        db_session, make_queue, make_student, outbox, at_five_am):
    queue = _queue(make_queue)
    due = _appt(db_session, make_student(), queue)
    _appt(db_session, make_student(), queue, day=APPT_DAY + timedelta(days=1))   # tomorrow
    _appt(db_session, make_student(), queue, status=AppointmentDBStatus.CANCELLED)
    _appt(db_session, make_student(), queue, status=AppointmentDBStatus.EXPIRED)
    _appt(db_session, make_student(), queue, status=AppointmentDBStatus.CHECKED_IN)
    _appt(db_session, make_student(), queue, reminder_sent_at=FIVE_AM - timedelta(minutes=30))
    # Slot already over by the time this (late) run happens.
    _appt(db_session, make_student(), queue, start=time(4, 0), end=time(4, 30))

    result = appointment_email.send_due_reminders(db_session)

    assert result == {"status": "ok", "due": 1, "sent": 1, "failed": 0}
    assert [m["to"] for m in outbox] == [due.student.email]
    db_session.refresh(due)
    assert due.reminder_sent_at is not None and due.reminder_attempts == 1
    assert reminder_status(due) == "sent"

    # The 5:30 run sends nothing new - no student is reminded twice.
    again = appointment_email.send_due_reminders(db_session)
    assert again["sent"] == 0 and len(outbox) == 1


def test_failed_reminder_is_retried_once_then_marked_failed(
        db_session, make_queue, make_student, monkeypatch, at_five_am):
    attempts = []
    monkeypatch.setattr(email_sender, "send_email", lambda **m: attempts.append(m) and False)
    appt = _appt(db_session, make_student(), _queue(make_queue))

    first = appointment_email.send_due_reminders(db_session)
    db_session.refresh(appt)
    assert first["failed"] == 1 and appt.reminder_attempts == 1
    assert reminder_status(appt) == "pending"

    second = appointment_email.send_due_reminders(db_session)
    db_session.refresh(appt)
    assert second["failed"] == 1 and appt.reminder_attempts == 2
    assert reminder_status(appt) == "failed"

    third = appointment_email.send_due_reminders(db_session)
    assert third["due"] == 0 and len(attempts) == 2


def test_overlapping_run_does_nothing(db_session, make_queue, make_student, outbox, at_five_am):
    _appt(db_session, make_student(), _queue(make_queue))

    with engine.connect() as other, other.begin():
        other.execute(text("SELECT pg_try_advisory_xact_lock(:k)"),
                      {"k": appointment_email._REMINDER_LOCK_KEY})
        result = appointment_email.send_due_reminders(db_session)

    assert result["status"] == "already_running"
    assert outbox == []


# ---- cron endpoint ------------------------------------------------------

def test_cron_endpoint_runs_the_batch_with_the_right_secret(
        client, db_session, make_queue, make_student, outbox, at_five_am, monkeypatch):
    monkeypatch.setattr(settings, "CRON_SECRET", SECRET)
    student = make_student()
    _appt(db_session, student, _queue(make_queue))

    handler, events = _audit_capture()
    try:
        r = client.post("/api/internal/appointment-reminders", headers={"X-Cron-Secret": SECRET})
    finally:
        logging.getLogger("bsu.security").removeHandler(handler)

    assert r.status_code == 200
    assert r.json() == {"status": "ok", "due": 1, "sent": 1, "failed": 0}
    assert student.email not in r.text
    run = [e for e in events() if e["event"] == "appointment.reminders_run"]
    assert run and run[0]["outcome"] == "success"


@pytest.mark.parametrize("headers", [{}, {"X-Cron-Secret": "wrong" * 10}])
def test_cron_endpoint_refuses_a_missing_or_wrong_secret(client, outbox, monkeypatch, headers):
    monkeypatch.setattr(settings, "CRON_SECRET", SECRET)

    handler, events = _audit_capture()
    try:
        r = client.post("/api/internal/appointment-reminders", headers=headers)
    finally:
        logging.getLogger("bsu.security").removeHandler(handler)

    assert r.status_code == 403
    assert outbox == []
    assert any(e["event"] == "appointment.reminders_run" and e["outcome"] == "denied" for e in events())


def test_cron_endpoint_is_absent_when_not_configured(client, monkeypatch):
    monkeypatch.setattr(settings, "CRON_SECRET", None)
    r = client.post("/api/internal/appointment-reminders", headers={"X-Cron-Secret": SECRET})
    assert r.status_code == 404


def test_short_cron_secret_fails_at_startup():
    env = {**os.environ, "CRON_SECRET": "too-short", "DEBUG": "True"}
    proc = subprocess.run([sys.executable, "-c", "import app.core.config"],
                          cwd=BACKEND_DIR, env=env, capture_output=True, text=True)
    assert proc.returncode != 0
    assert "CRON_SECRET must be at least 32 characters" in proc.stderr


# ---- staff resend ---------------------------------------------------------

def test_staff_can_resend_the_confirmation(
        client, db_session, make_user, make_queue, make_student, outbox, own_session):
    staff = make_user(role=UserRole.STAFF)
    student = make_student(email="juan.delacruz@gmail.com")
    appt = _appt(db_session, student, _queue(make_queue),
                 day=campus_time.campus_today() + timedelta(days=1))
    _login(client, staff)

    handler, events = _audit_capture()
    try:
        r = client.post(f"/api/appointments/{appt.id}/resend-confirmation")
    finally:
        logging.getLogger("bsu.security").removeHandler(handler)

    assert r.status_code == 202
    assert r.json()["detail"] == "Sending the confirmation to j***@gmail.com."
    assert [m["to"] for m in outbox] == ["juan.delacruz@gmail.com"]
    resent = [e for e in events() if e["event"] == "appointment.confirmation_resent"]
    assert resent and resent[0]["actor"] == staff.username


def test_resend_rules(client, db_session, make_user, make_queue, make_student, outbox, own_session):
    appt = _appt(db_session, make_student(), _queue(make_queue), status=AppointmentDBStatus.CHECKED_IN)

    assert client.post(f"/api/appointments/{appt.id}/resend-confirmation").status_code == 401
    _login(client, make_user(role=UserRole.STAFF))
    assert client.post(f"/api/appointments/{appt.id}/resend-confirmation").status_code == 400
    assert client.post("/api/appointments/999999/resend-confirmation").status_code == 404
    assert client.post("/api/appointments/0/resend-confirmation").status_code == 422
    assert outbox == []


def test_staff_list_shows_reminder_status(client, db_session, make_user, make_queue, make_student):
    queue = _queue(make_queue)
    day = campus_time.campus_today() + timedelta(days=1)
    _appt(db_session, make_student(), queue, day=day)
    _login(client, make_user(role=UserRole.STAFF))

    r = client.get("/api/appointments", params={"date_from": day.isoformat(), "date_to": day.isoformat()})

    assert r.status_code == 200
    assert {a["reminder_status"] for a in r.json()["items"]} == {"pending"}


# ---- masked public student email -------------------------------------------

@pytest.mark.parametrize("email, masked", [
    ("juan.delacruz@gmail.com", "j***@gmail.com"),
    ("ab@bulsu.edu.ph", "a***@bulsu.edu.ph"),
    ("x@yahoo.com", "*@yahoo.com"),
    ("not-an-email", "***"),
])
def test_mask_email(email, masked):
    assert mask_email(email) == masked


def test_public_student_lookup_never_returns_the_full_email(client, make_student):
    student = make_student(email="maria.santos@gmail.com")

    r = client.get("/api/students/search", params={"student_id": student.student_id})

    assert r.status_code == 200
    body = r.json()
    assert body["email_masked"] == "m***@gmail.com"
    assert "email" not in body
    assert "maria.santos" not in r.text
