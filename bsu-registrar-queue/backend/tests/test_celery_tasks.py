"""Characterization tests for the Celery beat tasks in app/services/notifications.py.

The tasks open their own SessionLocal(); here it's swapped for the per-test
transactional session so every write is rolled back like any other test.
"""
from datetime import datetime, timedelta, timezone

import pytest

import app.services.notifications as notifications
from app.db_models import TicketDB, TicketDBStatus
from app.models.ticket import TicketCreate
from app.services.ticket_service import TicketService


class _NoCloseSession:
    """Proxy that ignores close() so the task can't end the test's session."""

    def __init__(self, session):
        self._session = session

    def close(self):
        pass

    def __getattr__(self, name):
        return getattr(self._session, name)


@pytest.fixture()
def task_db(db_session, monkeypatch):
    monkeypatch.setattr(notifications, "SessionLocal", lambda: _NoCloseSession(db_session))
    return db_session


def _take(db, queue, student):
    return TicketService(db).create_ticket(TicketCreate(student_id=student.id, queue_id=queue.id))


def _backdate(db, ticket_id, days=1):
    row = db.query(TicketDB).filter(TicketDB.id == ticket_id).one()
    row.created_at = TicketService(db)._campus_today_start() - timedelta(days=days, minutes=-30)
    db.commit()
    return row


def _status(db, ticket_id):
    db.expire_all()
    return db.query(TicketDB).filter(TicketDB.id == ticket_id).one().status


def test_no_show_cleanup_expires_previous_day_waiting_and_serving(task_db, make_queue, make_student, caplog):
    queue = make_queue()
    old_serving = _take(task_db, queue, make_student())
    old_waiting = _take(task_db, queue, make_student())
    TicketService(task_db).serve_next_ticket(queue.id)  # serves old_serving
    _backdate(task_db, old_serving.id)
    _backdate(task_db, old_waiting.id)

    notifications.check_no_show_tickets()

    assert "Error checking no-show tickets" not in caplog.text
    assert _status(task_db, old_serving.id) == TicketDBStatus.NO_SHOW
    assert _status(task_db, old_waiting.id) == TicketDBStatus.NO_SHOW


def test_no_show_cleanup_never_touches_todays_tickets(task_db, make_queue, make_student):
    """A student still at the counter after 45 minutes is not a no-show."""
    queue = make_queue()
    serving = _take(task_db, queue, make_student())
    waiting = _take(task_db, queue, make_student())
    TicketService(task_db).serve_next_ticket(queue.id)
    row = task_db.query(TicketDB).filter(TicketDB.id == serving.id).one()
    row.served_at = datetime.now(timezone.utc) - timedelta(minutes=45)
    task_db.commit()

    notifications.check_no_show_tickets()

    assert _status(task_db, serving.id) == TicketDBStatus.SERVING
    assert _status(task_db, waiting.id) == TicketDBStatus.WAITING


def test_no_show_cleanup_renumbers_todays_line(task_db, make_queue, make_student):
    """Yesterday's leftovers inflated today's positions; after cleanup the
    waiting line starts at 1 again and serve-next picks today's student."""
    queue = make_queue()
    leftover = _take(task_db, queue, make_student())
    _backdate(task_db, leftover.id)
    today = _take(task_db, queue, make_student())
    assert today.position == 2

    notifications.check_no_show_tickets()

    task_db.expire_all()
    row = task_db.query(TicketDB).filter(TicketDB.id == today.id).one()
    assert row.position == 1
    assert TicketService(task_db).serve_next_ticket(queue.id).id == today.id


def test_update_wait_times_runs_without_error(task_db, make_queue, make_student, caplog):
    queue = make_queue()
    TicketService(task_db).create_ticket(TicketCreate(student_id=make_student().id, queue_id=queue.id))

    notifications.update_all_wait_times()

    assert "Error updating wait times" not in caplog.text


def test_reminder_check_runs_without_error(task_db, make_queue, make_student, caplog, monkeypatch):
    dispatched = []
    monkeypatch.setattr(notifications.send_ticket_reminder, "delay", dispatched.append)
    queue = make_queue()
    TicketService(task_db).create_ticket(TicketCreate(student_id=make_student().id, queue_id=queue.id))

    notifications.send_reminder_check()

    assert "Error checking tickets for reminders" not in caplog.text
    assert dispatched


def test_expire_appointments_runs_without_error(task_db, caplog):
    notifications.expire_stale_appointments()

    assert "Error expiring stale appointments" not in caplog.text


def test_reminders_are_not_scheduled_until_a_delivery_channel_exists():
    from app.worker import celery as worker_app

    scheduled = {entry["task"] for entry in worker_app.conf.beat_schedule.values()}
    assert "app.services.notifications.send_reminder_check" not in scheduled
    assert "app.services.notifications.check_no_show_tickets" in scheduled


def test_reminder_log_has_no_student_name(task_db, make_queue, make_student, caplog):
    caplog.set_level("INFO")
    queue = make_queue()
    student = make_student(first_name="Juana", last_name="Lunaria")
    ticket = _take(task_db, queue, student)

    notifications.send_ticket_reminder.run(ticket.id)

    assert "REMINDER" in caplog.text
    assert "Juana" not in caplog.text and "Lunaria" not in caplog.text
