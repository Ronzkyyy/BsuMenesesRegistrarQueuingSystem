from datetime import date, datetime, time, timedelta

import pytest

from app.services.appointment_service import (
    AppointmentExpiredError, AppointmentService, AppointmentWindowError,
    earliest_bookable_date,
)
from app.models.appointment import AppointmentCreate
from app.models.ticket import DocumentType
from app.models.queue import QueueType
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


def test_book_appointment_for_document_request_requires_document_type(db_session, make_queue, make_student):
    queue = _bookable_queue(make_queue, queue_type=QueueType.DOCUMENT_REQUEST)
    student = make_student()
    target_date = date.today() + timedelta(days=1)
    service = AppointmentService(db_session)
    slot = service.get_availability(queue.id, target_date)[0]

    with pytest.raises(ValueError, match="Select which document"):
        service.create_appointment(AppointmentCreate(
            student_id=student.id, queue_id=queue.id,
            appointment_date=target_date, slot_start_time=slot.slot_start_time,
        ))


def test_book_appointment_rejects_document_type_outside_document_request(db_session, make_queue, make_student):
    queue = _bookable_queue(make_queue)  # not Document Request
    student = make_student()
    target_date = date.today() + timedelta(days=1)
    service = AppointmentService(db_session)
    slot = service.get_availability(queue.id, target_date)[0]

    with pytest.raises(ValueError, match="only accepted for the Request Documents service"):
        service.create_appointment(AppointmentCreate(
            student_id=student.id, queue_id=queue.id,
            appointment_date=target_date, slot_start_time=slot.slot_start_time,
            document_type=DocumentType.TOR,
        ))


def test_check_in_carries_document_type_onto_the_created_ticket(db_session, make_queue, make_student):
    queue = _bookable_queue(make_queue, queue_type=QueueType.DOCUMENT_REQUEST)
    student = make_student()
    target_date = date.today() + timedelta(days=1)
    service = AppointmentService(db_session)
    slot = service.get_availability(queue.id, target_date)[0]
    booked = service.create_appointment(AppointmentCreate(
        student_id=student.id, queue_id=queue.id,
        appointment_date=target_date, slot_start_time=slot.slot_start_time,
        document_type=DocumentType.COR,
    ))

    assert booked.document_type == DocumentType.COR

    ticket = service.check_in(token=booked.qr_token, force=True)

    assert ticket.document_type == DocumentType.COR


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


def test_search_includes_expired_appointments(db_session, make_queue, make_student):
    queue = _bookable_queue(make_queue)
    appt = _expired_appointment(db_session, queue, make_student(), reference_code="APT-EXPIR3")
    service = AppointmentService(db_session)

    found = service.search(appt.reference_code)

    assert any(r.id == appt.id for r in found)


def test_staff_cancel_expired_cancels_an_expired_appointment(db_session, make_queue, make_student):
    queue = _bookable_queue(make_queue)
    appt = _expired_appointment(db_session, queue, make_student(), reference_code="APT-EXPIR4")
    service = AppointmentService(db_session)

    cancelled = service.staff_cancel_expired(appt.id)

    assert cancelled.status == "cancelled"
    db_session.refresh(appt)
    assert appt.status == AppointmentDBStatus.CANCELLED


def test_staff_cancel_expired_cancels_a_stale_booked_appointment(db_session, make_queue, make_student):
    # Still BOOKED (the periodic task hasn't caught it yet), but well past the
    # buffer - staff_cancel_expired should treat this the same as EXPIRED.
    queue = _bookable_queue(make_queue)
    student = make_student()
    stale = AppointmentDB(
        reference_code="APT-STALE2", student_id=student.id, queue_id=queue.id,
        appointment_date=date.today() - timedelta(days=1),
        slot_start_time=time(8, 0), slot_end_time=time(8, 30),
        qr_token="stale-token-for-cancel-test", status=AppointmentDBStatus.BOOKED,
    )
    db_session.add(stale)
    db_session.commit()
    db_session.refresh(stale)
    service = AppointmentService(db_session)

    cancelled = service.staff_cancel_expired(stale.id)

    assert cancelled.status == "cancelled"


def test_staff_cancel_expired_rejects_a_still_valid_booking(db_session, make_queue, make_student):
    queue = _bookable_queue(make_queue)
    student = make_student()
    target_date = date.today() + timedelta(days=1)
    service = AppointmentService(db_session)
    slot = service.get_availability(queue.id, target_date)[0]
    booked = service.create_appointment(AppointmentCreate(
        student_id=student.id, queue_id=queue.id,
        appointment_date=target_date, slot_start_time=slot.slot_start_time,
    ))

    with pytest.raises(ValueError, match="overdue"):
        service.staff_cancel_expired(booked.id)


