"""
Ticket service - core queue logic for student tickets
"""
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
from sqlalchemy import func, and_, case

from ..db_models import (
    TicketDB, TicketDBStatus, PriorityLevel,
    StudentDB, QueueDB, QueueDBStatus
)
from ..models.ticket import (
    Ticket, TicketCreate, TicketStatus, PriorityLevel as PydanticPriorityLevel,
    TicketPublic
)
from ..models.student import Student
from ..models.queue import Queue


class TicketService:
    def __init__(self, db: Session):
        self.db = db

    def calculate_priority(self, student: StudentDB) -> PriorityLevel:
        """Determine ticket priority based on student status"""
        if student.is_graduating:
            return PriorityLevel.URGENT
        elif student.is_scholar or student.is_varsity:
            return PriorityLevel.PRIORITY
        return PriorityLevel.NORMAL

    def calculate_position(self, queue_id: int, priority: PriorityLevel) -> int:
        """Calculate next position, considering priority tickets"""
        # Priority order: URGENT first, then PRIORITY, then NORMAL
        # Within same priority, FIFO by created_at

        # Count waiting/serving tickets with higher or equal priority
        priority_order = {
            PriorityLevel.URGENT: 3,
            PriorityLevel.PRIORITY: 2,
            PriorityLevel.NORMAL: 1,
        }

        target_priority_value = priority_order[priority]

        # Count tickets that should be served before this one
        count = self.db.query(func.count(TicketDB.id)).filter(
            TicketDB.queue_id == queue_id,
            TicketDB.status.in_([TicketDBStatus.WAITING, TicketDBStatus.SERVING]),
            case(
                (TicketDB.priority == PriorityLevel.URGENT, 3),
                (TicketDB.priority == PriorityLevel.PRIORITY, 2),
                else_=1
            ) >= target_priority_value
        ).scalar()

        return (count or 0) + 1

    def estimate_wait_time(self, queue_id: int, position: int) -> int:
        """Estimate wait time based on historical data and queue length"""
        queue = self.db.query(QueueDB).filter(QueueDB.id == queue_id).first()
        if not queue:
            return 0

        # Base estimate: position * slot_duration
        base_wait = position * queue.slot_duration_minutes

        # Adjust based on current serving status
        serving_count = self.db.query(func.count(TicketDB.id)).filter(
            TicketDB.queue_id == queue_id,
            TicketDB.status == TicketDBStatus.SERVING
        ).scalar()

        if serving_count and serving_count > 0:
            # Someone is currently being served, add remaining time
            base_wait += queue.slot_duration_minutes

        return max(base_wait, 0)

    def create_ticket(self, ticket_data: TicketCreate) -> Optional[Ticket]:
        """Create a new ticket for a student"""
        # Verify student exists
        student = self.db.query(StudentDB).filter(StudentDB.id == ticket_data.student_id).first()
        if not student:
            return None

        # Verify queue exists and is active
        queue = self.db.query(QueueDB).filter(
            QueueDB.id == ticket_data.queue_id,
            QueueDB.status == QueueDBStatus.ACTIVE
        ).first()
        if not queue:
            return None

        # Check if student already has an active ticket in this queue
        existing = self.db.query(TicketDB).filter(
            TicketDB.student_id == ticket_data.student_id,
            TicketDB.queue_id == ticket_data.queue_id,
            TicketDB.status.in_([TicketDBStatus.WAITING, TicketDBStatus.SERVING])
        ).first()
        if existing:
            return None  # Student already has active ticket

        # Check queue capacity
        waiting_count = self.db.query(func.count(TicketDB.id)).filter(
            TicketDB.queue_id == ticket_data.queue_id,
            TicketDB.status.in_([TicketDBStatus.WAITING, TicketDBStatus.SERVING])
        ).scalar()

        if waiting_count and waiting_count >= queue.max_capacity:
            return None  # Queue at capacity

        # Calculate priority
        priority = self.calculate_priority(student)
        if not queue.allow_priority:
            priority = PriorityLevel.NORMAL

        # Get next ticket number
        next_ticket_number = self._get_next_ticket_number(queue.id)

        # Calculate position
        position = self.calculate_position(queue.id, priority)

        # Make room for the new ticket by shifting existing tickets that sit
        # at or after this position, BEFORE inserting - otherwise the new
        # ticket would already be in the table and get caught by its own
        # shift query.
        self._update_positions_after_insert(queue.id, position)

        # Estimate wait time
        estimated_wait = self.estimate_wait_time(queue.id, position)

        # Create ticket
        db_ticket = TicketDB(
            ticket_number=next_ticket_number,
            student_id=ticket_data.student_id,
            queue_id=ticket_data.queue_id,
            priority=priority,
            purpose=ticket_data.purpose,
            status=TicketDBStatus.WAITING,
            position=position,
            estimated_wait_time_minutes=estimated_wait,
        )
        self.db.add(db_ticket)
        self.db.commit()
        self.db.refresh(db_ticket)

        return self._to_ticket(db_ticket, student, queue)

    def _get_next_ticket_number(self, queue_id: int) -> int:
        """Get next ticket number for a queue"""
        queue = self.db.query(QueueDB).filter(QueueDB.id == queue_id).first()
        if not queue:
            return 1
        queue.current_ticket_number += 1
        self.db.commit()
        return queue.current_ticket_number

    def _update_positions_after_insert(self, queue_id: int, new_position: int):
        """Make room for a new ticket by bumping existing tickets at or after
        new_position back by one. Must be called BEFORE the new ticket is
        inserted, otherwise it would match its own query and get bumped too.
        """
        tickets = self.db.query(TicketDB).filter(
            TicketDB.queue_id == queue_id,
            TicketDB.status.in_([TicketDBStatus.WAITING, TicketDBStatus.SERVING]),
            TicketDB.position >= new_position,
        ).all()

        for ticket in tickets:
            ticket.position += 1
            # Recalculate wait time
            ticket.estimated_wait_time_minutes = self.estimate_wait_time(queue_id, ticket.position)

        self.db.commit()

    def serve_next_ticket(self, queue_id: int) -> Optional[Ticket]:
        """Get the next ticket to serve (considering priority)"""
        # Find highest priority waiting ticket
        # Order by priority desc, then created_at asc
        priority_order = case(
            (TicketDB.priority == PriorityLevel.URGENT, 3),
            (TicketDB.priority == PriorityLevel.PRIORITY, 2),
            else_=1
        )

        ticket = self.db.query(TicketDB).filter(
            TicketDB.queue_id == queue_id,
            TicketDB.status == TicketDBStatus.WAITING
        ).order_by(
            priority_order.desc(),
            TicketDB.created_at.asc()
        ).first()

        if not ticket:
            return None

        # Update ticket status
        ticket.status = TicketDBStatus.SERVING
        ticket.served_at = datetime.now()
        ticket.updated_at = datetime.now()

        # Update positions of remaining waiting tickets
        self._update_positions_after_serve(queue_id, ticket.position)

        self.db.commit()
        self.db.refresh(ticket)

        # Get student and queue for full ticket object
        student = self.db.query(StudentDB).filter(StudentDB.id == ticket.student_id).first()
        queue = self.db.query(QueueDB).filter(QueueDB.id == ticket.queue_id).first()

        return self._to_ticket(ticket, student, queue)

    def serve_ticket(self, ticket_id: int) -> Optional[Ticket]:
        """Mark a specific waiting ticket as being served (out-of-order serve)"""
        ticket = self.db.query(TicketDB).filter(TicketDB.id == ticket_id).first()
        if not ticket or ticket.status != TicketDBStatus.WAITING:
            return None

        ticket.status = TicketDBStatus.SERVING
        ticket.served_at = datetime.now()
        ticket.updated_at = datetime.now()

        self._update_positions_after_serve(ticket.queue_id, ticket.position)

        self.db.commit()
        self.db.refresh(ticket)

        student = self.db.query(StudentDB).filter(StudentDB.id == ticket.student_id).first()
        queue = self.db.query(QueueDB).filter(QueueDB.id == ticket.queue_id).first()

        return self._to_ticket(ticket, student, queue)

    def _update_positions_after_serve(self, queue_id: int, served_position: int):
        """Update positions after a ticket is served"""
        tickets = self.db.query(TicketDB).filter(
            TicketDB.queue_id == queue_id,
            TicketDB.status == TicketDBStatus.WAITING,
            TicketDB.position > served_position
        ).all()

        for ticket in tickets:
            ticket.position -= 1
            ticket.estimated_wait_time_minutes = self.estimate_wait_time(queue_id, ticket.position)

        self.db.commit()

    def mark_completed(self, ticket_id: int) -> Optional[Ticket]:
        """Mark ticket as completed"""
        ticket = self.db.query(TicketDB).filter(TicketDB.id == ticket_id).first()
        if not ticket:
            return None

        was_waiting = ticket.status == TicketDBStatus.WAITING
        old_position = ticket.position

        ticket.status = TicketDBStatus.COMPLETED
        ticket.completed_at = datetime.now()
        ticket.updated_at = datetime.now()
        self.db.commit()

        # If the ticket was completed directly while still waiting (skipping
        # the serve step), the tickets behind it never had their positions
        # shifted up - do that now, same as cancelling a waiting ticket.
        if was_waiting:
            self._update_positions_after_cancel(ticket.queue_id, old_position)

        self.db.refresh(ticket)

        student = self.db.query(StudentDB).filter(StudentDB.id == ticket.student_id).first()
        queue = self.db.query(QueueDB).filter(QueueDB.id == ticket.queue_id).first()

        return self._to_ticket(ticket, student, queue)

    def mark_no_show(self, ticket_id: int) -> Optional[Ticket]:
        """Mark ticket as no-show after timeout"""
        ticket = self.db.query(TicketDB).filter(TicketDB.id == ticket_id).first()
        if not ticket:
            return None

        was_waiting = ticket.status == TicketDBStatus.WAITING
        old_position = ticket.position

        ticket.status = TicketDBStatus.NO_SHOW
        ticket.updated_at = datetime.now()
        self.db.commit()

        if was_waiting:
            self._update_positions_after_cancel(ticket.queue_id, old_position)

        self.db.refresh(ticket)

        student = self.db.query(StudentDB).filter(StudentDB.id == ticket.student_id).first()
        queue = self.db.query(QueueDB).filter(QueueDB.id == ticket.queue_id).first()

        return self._to_ticket(ticket, student, queue)

    def cancel_ticket(self, ticket_id: int) -> Optional[Ticket]:
        """Cancel a student's ticket"""
        ticket = self.db.query(TicketDB).filter(TicketDB.id == ticket_id).first()
        if not ticket:
            return None

        if ticket.status not in [TicketDBStatus.WAITING, TicketDBStatus.SERVING]:
            return None

        old_position = ticket.position
        ticket.status = TicketDBStatus.CANCELLED
        ticket.updated_at = datetime.now()
        self.db.commit()

        # Update positions of remaining tickets
        self._update_positions_after_cancel(ticket.queue_id, old_position)

        self.db.refresh(ticket)

        student = self.db.query(StudentDB).filter(StudentDB.id == ticket.student_id).first()
        queue = self.db.query(QueueDB).filter(QueueDB.id == ticket.queue_id).first()

        return self._to_ticket(ticket, student, queue)

    def _update_positions_after_cancel(self, queue_id: int, cancelled_position: int):
        """Update positions after a ticket is cancelled"""
        tickets = self.db.query(TicketDB).filter(
            TicketDB.queue_id == queue_id,
            TicketDB.status.in_([TicketDBStatus.WAITING, TicketDBStatus.SERVING]),
            TicketDB.position > cancelled_position
        ).all()

        for ticket in tickets:
            ticket.position -= 1
            ticket.estimated_wait_time_minutes = self.estimate_wait_time(queue_id, ticket.position)

        self.db.commit()

    def get_queue_tickets(self, queue_id: int, status: Optional[TicketDBStatus] = None) -> List[Ticket]:
        """Get all tickets for a queue"""
        query = self.db.query(TicketDB).filter(TicketDB.queue_id == queue_id)
        if status:
            query = query.filter(TicketDB.status == status)
        tickets = query.order_by(TicketDB.position).all()

        result = []
        for ticket in tickets:
            student = self.db.query(StudentDB).filter(StudentDB.id == ticket.student_id).first()
            queue = self.db.query(QueueDB).filter(QueueDB.id == ticket.queue_id).first()
            result.append(self._to_ticket(ticket, student, queue))
        return result

    def get_student_ticket(self, student_id: int, queue_id: Optional[int] = None) -> Optional[Ticket]:
        """Get student's current active ticket, optionally scoped to one queue.

        Without queue_id, a student holding active tickets in multiple queues
        would non-deterministically get back whichever ticket the query finds
        first - always pass queue_id when checking a specific queue's page.
        """
        query = self.db.query(TicketDB).filter(
            TicketDB.student_id == student_id,
            TicketDB.status.in_([TicketDBStatus.WAITING, TicketDBStatus.SERVING])
        )
        if queue_id is not None:
            query = query.filter(TicketDB.queue_id == queue_id)
        ticket = query.first()

        if not ticket:
            return None

        student = self.db.query(StudentDB).filter(StudentDB.id == ticket.student_id).first()
        queue = self.db.query(QueueDB).filter(QueueDB.id == ticket.queue_id).first()

        return self._to_ticket(ticket, student, queue)

    def get_student_tickets(self, student_id: int) -> List[Ticket]:
        """Get all of a student's currently active tickets, across every queue"""
        tickets = self.db.query(TicketDB).filter(
            TicketDB.student_id == student_id,
            TicketDB.status.in_([TicketDBStatus.WAITING, TicketDBStatus.SERVING])
        ).all()

        student = self.db.query(StudentDB).filter(StudentDB.id == student_id).first()
        result = []
        for ticket in tickets:
            queue = self.db.query(QueueDB).filter(QueueDB.id == ticket.queue_id).first()
            result.append(self._to_ticket(ticket, student, queue))
        return result

    def get_queue_display(self, queue_id: int) -> List[TicketPublic]:
        """Get tickets for public display (limited info)"""
        tickets = self.db.query(TicketDB).filter(
            TicketDB.queue_id == queue_id,
            TicketDB.status.in_([TicketDBStatus.WAITING, TicketDBStatus.SERVING])
        ).order_by(TicketDB.position).all()

        queue = self.db.query(QueueDB).filter(QueueDB.id == queue_id).first()

        result = []
        for ticket in tickets:
            # For display, show only ticket number, not student info
            result.append(TicketPublic(
                ticket_number=ticket.ticket_number,
                queue_name=queue.name if queue else "Unknown",
                position=ticket.position,
                status=TicketStatus(ticket.status.value),
                estimated_wait_time_minutes=ticket.estimated_wait_time_minutes,
                created_at=ticket.created_at,
            ))
        return result

    def _to_ticket(self, db_ticket: TicketDB, student: StudentDB = None, queue: QueueDB = None) -> Ticket:
        """Convert DB model to Pydantic model"""
        return Ticket(
            id=db_ticket.id,
            ticket_number=db_ticket.ticket_number,
            student_id=db_ticket.student_id,
            queue_id=db_ticket.queue_id,
            priority=PydanticPriorityLevel(db_ticket.priority.value),
            purpose=db_ticket.purpose,
            status=TicketStatus(db_ticket.status.value),
            position=db_ticket.position,
            estimated_wait_time_minutes=db_ticket.estimated_wait_time_minutes,
            served_at=db_ticket.served_at,
            completed_at=db_ticket.completed_at,
            created_at=db_ticket.created_at,
            updated_at=db_ticket.updated_at,
            queue_name=queue.name if queue else None,
        )