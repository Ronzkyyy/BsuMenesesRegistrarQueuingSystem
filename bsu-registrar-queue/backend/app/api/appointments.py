"""
Appointment booking and check-in endpoints
"""
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from sqlalchemy.orm import Session
from typing import List, Optional

from ..core.audit import log_security_event
from ..core.database import get_db
from ..core.limiter import limiter
from ..core.security import require_role
from ..db_models import UserRole
from ..models.appointment import (
    Appointment, AppointmentBooked, AppointmentCheckInRequest, AppointmentCreate,
    AppointmentListResponse, SlotAvailability
)
from ..models.ticket import Ticket
from ..models.user import User
from ..services.appointment_service import (
    AppointmentExpiredError, AppointmentService, AppointmentWindowError
)


router = APIRouter()


@router.get("/availability", response_model=List[SlotAvailability])
def get_availability(
    queue_id: int = Query(..., gt=0),
    appointment_date: date = Query(...),
    db: Session = Depends(get_db)
):
    """List bookable slots and remaining capacity for a queue/date (public)"""
    service = AppointmentService(db)
    return service.get_availability(queue_id, appointment_date)


@router.post("", response_model=AppointmentBooked)
@limiter.limit("10/minute")
def create_appointment(
    request: Request,
    appointment: AppointmentCreate,
    db: Session = Depends(get_db)
):
    """Student books an appointment (public endpoint)"""
    service = AppointmentService(db)
    try:
        return service.create_appointment(appointment)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/lookup", response_model=Appointment)
@limiter.limit("10/minute")
def lookup_appointment(
    request: Request,
    student_id: str = Query(..., pattern=r"^\d{10}$", description="10-digit student number"),
    reference_code: str = Query(..., min_length=1, max_length=20),
    db: Session = Depends(get_db)
):
    """Student re-views their booking (public endpoint)"""
    service = AppointmentService(db)
    appointment = service.lookup(student_id, reference_code)
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    return appointment


@router.post("/{appointment_id}/cancel", response_model=Appointment)
@limiter.limit("10/minute")
def cancel_appointment(
    request: Request,
    appointment_id: int = Path(..., gt=0),
    student_id: str = Query(..., pattern=r"^\d{10}$", description="10-digit student number"),
    db: Session = Depends(get_db)
):
    """Student cancels their own booked appointment (public endpoint)"""
    service = AppointmentService(db)
    try:
        appointment = service.cancel(appointment_id, student_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    return appointment


@router.get("/search", response_model=List[Appointment])
def search_appointments(
    query: str = Query(..., min_length=1, max_length=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.STAFF))
):
    """Manual lookup fallback for staff - matches student ID or reference code (staff only)"""
    service = AppointmentService(db)
    return service.search(query)


@router.get("", response_model=AppointmentListResponse)
def list_appointments(
    upcoming: bool = Query(True, description="True: still-booked, dated today or later. False: history (checked-in/cancelled/expired/past)."),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.STAFF))
):
    """Browse who's booked an appointment - upcoming by default, or history via upcoming=false,
    optionally narrowed to a date/date range (staff only)."""
    service = AppointmentService(db)
    items, total = service.list_appointments(
        upcoming=upcoming, date_from=date_from, date_to=date_to, skip=skip, limit=limit
    )
    return AppointmentListResponse(items=items, total=total, skip=skip, limit=limit)


@router.post("/checkin", response_model=Ticket)
def check_in(
    payload: AppointmentCheckInRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.STAFF))
):
    """Scan or manually check in an appointment, creating a queue ticket (staff only)"""
    service = AppointmentService(db)
    try:
        return service.check_in(
            token=payload.token,
            reference_code=payload.reference_code,
            staff_user_id=current_user.id,
            force=payload.force,
        )
    except AppointmentExpiredError as e:
        # 410 Gone, with the booking's own details so the check-in screen can
        # render an "expired appointment" panel rather than a bare error string.
        appt = e.appointment
        raise HTTPException(status_code=410, detail={
            "message": str(e),
            "code": "appointment_expired",
            "id": appt.id,
            "reference_code": appt.reference_code,
            "appointment_date": appt.appointment_date.isoformat(),
            "slot_start_time": appt.slot_start_time.isoformat(),
        })
    except AppointmentWindowError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{appointment_id}/staff-cancel", response_model=Appointment)
def staff_cancel_expired_appointment(
    request: Request,
    appointment_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.STAFF))
):
    """Staff removes one overdue appointment from the check-in flow (staff only).

    A soft cancel, not a hard delete - see AppointmentService.staff_cancel_expired.
    """
    service = AppointmentService(db)
    try:
        appointment = service.staff_cancel_expired(appointment_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    log_security_event(
        "appointment.staff_cancelled", outcome="success", request=request,
        actor=current_user.username, target=f"appointment#{appointment_id}",
    )
    return appointment
