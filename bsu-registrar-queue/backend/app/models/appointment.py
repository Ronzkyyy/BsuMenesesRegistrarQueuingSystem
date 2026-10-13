"""
Appointment model for QR-based queue booking
"""
from datetime import date, datetime, time
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator
from enum import Enum

from decimal import Decimal

from .document import RequestedDocument


class AppointmentStatus(str, Enum):
    BOOKED = "booked"
    CHECKED_IN = "checked_in"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class AppointmentCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    student_id: int = Field(..., gt=0)
    queue_id: int = Field(..., gt=0)
    appointment_date: date
    slot_start_time: time
    document_ids: List[int] = Field(default_factory=list, max_length=50)

    @field_validator("document_ids")
    @classmethod
    def positive_ids(cls, v):
        if any(i <= 0 for i in v):
            raise ValueError("Document ids must be positive")
        return v


class Appointment(BaseModel):
    id: int
    reference_code: str
    student_id: int
    queue_id: int
    appointment_date: date
    slot_start_time: time
    slot_end_time: time
    documents: List[RequestedDocument] = []
    documents_fee_total: Optional[Decimal] = None
    # Morning reminder email: sent | failed | pending | not_applicable.
    reminder_status: Optional[str] = None
    status: AppointmentStatus
    checked_in_at: Optional[datetime] = None
    ticket_id: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    queue_name: Optional[str] = None
    student_number: Optional[str] = None
    student_name: Optional[str] = None

    class Config:
        from_attributes = True


class AppointmentBooked(Appointment):
    """Returned only from the booking endpoint - the one time qr_token is exposed."""
    qr_token: str


class SlotAvailability(BaseModel):
    slot_start_time: time
    slot_end_time: time
    booked: int
    capacity: int
    is_full: bool


class AppointmentCheckInRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    token: Optional[str] = Field(default=None, max_length=64)
    reference_code: Optional[str] = Field(default=None, max_length=20)
    force: bool = False


class AppointmentListResponse(BaseModel):
    items: List[Appointment]
    total: int
    skip: int
    limit: int
