from datetime import date, datetime, time, timedelta

import pytest

from app.services.appointment_service import (
    AppointmentExpiredError, AppointmentService, AppointmentWindowError,
    earliest_bookable_date,
)
from app.models.appointment import AppointmentCreate
from app.db_models import AppointmentDB, AppointmentDBStatus, UserRole


def _bookable_queue(make_queue, **overrides):
    defaults = dict(
        booking_enabled=True,
        operating_start_time=time(8, 0),
        operating_end_time=time(17, 0),
        slot_capacity=1,
        booking_window_days=14,
    )
    defaults.update(overrides)
    return make_queue(**defaults)


def test_availability_empty_when_booking_disabled(db_session, make_queue):
    queue = make_queue(booking_enabled=False)
    service = AppointmentService(db_session)

    slots = service.get_availability(queue.id, date.today() + timedelta(days=1))

    assert slots == []


def test_availability_computes_slots_from_queue_hours(db_session, make_queue):
    queue = _bookable_queue(make_queue, operating_start_time=time(8, 0), operating_end_time=time(9, 0))
    service = AppointmentService(db_session)

    slots = service.get_availability(queue.id, date.today() + timedelta(days=1))

    # queue's slot_duration_minutes defaults to 30 -> two 30-min slots between 8-9am
    assert len(slots) == 2
    assert slots[0].booked == 0
    assert slots[0].capacity == 1


def test_book_appointment_happy_path(db_session, make_queue, make_student):
    queue = _bookable_queue(make_queue)
    student = make_student()
    target_date = date.today() + timedelta(days=1)
    service = AppointmentService(db_session)
    slot = service.get_availability(queue.id, target_date)[0]

    booked = service.create_appointment(AppointmentCreate(
        student_id=student.id, queue_id=queue.id,
        appointment_date=target_date, slot_start_time=slot.slot_start_time,
    ))

    assert booked.reference_code.startswith("APT-")
    assert booked.qr_token
    assert booked.status == "booked"


def test_book_appointment_rejects_booking_disabled_queue(db_session, make_queue, make_student):
    queue = make_queue(booking_enabled=False)
    student = make_student()
    service = AppointmentService(db_session)

    with pytest.raises(ValueError, match="not open for appointment booking"):
        service.create_appointment(AppointmentCreate(
            student_id=student.id, queue_id=queue.id,
            appointment_date=date.today() + timedelta(days=1), slot_start_time=time(9, 0),
        ))


def test_book_appointment_rejects_full_slot(db_session, make_queue, make_student):
    queue = _bookable_queue(make_queue, slot_capacity=1)
    target_date = date.today() + timedelta(days=1)
    service = AppointmentService(db_session)
    slot = service.get_availability(queue.id, target_date)[0]

    service.create_appointment(AppointmentCreate(
        student_id=make_student().id, queue_id=queue.id,
        appointment_date=target_date, slot_start_time=slot.slot_start_time,
    ))

    with pytest.raises(ValueError, match="fully booked"):
        service.create_appointment(AppointmentCreate(
            student_id=make_student().id, queue_id=queue.id,
            appointment_date=target_date, slot_start_time=slot.slot_start_time,
        ))


def test_book_appointment_rejects_second_active_booking_for_same_student(db_session, make_queue, make_student):
    queue = _bookable_queue(make_queue, slot_capacity=5)
    student = make_student()
    target_date = date.today() + timedelta(days=1)
    service = AppointmentService(db_session)
    slots = service.get_availability(queue.id, target_date)

    service.create_appointment(AppointmentCreate(
        student_id=student.id, queue_id=queue.id,
        appointment_date=target_date, slot_start_time=slots[0].slot_start_time,
    ))

    with pytest.raises(ValueError, match="already have an active appointment"):
        service.create_appointment(AppointmentCreate(
            student_id=student.id, queue_id=queue.id,
            appointment_date=target_date, slot_start_time=slots[1].slot_start_time,
        ))


def test_book_appointment_rejects_beyond_booking_window(db_session, make_queue, make_student):
    queue = _bookable_queue(make_queue, booking_window_days=1)
    student = make_student()
    service = AppointmentService(db_session)

    with pytest.raises(ValueError, match="days in advance"):
        service.create_appointment(AppointmentCreate(
            student_id=student.id, queue_id=queue.id,
            appointment_date=date.today() + timedelta(days=5), slot_start_time=time(9, 0),
        ))


