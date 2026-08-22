import pytest
from datetime import time

from app.services.queue_service import QueueService
from app.models.queue import QueueCreate, QueueType, QueueStatus, QueueBookingSettings


def test_create_queue_defaults(db_session, make_queue):
    queue = make_queue(name="Enrollment Desk", ticket_letter="E")

    assert queue.name == "Enrollment Desk"
    assert queue.ticket_letter == "E"
    assert queue.status == QueueStatus.ACTIVE
    assert queue.current_ticket_number == 0
    assert queue.booking_enabled is False


def test_create_queue_rejects_duplicate_ticket_letter(db_session, make_queue):
    make_queue(ticket_letter="Z")

    service = QueueService(db_session)
    with pytest.raises(ValueError, match="already used"):
        service.create_queue(QueueCreate(
            name="Another Queue",
            queue_type=QueueType.OTHERS,
            ticket_letter="Z",
        ))


def test_pause_resume_close_queue(db_session, make_queue):
    queue = make_queue()
    service = QueueService(db_session)

    paused = service.pause_queue(queue.id)
    assert paused.status == QueueStatus.PAUSED

    resumed = service.resume_queue(queue.id)
    assert resumed.status == QueueStatus.ACTIVE

    closed = service.close_queue(queue.id)
    assert closed.status == QueueStatus.CLOSED


def test_update_booking_settings_enables_booking(db_session, make_queue):
    queue = make_queue()
    service = QueueService(db_session)

    updated = service.update_booking_settings(queue.id, QueueBookingSettings(
        booking_enabled=True,
        operating_start_time=time(8, 0),
        operating_end_time=time(17, 0),
        slot_capacity=5,
        booking_window_days=7,
    ))

    assert updated.booking_enabled is True
    assert updated.slot_capacity == 5
    assert updated.booking_window_days == 7


def test_update_booking_settings_rejects_start_after_end(db_session, make_queue):
    queue = make_queue()
    service = QueueService(db_session)

    with pytest.raises(ValueError, match="operating_start_time"):
        service.update_booking_settings(queue.id, QueueBookingSettings(
            booking_enabled=True,
            operating_start_time=time(17, 0),
            operating_end_time=time(8, 0),
            slot_capacity=3,
            booking_window_days=14,
        ))


def test_increment_ticket_number(db_session, make_queue):
    queue = make_queue()
    service = QueueService(db_session)

    first = service.increment_ticket_number(queue.id)
    second = service.increment_ticket_number(queue.id)

    assert first == 1
    assert second == 2
