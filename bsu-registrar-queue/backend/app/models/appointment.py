"""
Appointment model for QR-based queue booking
"""
from datetime import date, datetime, time
from typing import List, Optional
from pydantic import BaseModel, Field
from enum import Enum


class AppointmentStatus(str, Enum):
    BOOKED = "booked"
    CHECKED_IN = "checked_in"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class AppointmentCreate(BaseModel):
    student_id: int
    queue_id: int
    appointment_date: date
    slot_start_time: time
    purpose: Optional[str] = None


class Appointment(BaseModel):
    id: int
    reference_code: str
    student_id: int
    queue_id: int
    appointment_date: date
    slot_start_time: time
    slot_end_time: time
    purpose: Optional[str] = None
    status: AppointmentStatus
    checked_in_at: Optional[datetime] = None
    ticket_id: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    queue_name: Optional[str] = None

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
    token: Optional[str] = None
    reference_code: Optional[str] = None
    force: bool = False
