"""
Appointment service - QR-based booking that checks in to create a queue ticket
"""
import secrets
from datetime import date, datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from typing import List, Optional, Tuple

from ..db_models import AppointmentDB, AppointmentDBStatus, PriorityLevel, QueueDB, StudentDB
from ..models.appointment import (
    Appointment, AppointmentBooked, AppointmentCreate, AppointmentStatus, SlotAvailability
)
from ..models.ticket import DocumentType, Ticket, TicketCreate
from .search_utils import LIKE_ESCAPE, escape_like
from .ticket_service import TicketService, validate_document_type


class AppointmentWindowError(Exception):
    """Raised when a check-in is attempted outside the appointment's window and not forced."""
    pass


class AppointmentExpiredError(ValueError):
    """Raised when checking in an appointment that has already been marked EXPIRED.

    Subclasses ValueError so existing `except ValueError` handlers still treat it
    as a client error; the API catches it first to answer 410 with the booking's
    own details, so the UI can render an "expired" state instead of a raw error.
    """

    def __init__(self, appointment: "AppointmentDB"):
        self.appointment = appointment
        super().__init__(
            "This appointment has expired. Use manual lookup or take a walk-in ticket."
        )


def earliest_bookable_date() -> date:
    """The first date a student may book: tomorrow.

    Same-day appointments are not offered, so the registrar has the day's
    bookings settled before it opens. Availability and creation both read the
    rule from here rather than each re-deriving it from date.today().
    """
    return date.today() + timedelta(days=1)


# How far before/after a slot's start/end time a check-in is accepted without
# staff explicitly overriding via force=True.
GRACE_MINUTES_BEFORE = 30
GRACE_MINUTES_AFTER = 30

# How long past a slot's end time a still-BOOKED appointment is left alone
# before expire_stale_appointments marks it EXPIRED - gives a late walk-in a
# buffer beyond the check-in grace window before losing the slot for good.
EXPIRE_BUFFER_MINUTES = 60


