"""Response schemas for the admin reporting module (read-only)."""
from datetime import date, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel


class ReportKind(str, Enum):
    TICKET = "ticket"
    APPOINTMENT = "appointment"


class ReportStatus(str, Enum):
    WAITING = "waiting"
    SERVING = "serving"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"
    BOOKED = "booked"
    CHECKED_IN = "checked_in"
    EXPIRED = "expired"


class ReportPriority(str, Enum):
    NORMAL = "normal"
    PRIORITY = "priority"
    URGENT = "urgent"


class TransactionRow(BaseModel):
    kind: str
    id: int
    reference: str
    student_number: str
    student_name: str
    service: str
    queue_name: str
    status: str
    priority: Optional[str] = None
    created_at: datetime
    occurred_at: Optional[datetime] = None
    appointment_date: Optional[date] = None


class TransactionHistoryPage(BaseModel):
    items: list[TransactionRow]
    total: int
    skip: int
    limit: int


class CalendarDay(BaseModel):
    date: date
    total: int
    tickets: int
    appointments: int
    by_status: dict[str, int]


class CalendarSummary(BaseModel):
    year: int
    month: int
    month_total: int
    peak_day: Optional[date] = None
    peak_count: int
    busiest_hours: list[int]
    days: list[CalendarDay]
