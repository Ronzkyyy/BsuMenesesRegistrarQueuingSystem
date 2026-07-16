"""
Queue model for registrar services
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from enum import Enum


class QueueStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    CLOSED = "closed"


class QueueType(str, Enum):
    ENROLLMENT = "enrollment"
    DOCUMENT_REQUEST = "document_request"
    CLEARANCE = "clearance"
    SCHOLARSHIP = "scholarship"
    OTHERS = "others"


class QueueBase(BaseModel):
    name: str
    queue_type: QueueType
    description: Optional[str] = None
    allow_priority: bool = True
    max_capacity: int = Field(default=50, ge=1, le=200)
    slot_duration_minutes: int = Field(default=30, ge=5, le=120)


class QueueCreate(QueueBase):
    pass


class Queue(QueueBase):
    id: int
    status: QueueStatus = QueueStatus.ACTIVE
    current_ticket_number: int = 0
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class QueueInDB(Queue):
    id: int