"""Admin-only reporting endpoints: transaction history + peak-volume calendar."""
import csv
import io
from datetime import date, datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..core.audit import log_security_event
from ..core.config import settings
from ..core.database import get_db
from ..core.security import require_role
from ..db_models import UserRole
from ..models.report import (
    CalendarSummary, ReportKind, ReportPriority, ReportStatus,
    TransactionHistoryPage,
)
from ..models.user import User
from ..services import ReportService

router = APIRouter()


def _today_campus() -> date:
    return datetime.now(ZoneInfo(settings.CAMPUS_TIMEZONE)).date()


def _resolve_window(date_from: Optional[date], date_to: Optional[date]) -> tuple[date, date]:
    resolved_to = date_to or _today_campus()
    resolved_from = date_from or (resolved_to - timedelta(days=30))
    return resolved_from, resolved_to


@router.get("/transactions", response_model=TransactionHistoryPage)
def list_transactions(
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    kind: list[ReportKind] = Query(default_factory=lambda: list(ReportKind)),
    status: Optional[list[ReportStatus]] = Query(None),
    queue_id: Optional[int] = Query(None, gt=0),
    student_number: Optional[str] = Query(None, pattern=r"^\d{10}$"),
    priority: Optional[ReportPriority] = Query(None),
    skip: int = Query(0, ge=0, le=100000),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Paginated, filterable merged history of tickets and appointments."""
    resolved_from, resolved_to = _resolve_window(date_from, date_to)
    service = ReportService(db)
    try:
        return service.get_transactions(
            date_from=resolved_from, date_to=resolved_to,
            kinds=[k.value for k in kind],
            statuses=[s.value for s in status] if status else None,
            queue_id=queue_id, student_number=student_number,
            priority=priority.value if priority else None,
            skip=skip, limit=limit,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/calendar", response_model=CalendarSummary)
def get_calendar(
    year: int = Query(default_factory=lambda: _today_campus().year, ge=2020, le=2100),
    month: int = Query(default_factory=lambda: _today_campus().month, ge=1, le=12),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Per-day transaction volume for one month, plus peak day and busiest hours."""
    service = ReportService(db)
    try:
        return service.get_calendar(year=year, month=month)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


_CSV_COLUMNS = [
    "kind", "reference", "student_number", "student_name", "service",
    "queue_name", "status", "priority", "created_at", "occurred_at",
    "appointment_date",
]


def _csv_safe(value: str) -> str:
    """Neutralize spreadsheet formula injection. student_name / service come
    from public unauthenticated kiosk endpoints, so a cell beginning =/+/-/@
    (or a control char Excel strips to reach one) must not be run as a formula
    when an admin opens the export."""
    if value and value[0] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


@router.get("/transactions.csv")
def export_transactions_csv(
    request: Request,
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    kind: list[ReportKind] = Query(default_factory=lambda: list(ReportKind)),
    status: Optional[list[ReportStatus]] = Query(None),
    queue_id: Optional[int] = Query(None, gt=0),
    student_number: Optional[str] = Query(None, pattern=r"^\d{10}$"),
    priority: Optional[ReportPriority] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Download every row matching the filters as CSV (audit export)."""
    resolved_from, resolved_to = _resolve_window(date_from, date_to)
    service = ReportService(db)
    try:
        rows = service.get_all_transactions(
            date_from=resolved_from, date_to=resolved_to,
            kinds=[k.value for k in kind],
            statuses=[s.value for s in status] if status else None,
            queue_id=queue_id, student_number=student_number,
            priority=priority.value if priority else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(_CSV_COLUMNS)
    for r in rows:
        writer.writerow([
            _csv_safe(r.kind), _csv_safe(r.reference),
            _csv_safe(r.student_number), _csv_safe(r.student_name),
            _csv_safe(r.service), _csv_safe(r.queue_name),
            _csv_safe(r.status), _csv_safe(r.priority or ""),
            r.created_at.isoformat(),
            r.occurred_at.isoformat() if r.occurred_at else "",
            r.appointment_date.isoformat() if r.appointment_date else "",
        ])

    log_security_event(
        "report.exported", outcome="success", request=request,
        actor=current_user.username,
        detail=f"{len(rows)} rows, {resolved_from}..{resolved_to}",
    )

    filename = f"transactions_{resolved_from}_{resolved_to}.csv"
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
