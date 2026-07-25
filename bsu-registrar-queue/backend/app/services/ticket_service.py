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


def _format_ticket_code(letter: str, ticket_number: int) -> str:
    return f"{letter}-{ticket_number:03d}"


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

        # Check if student already has an active ticket in ANY queue - only
        # one transaction in flight per student is allowed, across all queues.
        existing = self.db.query(TicketDB).filter(
            TicketDB.student_id == ticket_data.student_id,
            TicketDB.status.in_([TicketDBStatus.WAITING, TicketDBStatus.SERVING])
        ).first()
        if existing:
            existing_queue = self.db.query(QueueDB).filter(QueueDB.id == existing.queue_id).first()
            queue_label = existing_queue.name if existing_queue else "another queue"
            ticket_code = (
                _format_ticket_code(existing_queue.ticket_letter, existing.ticket_number)
                if existing_queue else ""
            )
            raise ValueError(
                f"You already have an active ticket in {queue_label} ({ticket_code}). "
                f"Complete or cancel it before taking a new one."
            )

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

    def call_ticket(self, ticket_id: int) -> Optional[Ticket]:
        """Record that staff called this ticket again (does not change status)"""
        ticket = self.db.query(TicketDB).filter(TicketDB.id == ticket_id).first()
        if not ticket:
            return None

        ticket.called_at = datetime.now()
        ticket.updated_at = datetime.now()
        self.db.commit()
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

        A student can hold at most one active ticket at a time, across all
        queues (enforced in create_ticket), so an unscoped call is
        deterministic - callers may omit queue_id to check for any active
        ticket regardless of which queue it's in.
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
                ticket_code=_format_ticket_code(queue.ticket_letter if queue else "?", ticket.ticket_number),
                queue_name=queue.name if queue else "Unknown",
                position=ticket.position,
                status=TicketStatus(ticket.status.value),
                priority=PydanticPriorityLevel(ticket.priority.value),
                estimated_wait_time_minutes=ticket.estimated_wait_time_minutes,
                called_at=ticket.called_at,
                created_at=ticket.created_at,
            ))
        return result

    def get_now_serving_overview(self) -> List[dict]:
        """Aggregate now-serving/waiting summary for every active queue"""
        active_queues = self.db.query(QueueDB).filter(
            QueueDB.status == QueueDBStatus.ACTIVE
        ).all()

        result = []
        for queue in active_queues:
            serving_tickets = self.db.query(TicketDB).filter(
                TicketDB.queue_id == queue.id,
                TicketDB.status == TicketDBStatus.SERVING
            ).order_by(TicketDB.position).all()

            next_waiting = self.db.query(TicketDB).filter(
                TicketDB.queue_id == queue.id,
                TicketDB.status == TicketDBStatus.WAITING
            ).order_by(TicketDB.position).first()

            waiting_count = self.db.query(func.count(TicketDB.id)).filter(
                TicketDB.queue_id == queue.id,
                TicketDB.status == TicketDBStatus.WAITING
            ).scalar()

            result.append({
                "queue_id": queue.id,
                "queue_name": queue.name,
                "queue_type": queue.queue_type.value,
                "serving_ticket_codes": [
                    _format_ticket_code(queue.ticket_letter, t.ticket_number) for t in serving_tickets
                ],
                "next_ticket_code": (
                    _format_ticket_code(queue.ticket_letter, next_waiting.ticket_number) if next_waiting else None
                ),
                "waiting_count": waiting_count,
            })

        return result

    def _to_ticket(self, db_ticket: TicketDB, student: StudentDB = None, queue: QueueDB = None) -> Ticket:
        """Convert DB model to Pydantic model"""
        return Ticket(
            id=db_ticket.id,
            ticket_number=db_ticket.ticket_number,
            ticket_code=_format_ticket_code(queue.ticket_letter, db_ticket.ticket_number) if queue else None,
            student_id=db_ticket.student_id,
            queue_id=db_ticket.queue_id,
            priority=PydanticPriorityLevel(db_ticket.priority.value),
            purpose=db_ticket.purpose,
            status=TicketStatus(db_ticket.status.value),
            position=db_ticket.position,
            estimated_wait_time_minutes=db_ticket.estimated_wait_time_minutes,
            served_at=db_ticket.served_at,
            completed_at=db_ticket.completed_at,
            called_at=db_ticket.called_at,
            created_at=db_ticket.created_at,
            updated_at=db_ticket.updated_at,
            queue_name=queue.name if queue else None,
        )