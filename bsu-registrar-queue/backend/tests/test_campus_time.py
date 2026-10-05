"""Appointment rules run on the campus clock (Asia/Manila), not the server's.

Production runs on UTC, 8 hours behind campus. These tests pin the clock to
early-morning Manila times - when the UTC date is still "yesterday" - which is
exactly where the old date.today()/datetime.now() logic went wrong.
"""
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import pytest

from app.core import campus_time
from app.db_models import AppointmentDB, AppointmentDBStatus
from app.services.appointment_service import (
    AppointmentService, AppointmentWindowError, earliest_bookable_date,
)

MANILA = ZoneInfo("Asia/Manila")
DAY = date(2026, 10, 6)


@pytest.fixture()
def pin_clock(monkeypatch):
    def _pin(hour, minute=0, day=DAY):
        moment = datetime.combine(day, time(hour, minute), tzinfo=MANILA)
        monkeypatch.setattr(campus_time, "campus_now", lambda: moment)
        return moment
    return _pin


def _booked(db_session, queue, student, start=time(9, 0), end=time(9, 30), ref="APT-TZTEST"):
    appt = AppointmentDB(
        reference_code=ref,
        student_id=student.id,
        queue_id=queue.id,
        appointment_date=DAY,
        slot_start_time=start,
        slot_end_time=end,
        qr_token=f"token-{ref}",
        status=AppointmentDBStatus.BOOKED,
    )
    db_session.add(appt)
    db_session.commit()
    db_session.refresh(appt)
    return appt


def test_today_follows_campus_calendar_before_8am(pin_clock):
    moment = pin_clock(7, 0)
    assert moment.astimezone(ZoneInfo("UTC")).date() == date(2026, 10, 5)  # UTC is still "yesterday"

    assert campus_time.campus_today() == DAY
    assert earliest_bookable_date() == date(2026, 10, 7)


def test_check_in_window_uses_campus_time(db_session, make_queue, make_student, pin_clock):
    """08:45 Manila is inside a 09:00 slot's 30-minute early window. On a UTC
    clock it read as 00:45 and was rejected as out of window."""
    appt = _booked(db_session, make_queue(), make_student())
    pin_clock(8, 45)

    ticket = AppointmentService(db_session).check_in(reference_code=appt.reference_code)

    assert ticket is not None


def test_check_in_too_early_is_still_rejected(db_session, make_queue, make_student, pin_clock):
    appt = _booked(db_session, make_queue(), make_student())
    pin_clock(8, 0)

    with pytest.raises(AppointmentWindowError):
        AppointmentService(db_session).check_in(reference_code=appt.reference_code)


def test_already_checked_in_message_shows_campus_time(db_session, make_queue, make_student, pin_clock):
    appt = _booked(db_session, make_queue(), make_student())
    pin_clock(8, 45)
    service = AppointmentService(db_session)
    service.check_in(reference_code=appt.reference_code)

    with pytest.raises(ValueError, match="08:45 AM"):
        service.check_in(reference_code=appt.reference_code)


@pytest.mark.parametrize("hour, minute, expect_expired", [(10, 29, False), (10, 31, True)])
def test_expiry_is_one_hour_after_slot_end_in_campus_time(
    db_session, make_queue, make_student, pin_clock, hour, minute, expect_expired
):
    """09:30 slot end + 60-minute buffer = 10:30 Manila. On a UTC clock this
    didn't happen until 18:30 Manila."""
    appt = _booked(db_session, make_queue(), make_student())
    pin_clock(hour, minute)

    AppointmentService(db_session).expire_stale_appointments()

    db_session.refresh(appt)
    expected = AppointmentDBStatus.EXPIRED if expect_expired else AppointmentDBStatus.BOOKED
    assert appt.status == expected


def test_campus_today_start_is_campus_midnight(pin_clock):
    pin_clock(7, 0)
    start = campus_time.campus_today_start()
    assert start == datetime.combine(DAY, time.min, tzinfo=MANILA)