def test_lookup_and_cancel(db_session, make_queue, make_student):
    queue = _bookable_queue(make_queue)
    student = make_student()
    target_date = date.today() + timedelta(days=1)
    service = AppointmentService(db_session)
    slot = service.get_availability(queue.id, target_date)[0]
    booked = service.create_appointment(AppointmentCreate(
        student_id=student.id, queue_id=queue.id,
        appointment_date=target_date, slot_start_time=slot.slot_start_time,
    ))

    found = service.lookup(student.student_id, booked.reference_code)
    assert found is not None
    assert found.id == booked.id
    assert not hasattr(found, "qr_token")

    cancelled = service.cancel(booked.id, student.student_id)
    assert cancelled.status == "cancelled"

    # Slot should be free again
    slots_after = service.get_availability(queue.id, target_date)
    assert slots_after[0].booked == 0


def test_check_in_rejects_out_of_window_without_force(db_session, make_queue, make_student):
    queue = _bookable_queue(make_queue)
    student = make_student()
    target_date = date.today() + timedelta(days=1)
    service = AppointmentService(db_session)
    slot = service.get_availability(queue.id, target_date)[0]
    booked = service.create_appointment(AppointmentCreate(
        student_id=student.id, queue_id=queue.id,
        appointment_date=target_date, slot_start_time=slot.slot_start_time,
    ))

    with pytest.raises(AppointmentWindowError):
        service.check_in(token=booked.qr_token)


def test_check_in_creates_ticket_and_links_appointment(db_session, make_queue, make_student):
    queue = _bookable_queue(make_queue)
    student = make_student()
    target_date = date.today() + timedelta(days=1)
    service = AppointmentService(db_session)
    slot = service.get_availability(queue.id, target_date)[0]
    booked = service.create_appointment(AppointmentCreate(
        student_id=student.id, queue_id=queue.id,
        appointment_date=target_date, slot_start_time=slot.slot_start_time,
    ))

    ticket = service.check_in(token=booked.qr_token, force=True)

    assert ticket.student_id == student.id
    assert ticket.queue_id == queue.id

    appt_row = db_session.query(AppointmentDB).filter(AppointmentDB.id == booked.id).first()
    assert appt_row.status == AppointmentDBStatus.CHECKED_IN
    assert appt_row.ticket_id == ticket.id


def test_check_in_rejects_reuse_of_checked_in_token(db_session, make_queue, make_student):
    queue = _bookable_queue(make_queue)
    student = make_student()
    target_date = date.today() + timedelta(days=1)
    service = AppointmentService(db_session)
    slot = service.get_availability(queue.id, target_date)[0]
    booked = service.create_appointment(AppointmentCreate(
        student_id=student.id, queue_id=queue.id,
        appointment_date=target_date, slot_start_time=slot.slot_start_time,
    ))
    service.check_in(token=booked.qr_token, force=True)

    with pytest.raises(ValueError, match="already checked in"):
        service.check_in(token=booked.qr_token, force=True)


def test_search_excludes_checked_in_appointments(db_session, make_queue, make_student):
    queue = _bookable_queue(make_queue)
    student = make_student()
    target_date = date.today() + timedelta(days=1)
    service = AppointmentService(db_session)
    slot = service.get_availability(queue.id, target_date)[0]
    booked = service.create_appointment(AppointmentCreate(
        student_id=student.id, queue_id=queue.id,
        appointment_date=target_date, slot_start_time=slot.slot_start_time,
    ))

    found_before = service.search(booked.reference_code)
    assert any(r.id == booked.id for r in found_before)

    service.check_in(token=booked.qr_token, force=True)

    found_after = service.search(booked.reference_code)
    assert all(r.id != booked.id for r in found_after)


