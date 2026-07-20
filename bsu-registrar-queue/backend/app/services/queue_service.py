"""
Queue service - business logic for queue management
"""
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timezone

from ..db_models import QueueDB, QueueDBStatus, QueueDBType
from ..models.queue import Queue, QueueCreate, QueueStatus


class QueueService:
    def __init__(self, db: Session):
        self.db = db

    def create_queue(self, queue_data: QueueCreate) -> Queue:
        """Create a new service queue"""
        # ticket_letter is already uppercased by QueueBase's validator, and
        # every existing row's letter is uppercase too (backfilled or
        # created through this same validated path) - a plain equality
        # check is enough, no case-folding needed here.
        existing = self.db.query(QueueDB).filter(
            QueueDB.ticket_letter == queue_data.ticket_letter
        ).first()
        if existing:
            raise ValueError(f"Ticket letter '{queue_data.ticket_letter}' is already used by another queue")

        db_queue = QueueDB(
            name=queue_data.name,
            queue_type=QueueDBType(queue_data.queue_type.value),
            ticket_letter=queue_data.ticket_letter,
            description=queue_data.description,
            allow_priority=queue_data.allow_priority,
            max_capacity=queue_data.max_capacity,
            slot_duration_minutes=queue_data.slot_duration_minutes,
            status=QueueDBStatus.ACTIVE,
            current_ticket_number=0,
        )
        self.db.add(db_queue)
        self.db.commit()
        self.db.refresh(db_queue)
        return self._to_queue(db_queue)

    def get_active_queues(self) -> List[Queue]:
        """Get all active queues"""
        queues = self.db.query(QueueDB).filter(
            QueueDB.status == QueueDBStatus.ACTIVE
        ).all()
        return [self._to_queue(q) for q in queues]

    def get_all_queues(self, skip: int = 0, limit: int = 100) -> List[Queue]:
        """Get all queues with pagination"""
        queues = self.db.query(QueueDB).offset(skip).limit(limit).all()
        return [self._to_queue(q) for q in queues]

    def get_queue_by_id(self, queue_id: int) -> Optional[Queue]:
        """Get specific queue by ID"""
        queue = self.db.query(QueueDB).filter(QueueDB.id == queue_id).first()
        return self._to_queue(queue) if queue else None

    def update_queue_status(self, queue_id: int, status: QueueStatus) -> Optional[Queue]:
        """Update queue status (active, paused, closed)"""
        queue = self.db.query(QueueDB).filter(QueueDB.id == queue_id).first()
        if not queue:
            return None

        queue.status = QueueDBStatus(status.value)
        queue.updated_at = datetime.now()
        self.db.commit()
        self.db.refresh(queue)
        return self._to_queue(queue)

    def pause_queue(self, queue_id: int) -> Optional[Queue]:
        """Pause a queue - no new tickets allowed"""
        return self.update_queue_status(queue_id, QueueStatus.PAUSED)

    def resume_queue(self, queue_id: int) -> Optional[Queue]:
        """Resume a paused queue"""
        return self.update_queue_status(queue_id, QueueStatus.ACTIVE)

    def close_queue(self, queue_id: int) -> Optional[Queue]:
        """Close queue for the day"""
        return self.update_queue_status(queue_id, QueueStatus.CLOSED)

    def delete_queue(self, queue_id: int) -> bool:
        """Delete a queue. Returns False if the queue doesn't exist.

        Raises ValueError if the queue has any tickets (even completed/old
        ones) - deleting it would violate the tickets.queue_id foreign key
        and silently destroy historical ticket records, so we block it with
        a clear message instead of letting the database raise a raw 500.
        """
        from ..db_models import TicketDB
        from sqlalchemy import func

        queue = self.db.query(QueueDB).filter(QueueDB.id == queue_id).first()
        if not queue:
            return False

        ticket_count = self.db.query(func.count(TicketDB.id)).filter(
            TicketDB.queue_id == queue_id
        ).scalar()
        if ticket_count:
            raise ValueError(
                f"Cannot delete queue '{queue.name}': it has {ticket_count} ticket(s). "
                f"Close the queue instead to stop new tickets."
            )

        self.db.delete(queue)
        self.db.commit()
        return True

    def increment_ticket_number(self, queue_id: int) -> int:
        """Increment and return the next ticket number for a queue"""
        queue = self.db.query(QueueDB).filter(QueueDB.id == queue_id).first()
        if not queue:
            return 0
        queue.current_ticket_number += 1
        queue.updated_at = datetime.now()
        self.db.commit()
        return queue.current_ticket_number

    def get_queue_stats(self, queue_id: int) -> dict:
        """Get statistics for a queue"""
        from ..db_models import TicketDB, TicketDBStatus
        from sqlalchemy import func

        queue = self.db.query(QueueDB).filter(QueueDB.id == queue_id).first()
        if not queue:
            return {}

        total_tickets = self.db.query(func.count(TicketDB.id)).filter(
            TicketDB.queue_id == queue_id
        ).scalar()

        waiting = self.db.query(func.count(TicketDB.id)).filter(
            TicketDB.queue_id == queue_id,
            TicketDB.status == TicketDBStatus.WAITING
        ).scalar()

        serving = self.db.query(func.count(TicketDB.id)).filter(
            TicketDB.queue_id == queue_id,
            TicketDB.status == TicketDBStatus.SERVING
        ).scalar()

        completed = self.db.query(func.count(TicketDB.id)).filter(
            TicketDB.queue_id == queue_id,
            TicketDB.status == TicketDBStatus.COMPLETED
        ).scalar()

        cancelled = self.db.query(func.count(TicketDB.id)).filter(
            TicketDB.queue_id == queue_id,
            TicketDB.status == TicketDBStatus.CANCELLED
        ).scalar()

        no_show = self.db.query(func.count(TicketDB.id)).filter(
            TicketDB.queue_id == queue_id,
            TicketDB.status == TicketDBStatus.NO_SHOW
        ).scalar()

        return {
            "queue_id": queue_id,
            "queue_name": queue.name,
            "status": queue.status.value,
            "total_tickets": total_tickets,
            "waiting": waiting,
            "serving": serving,
            "completed": completed,
            "cancelled": cancelled,
            "no_show": no_show,
            "current_ticket_number": queue.current_ticket_number,
        }

    def get_dashboard_summary(self) -> dict:
        """Aggregate stats for the admin dashboard overview"""
        from ..db_models import TicketDB, TicketDBStatus, UserDB
        from sqlalchemy import func

        users_count = self.db.query(func.count(UserDB.id)).scalar()
        queues_count = self.db.query(func.count(QueueDB.id)).scalar()
        active_queues_count = self.db.query(func.count(QueueDB.id)).filter(
            QueueDB.status == QueueDBStatus.ACTIVE
        ).scalar()

        waiting_count = self.db.query(func.count(TicketDB.id)).filter(
            TicketDB.status == TicketDBStatus.WAITING
        ).scalar()
        serving_count = self.db.query(func.count(TicketDB.id)).filter(
            TicketDB.status == TicketDBStatus.SERVING
        ).scalar()

        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

        status_rows = self.db.query(
            TicketDB.status, func.count(TicketDB.id)
        ).filter(
            TicketDB.created_at >= today_start
        ).group_by(TicketDB.status).all()
        tickets_today_by_status = {status.value: 0 for status in TicketDBStatus}
        for status, count in status_rows:
            tickets_today_by_status[status.value] = count

        queue_rows = self.db.query(
            TicketDB.queue_id, QueueDB.name, func.count(TicketDB.id)
        ).join(QueueDB, TicketDB.queue_id == QueueDB.id).filter(
            TicketDB.created_at >= today_start
        ).group_by(TicketDB.queue_id, QueueDB.name).all()
        tickets_today_by_queue = [
            {"queue_id": queue_id, "queue_name": queue_name, "count": count}
            for queue_id, queue_name, count in queue_rows
        ]

        return {
            "users_count": users_count,
            "queues_count": queues_count,
            "active_queues_count": active_queues_count,
            "waiting_count": waiting_count,
            "serving_count": serving_count,
            "completed_today_count": tickets_today_by_status["completed"],
            "no_shows_today_count": tickets_today_by_status["no_show"],
            "tickets_today_by_queue": tickets_today_by_queue,
            "tickets_today_by_status": tickets_today_by_status,
        }

    def _to_queue(self, db_queue: QueueDB) -> Queue:
        """Convert DB model to Pydantic model"""
        return Queue(
            id=db_queue.id,
            name=db_queue.name,
            queue_type=QueueDBType(db_queue.queue_type.value),
            ticket_letter=db_queue.ticket_letter,
            description=db_queue.description,
            status=QueueDBStatus(db_queue.status.value),
            allow_priority=db_queue.allow_priority,
            max_capacity=db_queue.max_capacity,
            slot_duration_minutes=db_queue.slot_duration_minutes,
            current_ticket_number=db_queue.current_ticket_number,
            created_at=db_queue.created_at,
            updated_at=db_queue.updated_at,
        )