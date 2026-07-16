"""
Queue service - business logic for queue management
"""
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from ..db_models import QueueDB, QueueDBStatus, QueueDBType
from ..models.queue import Queue, QueueCreate, QueueStatus


class QueueService:
    def __init__(self, db: Session):
        self.db = db

    def create_queue(self, queue_data: QueueCreate) -> Queue:
        """Create a new service queue"""
        db_queue = QueueDB(
            name=queue_data.name,
            queue_type=QueueDBType(queue_data.queue_type.value),
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

    def _to_queue(self, db_queue: QueueDB) -> Queue:
        """Convert DB model to Pydantic model"""
        return Queue(
            id=db_queue.id,
            name=db_queue.name,
            queue_type=QueueDBType(db_queue.queue_type.value),
            description=db_queue.description,
            status=QueueDBStatus(db_queue.status.value),
            allow_priority=db_queue.allow_priority,
            max_capacity=db_queue.max_capacity,
            slot_duration_minutes=db_queue.slot_duration_minutes,
            current_ticket_number=db_queue.current_ticket_number,
            created_at=db_queue.created_at,
            updated_at=db_queue.updated_at,
        )