"""
Ticket management endpoints
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional

from ..core.database import get_db
from ..core.security import get_current_active_user, require_role
from ..db_models import UserRole, TicketDBStatus
from ..models.ticket import (
    Ticket, TicketCreate, TicketPublic, TicketStatus, PriorityLevel as PydanticPriorityLevel
)
from ..models.user import User
from ..services import TicketService


router = APIRouter()


@router.post("", response_model=Ticket)
def create_ticket(
    ticket: TicketCreate,
    db: Session = Depends(get_db)
):
    """Student takes a queue ticket (public endpoint)"""
    service = TicketService(db)
    result = service.create_ticket(ticket)
    if not result:
        raise HTTPException(
            status_code=400,
            detail="Could not create ticket. Queue may be full, inactive, or student already has an active ticket."
        )
    return result


@router.get("/my-ticket", response_model=Ticket)
def get_my_ticket(
    student_id: int,
    queue_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Get student's current ticket, optionally scoped to one queue (public endpoint)"""
    service = TicketService(db)
    ticket = service.get_student_ticket(student_id, queue_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="No active ticket found")
    return ticket


@router.get("/my-tickets", response_model=List[Ticket])
def get_my_tickets(
    student_id: int,
    db: Session = Depends(get_db)
):
    """Get all of a student's currently active tickets, across every queue (public endpoint)"""
    service = TicketService(db)
    return service.get_student_tickets(student_id)


@router.post("/{ticket_id}/cancel", response_model=Ticket)
def cancel_ticket(
    ticket_id: int,
    db: Session = Depends(get_db)
):
    """Student cancels their ticket (public endpoint)"""
    service = TicketService(db)
    ticket = service.cancel_ticket(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found or cannot be cancelled")
    return ticket


@router.post("/{ticket_id}/complete", response_model=Ticket)
def complete_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.REGISTRAR, UserRole.STAFF))
):
    """Registrar marks ticket as completed"""
    service = TicketService(db)
    ticket = service.mark_completed(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


@router.post("/{ticket_id}/serve", response_model=Ticket)
def serve_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.REGISTRAR, UserRole.STAFF))
):
    """Mark ticket as currently being served"""
    service = TicketService(db)
    ticket = service.serve_ticket(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found or not waiting")
    return ticket


@router.post("/{ticket_id}/no-show", response_model=Ticket)
def mark_no_show(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.REGISTRAR, UserRole.STAFF))
):
    """Mark ticket as no-show"""
    service = TicketService(db)
    ticket = service.mark_no_show(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


@router.get("/queue/{queue_id}", response_model=List[Ticket])
def get_queue_tickets(
    queue_id: int,
    status: Optional[TicketStatus] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get all tickets for a queue (for display)"""
    service = TicketService(db)

    # Convert Pydantic status to DB status if provided
    db_status = None
    if status:
        db_status = TicketDBStatus(status.value)

    tickets = service.get_queue_tickets(queue_id, db_status)
    return tickets


@router.get("/queue/{queue_id}/display", response_model=List[TicketPublic])
def get_queue_display(
    queue_id: int,
    db: Session = Depends(get_db)
):
    """Get tickets for public display board (limited info)"""
    service = TicketService(db)
    return service.get_queue_display(queue_id)


@router.get("/now-serving-overview")
def get_now_serving_overview(
    db: Session = Depends(get_db)
):
    """Get now-serving/waiting summary for every active queue (public display endpoint)"""
    service = TicketService(db)
    return service.get_now_serving_overview()


@router.post("/queue/{queue_id}/next", response_model=Ticket)
def serve_next_ticket(
    queue_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.REGISTRAR, UserRole.STAFF))
):
    """Serve the next ticket in queue (considering priority)"""
    service = TicketService(db)
    ticket = service.serve_next_ticket(queue_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="No waiting tickets in queue")
    return ticket