def test_staff_cancel_expired_returns_none_for_missing_appointment(db_session):
    service = AppointmentService(db_session)

    assert service.staff_cancel_expired(999999) is None


def test_staff_cancel_api_removes_expired_appointment(client, db_session, make_queue, make_student, make_user):
    staff = make_user(role=UserRole.STAFF)
    queue = _bookable_queue(make_queue)
    appt = _expired_appointment(db_session, queue, make_student(), reference_code="APT-EXPIR5")
    client.post("/api/auth/login",
                data={"username": staff.username, "password": staff._plain_password})

    r = client.patch(f"/api/appointments/{appt.id}/staff-cancel")

    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"


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


def test_list_appointments_upcoming_includes_only_future_booked(db_session, make_queue, make_student):
    queue = _bookable_queue(make_queue)
    service = AppointmentService(db_session)
    student = make_student()
    upcoming_appt = service.create_appointment(AppointmentCreate(
        student_id=student.id, queue_id=queue.id,
        appointment_date=date.today() + timedelta(days=1), slot_start_time=time(9, 0),
    ))
    # A past, resolved appointment - must not show up in the upcoming view.
    _expired_appointment(db_session, queue, make_student(), reference_code="APT-UPC1")

    items, total = service.list_appointments(upcoming=True)

    assert total == 1
    assert items[0].id == upcoming_appt.id
    assert items[0].student_number == student.student_id
    assert items[0].student_name == f"{student.first_name} {student.last_name}"
    assert items[0].queue_name == queue.name


def test_list_appointments_past_includes_expired_and_historical(db_session, make_queue, make_student):
    queue = _bookable_queue(make_queue)
    service = AppointmentService(db_session)
    make_student_for_upcoming = make_student()
    service.create_appointment(AppointmentCreate(
        student_id=make_student_for_upcoming.id, queue_id=queue.id,
        appointment_date=date.today() + timedelta(days=1), slot_start_time=time(9, 0),
    ))
    expired = _expired_appointment(db_session, queue, make_student(), reference_code="APT-PAST1")

    items, total = service.list_appointments(upcoming=False)

    assert total == 1
    assert items[0].id == expired.id


def test_list_appointments_filters_by_date_range(db_session, make_queue, make_student):
    queue = _bookable_queue(make_queue)
    service = AppointmentService(db_session)
    near = service.create_appointment(AppointmentCreate(
        student_id=make_student().id, queue_id=queue.id,
        appointment_date=date.today() + timedelta(days=1), slot_start_time=time(9, 0),
    ))
    service.create_appointment(AppointmentCreate(
        student_id=make_student().id, queue_id=queue.id,
        appointment_date=date.today() + timedelta(days=10), slot_start_time=time(9, 0),
    ))

    items, total = service.list_appointments(
        upcoming=True,
        date_from=date.today(),
        date_to=date.today() + timedelta(days=2),
    )

    assert total == 1
    assert items[0].id == near.id


def test_list_appointments_paginates(db_session, make_queue, make_student):
    queue = _bookable_queue(make_queue, slot_capacity=5)
    service = AppointmentService(db_session)
    for _ in range(3):
        service.create_appointment(AppointmentCreate(
            student_id=make_student().id, queue_id=queue.id,
            appointment_date=date.today() + timedelta(days=1), slot_start_time=time(9, 0),
        ))

    page1, total = service.list_appointments(upcoming=True, skip=0, limit=2)
    page2, _ = service.list_appointments(upcoming=True, skip=2, limit=2)

    assert total == 3
    assert len(page1) == 2
    assert len(page2) == 1


def test_list_appointments_api_requires_staff_login(client, make_queue, make_student):
    queue = _bookable_queue(make_queue)
    student = make_student()
    client.post("/api/appointments", json={
        "student_id": student.id, "queue_id": queue.id,
        "appointment_date": (date.today() + timedelta(days=1)).isoformat(),
        "slot_start_time": "09:00:00",
    })

    r = client.get("/api/appointments")

    assert r.status_code == 401


def test_list_appointments_api_returns_bookings_with_student_identity(
    client, make_queue, make_student, make_user
):
    staff = make_user(role=UserRole.STAFF)
    queue = _bookable_queue(make_queue)
    student = make_student()
    client.post("/api/appointments", json={
        "student_id": student.id, "queue_id": queue.id,
        "appointment_date": (date.today() + timedelta(days=1)).isoformat(),
        "slot_start_time": "09:00:00",
    })
    client.post("/api/auth/login",
                data={"username": staff.username, "password": staff._plain_password})

    r = client.get("/api/appointments")

    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["student_number"] == student.student_id
    assert body["items"][0]["student_name"] == f"{student.first_name} {student.last_name}"