def test_expire_stale_appointments(db_session, make_queue, make_student):
    queue = _bookable_queue(make_queue)
    student = make_student()

    stale = AppointmentDB(
        reference_code="APT-STALE1",
        student_id=student.id,
        queue_id=queue.id,
        appointment_date=date.today() - timedelta(days=1),
        slot_start_time=time(8, 0),
        slot_end_time=time(8, 30),
        qr_token="stale-token-for-test",
        status=AppointmentDBStatus.BOOKED,
    )
    db_session.add(stale)
    db_session.commit()
    db_session.refresh(stale)

    service = AppointmentService(db_session)
    expired_count = service.expire_stale_appointments()

    assert expired_count >= 1
    db_session.refresh(stale)
    assert stale.status == AppointmentDBStatus.EXPIRED

    with pytest.raises(ValueError, match="expired"):
        service.check_in(reference_code=stale.reference_code)


def _expired_appointment(db_session, queue, student, reference_code="APT-EXPIR1"):
    appt = AppointmentDB(
        reference_code=reference_code,
        student_id=student.id,
        queue_id=queue.id,
        appointment_date=date.today() - timedelta(days=2),
        slot_start_time=time(9, 0),
        slot_end_time=time(9, 30),
        qr_token=f"token-{reference_code}",
        status=AppointmentDBStatus.EXPIRED,
    )
    db_session.add(appt)
    db_session.commit()
    db_session.refresh(appt)
    return appt


def test_check_in_expired_raises_expired_error_with_appointment(db_session, make_queue, make_student):
    queue = _bookable_queue(make_queue)
    appt = _expired_appointment(db_session, queue, make_student())
    service = AppointmentService(db_session)

    with pytest.raises(AppointmentExpiredError) as exc:
        service.check_in(reference_code=appt.reference_code)

    assert exc.value.appointment.id == appt.id
    # still a ValueError, so existing generic handlers keep working
    assert isinstance(exc.value, ValueError)


def test_checkin_api_answers_410_with_expiry_details(
    client, db_session, make_queue, make_student, make_user
):
    staff = make_user(role=UserRole.STAFF)
    queue = _bookable_queue(make_queue)
    appt = _expired_appointment(db_session, queue, make_student(), reference_code="APT-EXPIR2")
    client.post("/api/auth/login",
                data={"username": staff.username, "password": staff._plain_password})

    r = client.post("/api/appointments/checkin", json={"reference_code": appt.reference_code})

    assert r.status_code == 410
    detail = r.json()["detail"]
    assert detail["code"] == "appointment_expired"
    assert detail["reference_code"] == appt.reference_code
    assert detail["appointment_date"] == appt.appointment_date.isoformat()
    assert detail["slot_start_time"] == "09:00:00"
    assert "expired" in detail["message"]


def test_availability_is_empty_for_today(db_session, make_queue):
    queue = _bookable_queue(make_queue, operating_start_time=time(0, 0), operating_end_time=time(23, 30))
    service = AppointmentService(db_session)

    # Deliberately a full-day queue: were same-day booking still allowed, some
    # slot would always remain open no matter what time this test runs.
    assert service.get_availability(queue.id, date.today()) == []
    assert service.get_availability(queue.id, date.today() - timedelta(days=1)) == []


def test_availability_starts_from_tomorrow(db_session, make_queue):
    queue = _bookable_queue(make_queue)
    service = AppointmentService(db_session)

    slots = service.get_availability(queue.id, date.today() + timedelta(days=1))

    assert len(slots) > 0


def test_book_appointment_rejects_today(db_session, make_queue, make_student):
    queue = _bookable_queue(make_queue)
    student = make_student()
    service = AppointmentService(db_session)

    with pytest.raises(ValueError, match="at least one day ahead"):
        service.create_appointment(AppointmentCreate(
            student_id=student.id, queue_id=queue.id,
            appointment_date=date.today(), slot_start_time=time(9, 0),
        ))


def test_book_appointment_rejects_past_date(db_session, make_queue, make_student):
    queue = _bookable_queue(make_queue)
    student = make_student()
    service = AppointmentService(db_session)

    with pytest.raises(ValueError, match="at least one day ahead"):
        service.create_appointment(AppointmentCreate(
            student_id=student.id, queue_id=queue.id,
            appointment_date=date.today() - timedelta(days=1), slot_start_time=time(9, 0),
        ))


def test_earliest_bookable_date_is_tomorrow():
    assert earliest_bookable_date() == date.today() + timedelta(days=1)
