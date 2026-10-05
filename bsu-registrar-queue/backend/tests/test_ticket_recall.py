"""Recall: a skipped (no-show) ticket can be brought back and served
immediately - once per ticket, and only for tickets taken today (campus time).
"""
from datetime import timedelta

import pytest

from app.db_models import TicketDB, UserRole
from app.models.ticket import TicketCreate
from app.services.ticket_service import TicketService


def _skipped_ticket(db_session, make_queue, make_student):
    queue = make_queue()
    student = make_student()
    service = TicketService(db_session)
    service.create_ticket(TicketCreate(student_id=student.id, queue_id=queue.id))
    served = service.serve_next_ticket(queue.id)
    service.mark_no_show(served.id)
    return service, queue, served


def test_recall_serves_skipped_ticket_immediately(db_session, make_queue, make_student):
    service, queue, ticket = _skipped_ticket(db_session, make_queue, make_student)

    recalled = service.recall_ticket(ticket.id)

    assert recalled.status == "serving"
    assert recalled.recalled_at is not None
    assert recalled.called_at is not None
    assert recalled.served_at is not None


def test_recall_only_once(db_session, make_queue, make_student):
    service, queue, ticket = _skipped_ticket(db_session, make_queue, make_student)
    service.recall_ticket(ticket.id)
    service.mark_no_show(ticket.id)

    with pytest.raises(ValueError, match="already been recalled"):
        service.recall_ticket(ticket.id)


def test_recall_rejects_ticket_that_was_not_skipped(db_session, make_queue, make_student):
    queue = make_queue()
    student = make_student()
    service = TicketService(db_session)
    ticket = service.create_ticket(TicketCreate(student_id=student.id, queue_id=queue.id))

    with pytest.raises(ValueError, match="Only skipped tickets"):
        service.recall_ticket(ticket.id)


def test_recall_rejects_ticket_from_a_previous_day(db_session, make_queue, make_student):
    service, queue, ticket = _skipped_ticket(db_session, make_queue, make_student)
    row = db_session.query(TicketDB).filter(TicketDB.id == ticket.id).one()
    row.created_at = service._campus_today_start() - timedelta(minutes=1)
    db_session.commit()

    with pytest.raises(ValueError, match="from today"):
        service.recall_ticket(ticket.id)


def test_recall_unknown_ticket_returns_none(db_session):
    assert TicketService(db_session).recall_ticket(999999) is None


def test_recallable_list_only_has_todays_unrecalled_skips(db_session, make_queue, make_student):
    service, queue, ticket = _skipped_ticket(db_session, make_queue, make_student)
    assert [t.id for t in service.get_recallable_tickets(queue.id)] == [ticket.id]

    service.recall_ticket(ticket.id)
    service.mark_no_show(ticket.id)
    assert service.get_recallable_tickets(queue.id) == []


def _login(client, user):
    return client.post("/api/auth/login", data={"username": user.username, "password": user._plain_password})


def test_recall_api_requires_login(client, db_session, make_queue, make_student):
    _, _, ticket = _skipped_ticket(db_session, make_queue, make_student)
    assert client.post(f"/api/tickets/{ticket.id}/recall").status_code == 401


def test_recall_api_staff_recall_then_second_recall_rejected(client, db_session, make_queue, make_student, make_user):
    _, queue, ticket = _skipped_ticket(db_session, make_queue, make_student)
    assert _login(client, make_user(role=UserRole.STAFF)).status_code == 200

    listed = client.get(f"/api/tickets/queue/{queue.id}/recallable")
    assert listed.status_code == 200
    assert [t["id"] for t in listed.json()] == [ticket.id]

    resp = client.post(f"/api/tickets/{ticket.id}/recall")
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "serving"

    client.post(f"/api/tickets/{ticket.id}/no-show")
    again = client.post(f"/api/tickets/{ticket.id}/recall")
    assert again.status_code == 400
    assert "already been recalled" in again.json()["detail"]
