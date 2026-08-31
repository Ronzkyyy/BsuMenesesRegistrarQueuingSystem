"""
Ticket model for queue tickets
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
from enum import Enum


class TicketStatus(str, Enum):
    WAITING = "waiting"
    SERVING = "serving"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class PriorityLevel(str, Enum):
    NORMAL = "normal"
    PRIORITY = "priority"
    URGENT = "urgent"


class TicketBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    student_id: int = Field(..., gt=0)
    queue_id: int = Field(..., gt=0)
    priority: PriorityLevel = PriorityLevel.NORMAL
    purpose: Optional[str] = Field(default=None, max_length=500)


class TicketCreate(TicketBase):
    pass


class Ticket(TicketBase):
    id: int
    ticket_number: int
    ticket_code: Optional[str] = None
    status: TicketStatus = TicketStatus.WAITING
    position: int
    estimated_wait_time_minutes: Optional[int] = None
    served_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    called_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    queue_name: Optional[str] = None

    class Config:
        from_attributes = True


class TicketInDB(Ticket):
    id: int


class TicketPublic(BaseModel):
    """Ticket data safe to expose to students (hides sensitive info)"""
    ticket_number: int
    ticket_code: str
    queue_name: str
    position: int
    status: TicketStatus
    priority: PriorityLevel
    estimated_wait_time_minutes: Optional[int]
    called_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True