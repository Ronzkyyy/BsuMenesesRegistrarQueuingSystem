"""
Queue model for registrar services
"""
import string
from datetime import datetime, time
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator
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
    ADDING_DROPPING = "adding_dropping"
    PETITION_CLASS = "petition_class"
    OTHER_CONCERNS = "other_concerns"


class QueueBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(..., min_length=1, max_length=100)
    queue_type: QueueType
    ticket_letter: str = Field(min_length=1, max_length=1)
    description: Optional[str] = Field(default=None, max_length=1000)
    allow_priority: bool = True
    max_capacity: int = Field(default=50, ge=1, le=200)
    slot_duration_minutes: int = Field(default=30, ge=5, le=120)
    booking_enabled: bool = False
    operating_start_time: time = time(8, 0)
    operating_end_time: time = time(17, 0)
    slot_capacity: int = Field(default=3, ge=1, le=50)
    booking_window_days: int = Field(default=14, ge=1, le=90)

    @field_validator('ticket_letter')
    @classmethod
    def validate_ticket_letter(cls, v: str) -> str:
        v = v.upper()
        if v not in string.ascii_uppercase:
            raise ValueError('Ticket letter must be a single letter A-Z')
        return v


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


class QueueBookingSettings(BaseModel):
    booking_enabled: bool
    operating_start_time: time
    operating_end_time: time
    slot_capacity: int = Field(ge=1, le=50)
    booking_window_days: int = Field(ge=1, le=90)


class QueueSettingsUpdate(BaseModel):
    max_capacity: int = Field(ge=1, le=200)
    slot_duration_minutes: int = Field(ge=5, le=120)