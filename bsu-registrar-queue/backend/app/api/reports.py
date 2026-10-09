"""Admin-only reporting endpoints: transaction history + peak-volume calendar."""
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session

from ..core.audit import log_security_event
from ..core import campus_time
from ..core.database import get_db
from ..core.security import require_role
from ..db_models import QueueDB, UserRole
from ..models.report import (
    CalendarSummary, ReportKind, ReportPriority, ReportStatus,
    TransactionHistoryPage,
)
from ..models.user import User
from ..services import ReportService
from ..services.report_export import ExportContext, build_transactions_workbook

router = APIRouter()


def _today_campus() -> date:
    return campus_time.campus_today()


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


_XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("/transactions.xlsx")
def export_transactions_xlsx(
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
    """Download every row matching the filters as a branded Excel report (audit export)."""
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

    queue_name = None
    if queue_id is not None:
        queue = db.get(QueueDB, queue_id)
        queue_name = queue.name if queue else f"#{queue_id}"
    content = build_transactions_workbook(rows, ExportContext(
        date_from=resolved_from, date_to=resolved_to,
        kinds=[k.value for k in kind],
        statuses=[s.value for s in status] if status else None,
        queue_name=queue_name,
        priority=priority.value if priority else None,
        student_number=student_number,
        generated_by=f"{current_user.full_name} ({current_user.username})",
        generated_at=campus_time.campus_now(),
    ))

    log_security_event(
        "report.exported", outcome="success", request=request,
        actor=current_user.username,
        detail=f"{len(rows)} rows, {resolved_from}..{resolved_to}",
    )

    filename = f"transactions_{resolved_from}_{resolved_to}.xlsx"
    return Response(
        content=content,
        media_type=_XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
