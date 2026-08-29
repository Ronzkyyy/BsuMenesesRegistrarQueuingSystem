import pytest

from app.services.ticket_service import TicketService
from app.models.ticket import TicketCreate
from app.models.ticket import PriorityLevel


def _ticket_for(db_session, student, queue, purpose="Test purpose"):
    service = TicketService(db_session)
    return service.create_ticket(TicketCreate(
        student_id=student.id, queue_id=queue.id, purpose=purpose,
    ))


def test_priority_from_graduating_flag(db_session, make_queue, make_student):
    queue = make_queue()
    student = make_student(is_graduating=True)

    ticket = _ticket_for(db_session, student, queue)

    assert ticket.priority == PriorityLevel.URGENT


def test_priority_from_scholar_or_varsity_flag(db_session, make_queue, make_student):
    queue = make_queue()
    student = make_student(is_scholar=True)

    ticket = _ticket_for(db_session, student, queue)

    assert ticket.priority == PriorityLevel.PRIORITY


def test_priority_normal_by_default(db_session, make_queue, make_student):
    queue = make_queue()
    student = make_student()

    ticket = _ticket_for(db_session, student, queue)

    assert ticket.priority == PriorityLevel.NORMAL


def test_urgent_ticket_jumps_ahead_of_normal_ticket_in_position(db_session, make_queue, make_student):
    queue = make_queue()
    normal_student = make_student()
    urgent_student = make_student(is_graduating=True)

    _ticket_for(db_session, normal_student, queue)
    urgent_ticket = _ticket_for(db_session, urgent_student, queue)

    # Re-fetch the normal ticket: creating the urgent ticket shifts existing
    # lower-priority tickets' positions, so the object returned at its own
    # creation time is now a stale snapshot.
    service = TicketService(db_session)
    normal_ticket_now = service.get_student_ticket(normal_student.student_id, queue.id)

    assert urgent_ticket.position < normal_ticket_now.position


def test_one_active_ticket_per_student_across_queues(db_session, make_queue, make_student):
    queue_a = make_queue()
    queue_b = make_queue()
    student = make_student()

    _ticket_for(db_session, student, queue_a)

    service = TicketService(db_session)
    with pytest.raises(ValueError, match="already have an active ticket"):
        service.create_ticket(TicketCreate(student_id=student.id, queue_id=queue_b.id))


def test_queue_at_capacity_returns_none(db_session, make_queue, make_student):
    queue = make_queue(max_capacity=1)
    first_student = make_student()
    second_student = make_student()

    first = _ticket_for(db_session, first_student, queue)
    assert first is not None

    result = _ticket_for(db_session, second_student, queue)
    assert result is None


def test_serve_next_prefers_higher_priority_over_arrival_order(db_session, make_queue, make_student):
    queue = make_queue()
    normal_student = make_student()
    urgent_student = make_student(is_graduating=True)

    normal_ticket = _ticket_for(db_session, normal_student, queue)
    _ticket_for(db_session, urgent_student, queue)

    service = TicketService(db_session)
    served = service.serve_next_ticket(queue.id)

    assert served.priority == PriorityLevel.URGENT
    assert served.id != normal_ticket.id


def test_full_ticket_lifecycle_serve_then_complete(db_session, make_queue, make_student):
    queue = make_queue()
    student = make_student()
    ticket = _ticket_for(db_session, student, queue)

    service = TicketService(db_session)
    served = service.serve_next_ticket(queue.id)
    assert served.id == ticket.id
    assert served.status == "serving"

    completed = service.mark_completed(ticket.id)
    assert completed.status == "completed"
    assert completed.completed_at is not None


def test_cancel_waiting_ticket_shifts_positions_behind_it(db_session, make_queue, make_student):
    queue = make_queue()
    first_student = make_student()
    second_student = make_student()

    first_ticket = _ticket_for(db_session, first_student, queue)
    second_ticket = _ticket_for(db_session, second_student, queue)
    assert second_ticket.position == first_ticket.position + 1

    service = TicketService(db_session)
    cancelled = service.cancel_ticket(first_ticket.id, first_student.student_id)
    assert cancelled.status == "cancelled"

    refreshed_second = service.get_student_ticket(second_student.student_id, queue.id)
    assert refreshed_second.position == first_ticket.position


def test_cancel_ticket_rejects_wrong_student_number(db_session, make_queue, make_student):
    """A caller can only cancel a ticket by proving ownership with the owner's
    10-digit student number - the endpoint is public, so this is the only
    authorization gate."""
    queue = make_queue()
    owner = make_student()
    other = make_student()
    ticket = _ticket_for(db_session, owner, queue)

    service = TicketService(db_session)

    assert service.cancel_ticket(ticket.id, other.student_id) is None
    assert service.cancel_ticket(ticket.id, "0000000000") is None
    # still cancellable by the real owner
    assert service.cancel_ticket(ticket.id, owner.student_id).status == "cancelled"


def test_get_student_ticket_unknown_number_returns_none(db_session):
    service = TicketService(db_session)
    assert service.get_student_ticket("0000000000") is None


def test_mark_no_show(db_session, make_queue, make_student):
    queue = make_queue()
    student = make_student()
    ticket = _ticket_for(db_session, student, queue)

    service = TicketService(db_session)
    no_show = service.mark_no_show(ticket.id)

    assert no_show.status == "no_show"