class AppointmentService:
    def __init__(self, db: Session):
        self.db = db

    def get_availability(self, queue_id: int, target_date: date) -> List[SlotAvailability]:
        """Compute bookable slots for a queue/date from the queue's own settings"""
        queue = self.db.query(QueueDB).filter(QueueDB.id == queue_id).first()
        if not queue or not queue.booking_enabled:
            return []

        # Same-day booking is not offered - the earliest bookable date is
        # tomorrow, so today and anything before it has no slots at all.
        if target_date < earliest_bookable_date():
            return []

        slots: List[SlotAvailability] = []
        delta = timedelta(minutes=queue.slot_duration_minutes)
        current = datetime.combine(target_date, queue.operating_start_time)
        day_end = datetime.combine(target_date, queue.operating_end_time)

        while current + delta <= day_end:
            slot_start = current.time()
            slot_end = (current + delta).time()
            booked = self.db.query(func.count(AppointmentDB.id)).filter(
                AppointmentDB.queue_id == queue_id,
                AppointmentDB.appointment_date == target_date,
                AppointmentDB.slot_start_time == slot_start,
                AppointmentDB.status == AppointmentDBStatus.BOOKED,
            ).scalar() or 0
            slots.append(SlotAvailability(
                slot_start_time=slot_start,
                slot_end_time=slot_end,
                booked=booked,
                capacity=queue.slot_capacity,
                is_full=booked >= queue.slot_capacity,
            ))
            current += delta

        return slots

    def create_appointment(self, data: AppointmentCreate) -> AppointmentBooked:
        """Book an appointment for a student in a computed slot"""
        student = self.db.query(StudentDB).filter(StudentDB.id == data.student_id).first()
        if not student:
            raise ValueError("Student not found")

        queue = self.db.query(QueueDB).filter(QueueDB.id == data.queue_id).first()
        if not queue or not queue.booking_enabled:
            raise ValueError("This service is not open for appointment booking")

        validate_document_type(queue, data.document_type)

        today = date.today()
        earliest = earliest_bookable_date()
        if data.appointment_date < earliest:
            raise ValueError(
                "Appointments must be booked at least one day ahead - the earliest "
                f"available date is {earliest.isoformat()}."
            )
        if data.appointment_date > today + timedelta(days=queue.booking_window_days):
            raise ValueError(f"Appointments can only be booked up to {queue.booking_window_days} days in advance")

        existing = self.db.query(AppointmentDB).filter(
            AppointmentDB.student_id == data.student_id,
            AppointmentDB.status == AppointmentDBStatus.BOOKED,
            AppointmentDB.appointment_date >= today,
        ).first()
        if existing:
            raise ValueError(
                f"You already have an active appointment ({existing.reference_code}) on "
                f"{existing.appointment_date.isoformat()}. Cancel it before booking another."
            )

        slot_delta = timedelta(minutes=queue.slot_duration_minutes)
        slot_start_dt = datetime.combine(data.appointment_date, data.slot_start_time)
        day_start = datetime.combine(data.appointment_date, queue.operating_start_time)
        day_end = datetime.combine(data.appointment_date, queue.operating_end_time)
        is_valid_slot = (
            slot_start_dt >= day_start
            and slot_start_dt + slot_delta <= day_end
            and (slot_start_dt - day_start) % slot_delta == timedelta(0)
        )
        if not is_valid_slot:
            raise ValueError("That time is not a valid slot for this service")

        booked_count = self.db.query(func.count(AppointmentDB.id)).filter(
            AppointmentDB.queue_id == data.queue_id,
            AppointmentDB.appointment_date == data.appointment_date,
            AppointmentDB.slot_start_time == data.slot_start_time,
            AppointmentDB.status == AppointmentDBStatus.BOOKED,
        ).scalar() or 0
        if booked_count >= queue.slot_capacity:
            raise ValueError("That time slot is fully booked. Please choose another.")

        appointment = AppointmentDB(
            reference_code=self._generate_reference_code(),
            student_id=data.student_id,
            queue_id=data.queue_id,
            appointment_date=data.appointment_date,
            slot_start_time=data.slot_start_time,
            slot_end_time=(slot_start_dt + slot_delta).time(),
            document_type=data.document_type.value if data.document_type else None,
            qr_token=secrets.token_urlsafe(32),
            status=AppointmentDBStatus.BOOKED,
        )
        self.db.add(appointment)
        self.db.commit()
        self.db.refresh(appointment)
        return self._to_appointment(appointment, queue, student, include_token=True)

    def lookup(self, student_id_str: str, reference_code: str) -> Optional[Appointment]:
        """Student re-views a booking by student ID + reference code"""
        student = self.db.query(StudentDB).filter(StudentDB.student_id == student_id_str).first()
        if not student:
            return None
        appointment = self.db.query(AppointmentDB).filter(
            AppointmentDB.student_id == student.id,
            AppointmentDB.reference_code == reference_code.strip().upper(),
        ).first()
        if not appointment:
            return None
        queue = self.db.query(QueueDB).filter(QueueDB.id == appointment.queue_id).first()
        return self._to_appointment(appointment, queue, student)

    def cancel(self, appointment_id: int, student_id_str: str) -> Optional[Appointment]:
        """Student cancels their own still-booked appointment"""
        student = self.db.query(StudentDB).filter(StudentDB.student_id == student_id_str).first()
        if not student:
            return None
        appointment = self.db.query(AppointmentDB).filter(
            AppointmentDB.id == appointment_id,
            AppointmentDB.student_id == student.id,
        ).first()
        if not appointment:
            return None
        if appointment.status != AppointmentDBStatus.BOOKED:
            raise ValueError(f"This appointment cannot be cancelled (status: {appointment.status.value}).")

        appointment.status = AppointmentDBStatus.CANCELLED
        appointment.updated_at = datetime.now()
        self.db.commit()
        self.db.refresh(appointment)
        queue = self.db.query(QueueDB).filter(QueueDB.id == appointment.queue_id).first()
        return self._to_appointment(appointment, queue, student)

    def search(self, query: str) -> List[Appointment]:
        """Staff manual lookup fallback - matches student ID or reference code.

        Includes EXPIRED alongside BOOKED (not CANCELLED/CHECKED_IN, which are
        already resolved) so a stale appointment stays findable - and
        removable via staff_cancel_expired - after expire_stale_appointments
        flips it, instead of silently vanishing from search."""
        pattern = f"%{escape_like(query)}%"
        rows = self.db.query(AppointmentDB, StudentDB).join(
            StudentDB, AppointmentDB.student_id == StudentDB.id
        ).filter(
            AppointmentDB.status.in_([AppointmentDBStatus.BOOKED, AppointmentDBStatus.EXPIRED]),
            or_(
                StudentDB.student_id.ilike(pattern, escape=LIKE_ESCAPE),
                AppointmentDB.reference_code.ilike(pattern, escape=LIKE_ESCAPE),
            )
        ).order_by(AppointmentDB.appointment_date, AppointmentDB.slot_start_time).limit(20).all()

        result = []
        for appt, student in rows:
            queue = self.db.query(QueueDB).filter(QueueDB.id == appt.queue_id).first()
            result.append(self._to_appointment(appt, queue, student))
        return result

    def list_appointments(
        self,
        upcoming: bool = True,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[Appointment], int]:
        """Browse appointments for staff (Admin/Registrar/Staff) - "who's booked in".

        upcoming=True (default): still-BOOKED appointments dated today or
        later, soonest first - what's coming up.
        upcoming=False: everything else (checked-in, cancelled, expired, or
        just past-dated), most recent first - the history view.
        date_from/date_to further narrow either view to a specific day or
        range, applied on top of the upcoming/past split.
        """
        today = date.today()
        query = self.db.query(AppointmentDB, StudentDB, QueueDB).join(
            StudentDB, AppointmentDB.student_id == StudentDB.id
        ).join(
            QueueDB, AppointmentDB.queue_id == QueueDB.id
        )

        if upcoming:
            query = query.filter(
                AppointmentDB.appointment_date >= today,
                AppointmentDB.status == AppointmentDBStatus.BOOKED,
            )
        else:
            query = query.filter(
                or_(
                    AppointmentDB.appointment_date < today,
                    AppointmentDB.status != AppointmentDBStatus.BOOKED,
                )
            )

        if date_from:
            query = query.filter(AppointmentDB.appointment_date >= date_from)
        if date_to:
            query = query.filter(AppointmentDB.appointment_date <= date_to)

        total = query.count()

        if upcoming:
            query = query.order_by(AppointmentDB.appointment_date.asc(), AppointmentDB.slot_start_time.asc())
        else:
            query = query.order_by(AppointmentDB.appointment_date.desc(), AppointmentDB.slot_start_time.desc())

        rows = query.offset(skip).limit(limit).all()
        items = [self._to_appointment(appt, queue, student) for appt, student, queue in rows]
        return items, total

    def check_in(
        self,
        token: Optional[str] = None,
        reference_code: Optional[str] = None,
        staff_user_id: Optional[int] = None,
        force: bool = False,
    ) -> Ticket:
        """Scan or manually check in an appointment, creating a normal queue ticket"""
        if not token and not reference_code:
            raise ValueError("Provide a QR token or reference code")

        query = self.db.query(AppointmentDB)
        appointment = (
            query.filter(AppointmentDB.qr_token == token).first() if token
            else query.filter(AppointmentDB.reference_code == reference_code.strip().upper()).first()
        )
        if not appointment:
            raise ValueError("Appointment not found - invalid code")

        if appointment.status == AppointmentDBStatus.CHECKED_IN:
            when = appointment.checked_in_at.strftime('%I:%M %p') if appointment.checked_in_at else "an earlier time"
            raise ValueError(f"This appointment was already checked in at {when}.")
        if appointment.status == AppointmentDBStatus.CANCELLED:
            raise ValueError("This appointment was cancelled.")
        if appointment.status == AppointmentDBStatus.EXPIRED:
            raise AppointmentExpiredError(appointment)

        now = datetime.now()
        slot_start = datetime.combine(appointment.appointment_date, appointment.slot_start_time)
        slot_end = datetime.combine(appointment.appointment_date, appointment.slot_end_time)
        window_start = slot_start - timedelta(minutes=GRACE_MINUTES_BEFORE)
        window_end = slot_end + timedelta(minutes=GRACE_MINUTES_AFTER)
        if not force and not (window_start <= now <= window_end):
            raise AppointmentWindowError(
                f"This appointment is scheduled for {appointment.slot_start_time.strftime('%I:%M %p')} "
                f"on {appointment.appointment_date.isoformat()}, outside the normal check-in window."
            )

        # Atomic status flip: guards against two counters checking in the same
        # appointment at once. Only the request that actually flips BOOKED ->
        # CHECKED_IN proceeds to create a ticket.
        rows_updated = self.db.query(AppointmentDB).filter(
            AppointmentDB.id == appointment.id,
            AppointmentDB.status == AppointmentDBStatus.BOOKED,
        ).update({
            "status": AppointmentDBStatus.CHECKED_IN,
            "checked_in_at": now,
            "checked_in_by": staff_user_id,
        })
        self.db.commit()
        if not rows_updated:
            raise ValueError("This appointment was already checked in by another counter.")

        ticket_service = TicketService(self.db)
        ticket_data = TicketCreate(
            student_id=appointment.student_id,
            queue_id=appointment.queue_id,
            document_type=DocumentType(appointment.document_type) if appointment.document_type else None,
        )
        try:
            ticket = ticket_service.create_ticket(ticket_data, minimum_priority=PriorityLevel.PRIORITY)
        except Exception:
            self._revert_check_in(appointment.id)
            raise

        if not ticket:
            self._revert_check_in(appointment.id)
            raise ValueError(
                "Could not create a ticket for this appointment. The queue may be full or inactive."
            )

        self.db.query(AppointmentDB).filter(AppointmentDB.id == appointment.id).update({"ticket_id": ticket.id})
        self.db.commit()
        return ticket

    def _revert_check_in(self, appointment_id: int) -> None:
        """Roll a check-in back to BOOKED so the appointment can be retried, e.g. when
        ticket creation fails after the status flip already succeeded."""
        self.db.query(AppointmentDB).filter(AppointmentDB.id == appointment_id).update({
            "status": AppointmentDBStatus.BOOKED,
            "checked_in_at": None,
            "checked_in_by": None,
        })
        self.db.commit()

    def expire_stale_appointments(self, buffer_minutes: int = EXPIRE_BUFFER_MINUTES) -> int:
        """Mark BOOKED appointments whose window has fully passed as EXPIRED. Returns count expired."""
        cutoff = datetime.now() - timedelta(minutes=buffer_minutes)
        stale = self.db.query(AppointmentDB).filter(AppointmentDB.status == AppointmentDBStatus.BOOKED).all()
        count = 0
        for appt in stale:
            slot_end = datetime.combine(appt.appointment_date, appt.slot_end_time)
            if slot_end < cutoff:
                appt.status = AppointmentDBStatus.EXPIRED
                appt.updated_at = datetime.now()
                count += 1
        if count:
            self.db.commit()
        return count

    @staticmethod
    def _is_overdue(appt: AppointmentDB) -> bool:
        """True once an appointment is past saving - either already flipped to
        EXPIRED by expire_stale_appointments, or still BOOKED but past that
        same buffer_minutes cutoff (the periodic task runs every 5 minutes, so
        a BOOKED row can lag the cutoff briefly before it's caught)."""
        if appt.status == AppointmentDBStatus.EXPIRED:
            return True
        if appt.status != AppointmentDBStatus.BOOKED:
            return False
        slot_end = datetime.combine(appt.appointment_date, appt.slot_end_time)
        return slot_end < datetime.now() - timedelta(minutes=EXPIRE_BUFFER_MINUTES)

    def staff_cancel_expired(self, appointment_id: int) -> Optional[Appointment]:
        """Staff removes a specific overdue appointment from the check-in flow.

        A soft cancel (status -> CANCELLED), not a hard delete, so it still
        shows up in Transaction History for audit purposes. Restricted to
        appointments that are actually overdue - per **Authorize every
        sensitive action on the server** (CLAUDE.md), the UI only offers this
        button for expired rows, but the server re-checks _is_overdue itself
        rather than trusting the client not to call it on a valid upcoming
        booking."""
        appointment = self.db.query(AppointmentDB).filter(AppointmentDB.id == appointment_id).first()
        if not appointment:
            return None
        if not self._is_overdue(appointment):
            raise ValueError("Only expired or overdue appointments can be removed this way.")

        appointment.status = AppointmentDBStatus.CANCELLED
        appointment.updated_at = datetime.now()
        self.db.commit()
        self.db.refresh(appointment)
        queue = self.db.query(QueueDB).filter(QueueDB.id == appointment.queue_id).first()
        student = self.db.query(StudentDB).filter(StudentDB.id == appointment.student_id).first()
        return self._to_appointment(appointment, queue, student)

    def _generate_reference_code(self) -> str:
        for _ in range(10):
            candidate = f"APT-{secrets.randbelow(1_000_000):06d}"
            exists = self.db.query(AppointmentDB).filter(AppointmentDB.reference_code == candidate).first()
            if not exists:
                return candidate
        raise RuntimeError("Could not generate a unique appointment reference code")

    def _to_appointment(
        self,
        db_appt: AppointmentDB,
        queue: Optional[QueueDB] = None,
        student: Optional[StudentDB] = None,
        include_token: bool = False,
    ):
        """Convert DB model to Pydantic model"""
        data = dict(
            id=db_appt.id,
            reference_code=db_appt.reference_code,
            student_id=db_appt.student_id,
            queue_id=db_appt.queue_id,
            appointment_date=db_appt.appointment_date,
            slot_start_time=db_appt.slot_start_time,
            slot_end_time=db_appt.slot_end_time,
            document_type=DocumentType(db_appt.document_type) if db_appt.document_type else None,
            status=AppointmentStatus(db_appt.status.value),
            checked_in_at=db_appt.checked_in_at,
            ticket_id=db_appt.ticket_id,
            created_at=db_appt.created_at,
            updated_at=db_appt.updated_at,
            queue_name=queue.name if queue else None,
            student_number=student.student_id if student else None,
            student_name=f"{student.first_name} {student.last_name}" if student else None,
        )
        if include_token:
            return AppointmentBooked(**data, qr_token=db_appt.qr_token)
        return Appointment(**data)
