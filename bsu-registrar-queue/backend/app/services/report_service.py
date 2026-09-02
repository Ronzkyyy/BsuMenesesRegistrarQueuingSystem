"""ReportService - read-only history & peak-volume aggregation for admins.

Every query uses the SQLAlchemy ORM query builder (bound parameters by
construction). Day/hour bucketing is done in campus-local time
(settings.CAMPUS_TIMEZONE), never naive UTC.
"""
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from ..core.config import settings
from ..db_models import (
    AppointmentDB, AppointmentDBStatus, PriorityLevel, QueueDB, StudentDB,
    TicketDB, TicketDBStatus,
)
from ..models.report import (
    CalendarDay, CalendarSummary, TransactionHistoryPage, TransactionRow,
)

_TICKET_STATUS_VALUES = {s.value for s in TicketDBStatus}
_APPOINTMENT_STATUS_VALUES = {s.value for s in AppointmentDBStatus}
_ATTENDED_TICKET_STATUSES = (TicketDBStatus.COMPLETED, TicketDBStatus.SERVING)
_ATTENDED_APPOINTMENT_STATUSES = (AppointmentDBStatus.CHECKED_IN,)

MAX_EXPORT_ROWS = 10_000


class ReportService:
    def __init__(self, db: Session):
        self.db = db
        self.tz = ZoneInfo(settings.CAMPUS_TIMEZONE)

    # ---- window helpers ---------------------------------------------------

    def _utc_window(self, date_from: date, date_to: date) -> tuple[datetime, datetime]:
        """[date_from 00:00, date_to+1day 00:00) in campus tz, as UTC instants."""
        start = datetime.combine(date_from, time.min, tzinfo=self.tz)
        end = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=self.tz)
        return start.astimezone(timezone.utc), end.astimezone(timezone.utc)

    # ---- per-source queries --------------------------------------------

    def _query_tickets(self, start_utc, end_utc, statuses, queue_id,
                       student_number, priority, cap):
        q = (
            self.db.query(TicketDB, StudentDB, QueueDB)
            .join(StudentDB, TicketDB.student_id == StudentDB.id)
            .join(QueueDB, TicketDB.queue_id == QueueDB.id)
            .filter(TicketDB.created_at >= start_utc, TicketDB.created_at < end_utc)
        )
        if statuses:
            wanted = [TicketDBStatus(s) for s in statuses if s in _TICKET_STATUS_VALUES]
            if not wanted:
                return [], 0
            q = q.filter(TicketDB.status.in_(wanted))
        else:
            q = q.filter(TicketDB.status.in_(_ATTENDED_TICKET_STATUSES))
        if queue_id is not None:
            q = q.filter(TicketDB.queue_id == queue_id)
        if student_number is not None:
            q = q.filter(StudentDB.student_id == student_number)
        if priority is not None:
            q = q.filter(TicketDB.priority == PriorityLevel(priority))
        total = q.count()
        q = q.order_by(TicketDB.created_at.desc(), TicketDB.id.desc()).limit(cap)
        rows = [
            TransactionRow(
                kind="ticket",
                id=t.id,
                reference=f"{queue.ticket_letter}-{t.ticket_number:03d}",
                student_number=student.student_id,
                student_name=f"{student.first_name} {student.last_name}",
                service=(t.purpose or queue.name),
                queue_name=queue.name,
                status=t.status.value,
                priority=t.priority.value if t.priority else None,
                created_at=t.created_at,
                occurred_at=(t.completed_at or t.served_at),
                appointment_date=None,
            )
            for t, student, queue in q.all()
        ]
        return rows, total

    def _query_appointments(self, start_utc, end_utc, statuses, queue_id,
                            student_number, cap):
        q = (
            self.db.query(AppointmentDB, StudentDB, QueueDB)
            .join(StudentDB, AppointmentDB.student_id == StudentDB.id)
            .join(QueueDB, AppointmentDB.queue_id == QueueDB.id)
            .filter(AppointmentDB.created_at >= start_utc,
                    AppointmentDB.created_at < end_utc)
        )
        if statuses:
            wanted = [AppointmentDBStatus(s) for s in statuses
                      if s in _APPOINTMENT_STATUS_VALUES]
            if not wanted:
                return [], 0
            q = q.filter(AppointmentDB.status.in_(wanted))
        else:
            q = q.filter(AppointmentDB.status.in_(_ATTENDED_APPOINTMENT_STATUSES))
        if queue_id is not None:
            q = q.filter(AppointmentDB.queue_id == queue_id)
        if student_number is not None:
            q = q.filter(StudentDB.student_id == student_number)
        total = q.count()
        q = q.order_by(AppointmentDB.created_at.desc(),
                       AppointmentDB.id.desc()).limit(cap)
        rows = [
            TransactionRow(
                kind="appointment",
                id=a.id,
                reference=a.reference_code,
                student_number=student.student_id,
                student_name=f"{student.first_name} {student.last_name}",
                service=(a.purpose or queue.name),
                queue_name=queue.name,
                status=a.status.value,
                priority=None,
                created_at=a.created_at,
                occurred_at=a.checked_in_at,
                appointment_date=a.appointment_date,
            )
            for a, student, queue in q.all()
        ]
        return rows, total

    def _collect_rows(self, start_utc, end_utc, kinds, statuses, queue_id,
                      student_number, priority, cap):
        """Fetch up to `cap` newest rows from each requested source and their
        true totals. Merging the top-`cap` of each source is enough to slice
        any page whose (skip + limit) <= cap."""
        rows: list[TransactionRow] = []
        total = 0
        if "ticket" in kinds:
            t_rows, t_total = self._query_tickets(
                start_utc, end_utc, statuses, queue_id, student_number,
                priority, cap)
            rows += t_rows
            total += t_total
        # Appointments have no priority - a priority filter excludes them.
        if "appointment" in kinds and priority is None:
            a_rows, a_total = self._query_appointments(
                start_utc, end_utc, statuses, queue_id, student_number, cap)
            rows += a_rows
            total += a_total
        rows.sort(key=lambda r: (r.created_at, r.id), reverse=True)
        return rows, total

    # ---- public API ----------------------------------------------------

    def get_transactions(self, *, date_from: date, date_to: date,
                         kinds: list[str], statuses: Optional[list[str]],
                         queue_id: Optional[int], student_number: Optional[str],
                         priority: Optional[str], skip: int,
                         limit: int) -> TransactionHistoryPage:
        if date_from > date_to:
            raise ValueError("date_from must not be after date_to")
        start_utc, end_utc = self._utc_window(date_from, date_to)
        rows, total = self._collect_rows(
            start_utc, end_utc, kinds, statuses, queue_id, student_number,
            priority, cap=skip + limit)
        return TransactionHistoryPage(
            items=rows[skip:skip + limit], total=total, skip=skip, limit=limit)
