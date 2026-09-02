# Transaction History & Peak-Transactions Audit Calendar — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give admins a filterable, paginated history of past transactions
(tickets + appointments) plus a monthly heatmap calendar of transaction
volume with a busiest-hours breakdown and a CSV audit export.

**Architecture:** A new read-only reporting module. Backend: `ReportService`
runs ORM queries against the existing `tickets` / `appointments` tables and
aggregates in Python (day/hour bucketing in campus-local time); a thin
admin-gated `app/api/reports.py` router exposes three endpoints. Frontend: a
new `TransactionHistoryView.vue` at `/admin/reports` with a `date-fns`-built
month heatmap, a `vue-chartjs` busiest-hours bar chart, and a filterable
paginated table. No schema change, no migration.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 ORM, Pydantic v2, pytest; Vue 3 +
Pinia + Vue Router, `date-fns`, `chart.js` / `vue-chartjs`, Vitest.

**Spec:** `docs/superpowers/specs/2026-09-03-transaction-history-audit-design.md`

## Global Constraints

- **Branch:** all work on `feat/transaction-history-audit` (already created off `master`).
- **ORM only.** All DB access through the SQLAlchemy ORM query builder
  (`.query(...).filter(...)`). No `text()`, no f-string SQL, no `cursor.execute`.
- **Authorize on the server.** Every reports route declares
  `Depends(require_role(UserRole.ADMIN))` — Registrar and Staff get 403.
- **New sensitive action → audit log.** The CSV export calls
  `log_security_event("report.exported", outcome="success", request=request,
  actor=current_user.username, detail=...)`. Never pass a password/token/body.
- **Timezone:** day and hour bucketing uses `settings.CAMPUS_TIMEZONE`
  (new setting, default `"Asia/Manila"`), never naive UTC.
- **No new dependencies.** `date-fns`, `chart.js`, `vue-chartjs` are already
  in `frontend/package.json`; `zoneinfo` is stdlib.
- **Response models** are built by hand in the service (not from ORM rows), so
  no `from_attributes` / `extra="forbid"` needed on them.
- **Frontend** uses the shared `api` axios instance in `stores/queue.js`
  (relative `/api` base, `withCredentials: true`) — never a new axios or a
  hardcoded host.
- **Commit message trailer** (every commit):
  ```
  Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_0128ZcebyPQToRp5dUTSgdCp
  ```
- **Run tests:** backend `cd backend && python -m pytest`; frontend
  `cd frontend && npm run test`. `uvicorn --reload` is broken on this machine —
  never use it; use the `run-bsu-registrar-queue` skill to launch the app.

---

## Task 1: Config setting + Pydantic response models + `ReportService.get_transactions`

**Files:**
- Modify: `backend/app/core/config.py` (add `CAMPUS_TIMEZONE`)
- Modify: `backend/.env.example` (document `CAMPUS_TIMEZONE`)
- Create: `backend/app/models/report.py`
- Create: `backend/app/services/report_service.py`
- Modify: `backend/app/services/__init__.py` (export `ReportService`)
- Test: `backend/tests/test_report_service.py`

**Interfaces:**
- Produces:
  - `backend/app/models/report.py`:
    - `ReportKind(str, Enum)`: `TICKET="ticket"`, `APPOINTMENT="appointment"`
    - `ReportStatus(str, Enum)`: `WAITING="waiting"`, `SERVING="serving"`,
      `COMPLETED="completed"`, `CANCELLED="cancelled"`, `NO_SHOW="no_show"`,
      `BOOKED="booked"`, `CHECKED_IN="checked_in"`, `EXPIRED="expired"`
    - `ReportPriority(str, Enum)`: `NORMAL="normal"`, `PRIORITY="priority"`, `URGENT="urgent"`
    - `TransactionRow(BaseModel)`: `kind: str`, `id: int`, `reference: str`,
      `student_number: str`, `student_name: str`, `service: str`,
      `queue_name: str`, `status: str`, `priority: Optional[str]`,
      `created_at: datetime`, `occurred_at: Optional[datetime]`,
      `appointment_date: Optional[date]`
    - `TransactionHistoryPage(BaseModel)`: `items: list[TransactionRow]`,
      `total: int`, `skip: int`, `limit: int`
    - `CalendarDay(BaseModel)`: `date: date`, `total: int`, `tickets: int`,
      `appointments: int`, `by_status: dict[str, int]`
    - `CalendarSummary(BaseModel)`: `year: int`, `month: int`,
      `month_total: int`, `peak_day: Optional[date]`, `peak_count: int`,
      `busiest_hours: list[int]`, `days: list[CalendarDay]`
  - `ReportService(db: Session)` with:
    - `get_transactions(*, date_from: date, date_to: date, kinds: list[str],
      statuses: Optional[list[str]], queue_id: Optional[int],
      student_number: Optional[str], priority: Optional[str], skip: int,
      limit: int) -> TransactionHistoryPage` — raises `ValueError` if
      `date_from > date_to`.
    - private `_collect_rows(start_utc, end_utc, kinds, statuses, queue_id,
      student_number, priority, cap) -> tuple[list[TransactionRow], int]`
    - private `_utc_window(date_from, date_to) -> tuple[datetime, datetime]`

- [ ] **Step 1: Add the `CAMPUS_TIMEZONE` setting**

In `backend/app/core/config.py`, inside `class Settings`, right after the
`CAMPUS_NAME` line (currently line 46), add:

```python
    # IANA timezone used for day/hour bucketing in the admin reports module
    # (transaction history calendar). The campus is UTC+8; a report that
    # bucketed by naive UTC would misattribute early-morning/late-evening
    # activity to the wrong day.
    CAMPUS_TIMEZONE: str = "Asia/Manila"
```

In `backend/.env.example`, add under `CAMPUS_NAME`:

```env
CAMPUS_TIMEZONE=Asia/Manila
```

- [ ] **Step 2: Write the failing test file**

Create `backend/tests/test_report_service.py`:

```python
"""ReportService - transaction history queries and calendar aggregation."""
from datetime import date, datetime, timedelta, timezone

import pytest

from app.db_models import (
    AppointmentDB, AppointmentDBStatus, PriorityLevel, TicketDB, TicketDBStatus,
)
from app.services.report_service import ReportService

UTC = timezone.utc


def _ticket(db, student, queue, *, status=TicketDBStatus.COMPLETED,
            created_at, completed_at=None, served_at=None,
            priority=PriorityLevel.NORMAL, purpose="Clearance", ticket_number=1):
    row = TicketDB(
        ticket_number=ticket_number, student_id=student.id, queue_id=queue.id,
        priority=priority, purpose=purpose, status=status, position=0,
        created_at=created_at, served_at=served_at, completed_at=completed_at,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _appointment(db, student, queue, *, status=AppointmentDBStatus.CHECKED_IN,
                 created_at, checked_in_at=None, ref="APT-000001"):
    row = AppointmentDB(
        reference_code=ref, student_id=student.id, queue_id=queue.id,
        appointment_date=created_at.date(),
        slot_start_time=datetime(2000, 1, 1, 9, 0).time(),
        slot_end_time=datetime(2000, 1, 1, 9, 30).time(),
        purpose="Enrollment", qr_token=f"tok-{ref}", status=status,
        created_at=created_at, checked_in_at=checked_in_at,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_default_window_returns_only_attended_rows_newest_first(db_session, make_queue, make_student):
    queue = make_queue()
    s1, s2, s3 = make_student(), make_student(), make_student()
    _ticket(db_session, s1, queue, status=TicketDBStatus.COMPLETED,
            created_at=datetime(2026, 6, 10, 3, 0, tzinfo=UTC), ticket_number=1)
    _ticket(db_session, s2, queue, status=TicketDBStatus.WAITING,
            created_at=datetime(2026, 6, 11, 3, 0, tzinfo=UTC), ticket_number=2)
    _ticket(db_session, s3, queue, status=TicketDBStatus.SERVING,
            created_at=datetime(2026, 6, 12, 3, 0, tzinfo=UTC), ticket_number=3)

    svc = ReportService(db_session)
    page = svc.get_transactions(
        date_from=date(2026, 6, 1), date_to=date(2026, 6, 30),
        kinds=["ticket", "appointment"], statuses=None, queue_id=None,
        student_number=None, priority=None, skip=0, limit=50,
    )

    assert [r.status for r in page.items] == ["serving", "completed"]
    assert page.total == 2


def test_explicit_status_filter_overrides_the_attended_default(db_session, make_queue, make_student):
    queue = make_queue()
    _ticket(db_session, make_student(), queue, status=TicketDBStatus.CANCELLED,
            created_at=datetime(2026, 6, 10, 3, 0, tzinfo=UTC), ticket_number=1)
    _ticket(db_session, make_student(), queue, status=TicketDBStatus.COMPLETED,
            created_at=datetime(2026, 6, 10, 4, 0, tzinfo=UTC), ticket_number=2)

    svc = ReportService(db_session)
    page = svc.get_transactions(
        date_from=date(2026, 6, 1), date_to=date(2026, 6, 30),
        kinds=["ticket"], statuses=["cancelled"], queue_id=None,
        student_number=None, priority=None, skip=0, limit=50,
    )

    assert page.total == 1
    assert page.items[0].status == "cancelled"


def test_kind_filter_scopes_to_appointments_only(db_session, make_queue, make_student):
    queue = make_queue()
    _ticket(db_session, make_student(), queue,
            created_at=datetime(2026, 6, 10, 3, 0, tzinfo=UTC), ticket_number=1)
    _appointment(db_session, make_student(), queue,
                 created_at=datetime(2026, 6, 10, 4, 0, tzinfo=UTC))

    svc = ReportService(db_session)
    page = svc.get_transactions(
        date_from=date(2026, 6, 1), date_to=date(2026, 6, 30),
        kinds=["appointment"], statuses=None, queue_id=None,
        student_number=None, priority=None, skip=0, limit=50,
    )

    assert page.total == 1
    assert page.items[0].kind == "appointment"
    assert page.items[0].reference == "APT-000001"


def test_queue_and_student_filters(db_session, make_queue, make_student):
    q1, q2 = make_queue(), make_queue()
    target = make_student()
    _ticket(db_session, target, q1,
            created_at=datetime(2026, 6, 10, 3, 0, tzinfo=UTC), ticket_number=1)
    _ticket(db_session, make_student(), q2,
            created_at=datetime(2026, 6, 10, 4, 0, tzinfo=UTC), ticket_number=1)

    svc = ReportService(db_session)
    by_queue = svc.get_transactions(
        date_from=date(2026, 6, 1), date_to=date(2026, 6, 30), kinds=["ticket"],
        statuses=None, queue_id=q1.id, student_number=None, priority=None,
        skip=0, limit=50,
    )
    assert by_queue.total == 1 and by_queue.items[0].queue_name == q1.name

    by_student = svc.get_transactions(
        date_from=date(2026, 6, 1), date_to=date(2026, 6, 30), kinds=["ticket"],
        statuses=None, queue_id=None, student_number=target.student_id,
        priority=None, skip=0, limit=50,
    )
    assert by_student.total == 1
    assert by_student.items[0].student_number == target.student_id


def test_pagination_splits_without_overlap(db_session, make_queue, make_student):
    queue = make_queue()
    for i in range(5):
        _ticket(db_session, make_student(), queue,
                created_at=datetime(2026, 6, 10, 1 + i, 0, tzinfo=UTC),
                ticket_number=i + 1)

    svc = ReportService(db_session)
    common = dict(date_from=date(2026, 6, 1), date_to=date(2026, 6, 30),
                  kinds=["ticket"], statuses=["completed"], queue_id=None,
                  student_number=None, priority=None, limit=2)
    p1 = svc.get_transactions(skip=0, **common)
    p2 = svc.get_transactions(skip=2, **common)

    assert p1.total == 5 and p2.total == 5
    assert len(p1.items) == 2 and len(p2.items) == 2
    assert {r.id for r in p1.items}.isdisjoint({r.id for r in p2.items})


def test_date_from_after_date_to_raises(db_session):
    svc = ReportService(db_session)
    with pytest.raises(ValueError, match="date_from"):
        svc.get_transactions(
            date_from=date(2026, 6, 30), date_to=date(2026, 6, 1),
            kinds=["ticket"], statuses=None, queue_id=None,
            student_number=None, priority=None, skip=0, limit=50,
        )
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_report_service.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.report_service'`.

- [ ] **Step 4: Create the Pydantic models**

Create `backend/app/models/report.py`:

```python
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
```

- [ ] **Step 5: Create `ReportService` with `get_transactions`**

Create `backend/app/services/report_service.py`:

```python
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
```

- [ ] **Step 6: Export `ReportService`**

In `backend/app/services/__init__.py`, add the import and `__all__` entry:

```python
from .report_service import ReportService
```
and add `"ReportService"` to the `__all__` list.

- [ ] **Step 7: Run the tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_report_service.py -q`
Expected: PASS (6 passed).

- [ ] **Step 8: Run the full backend suite (no regressions)**

Run: `cd backend && python -m pytest -q`
Expected: all pass.

- [ ] **Step 9: Commit**

```bash
git add backend/app/core/config.py backend/.env.example backend/app/models/report.py backend/app/services/report_service.py backend/app/services/__init__.py backend/tests/test_report_service.py
git commit -m "$(cat <<'EOF'
feat(reports): ReportService.get_transactions + CAMPUS_TIMEZONE setting

Read-only merged tickets+appointments history with date/status/kind/queue/
student/priority filters and offset pagination. ORM query builder only;
day-window bounds computed in campus-local time.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0128ZcebyPQToRp5dUTSgdCp
EOF
)"
```

---

## Task 2: `ReportService.get_calendar` + `get_all_transactions`

**Files:**
- Modify: `backend/app/services/report_service.py`
- Test: `backend/tests/test_report_service.py` (add cases)

**Interfaces:**
- Consumes: `ReportService`, `_collect_rows`, `_utc_window` from Task 1.
- Produces:
  - `ReportService.get_calendar(*, year: int, month: int) -> CalendarSummary`
    — raises `ValueError` on an impossible year/month.
  - `ReportService.get_all_transactions(*, date_from, date_to, kinds,
    statuses, queue_id, student_number, priority) -> list[TransactionRow]`
    — no pagination; raises `ValueError` if the match count exceeds
    `MAX_EXPORT_ROWS` (10 000) or `date_from > date_to`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_report_service.py`:

```python
def test_calendar_buckets_by_day_and_finds_peak(db_session, make_queue, make_student):
    queue = make_queue()
    # 1 transaction on Jun 5, 3 on Jun 6 (all well inside Manila's day).
    _ticket(db_session, make_student(), queue,
            created_at=datetime(2026, 6, 5, 6, 0, tzinfo=UTC), ticket_number=1)
    for i in range(3):
        _ticket(db_session, make_student(), queue,
                created_at=datetime(2026, 6, 6, 6 + i, 0, tzinfo=UTC),
                ticket_number=10 + i)

    svc = ReportService(db_session)
    cal = svc.get_calendar(year=2026, month=6)

    assert cal.month_total == 4
    assert cal.peak_day == date(2026, 6, 6)
    assert cal.peak_count == 3
    assert len(cal.days) == 30
    jun6 = next(d for d in cal.days if d.date == date(2026, 6, 6))
    assert jun6.total == 3 and jun6.tickets == 3 and jun6.appointments == 0
    assert sum(cal.busiest_hours) == 4
    assert len(cal.busiest_hours) == 24


def test_calendar_bucketing_uses_campus_timezone_not_utc(db_session, make_queue, make_student):
    queue = make_queue()
    # 2026-06-01 16:30 UTC == 2026-06-02 00:30 Asia/Manila (UTC+8).
    _ticket(db_session, make_student(), queue,
            created_at=datetime(2026, 6, 1, 16, 30, tzinfo=UTC), ticket_number=1)

    svc = ReportService(db_session)
    cal = svc.get_calendar(year=2026, month=6)

    jun1 = next(d for d in cal.days if d.date == date(2026, 6, 1))
    jun2 = next(d for d in cal.days if d.date == date(2026, 6, 2))
    assert jun1.total == 0
    assert jun2.total == 1
    assert cal.busiest_hours[0] == 1
    assert cal.busiest_hours[16] == 0


def test_get_all_transactions_rejects_oversized_export(db_session, make_queue, make_student, monkeypatch):
    from app.services import report_service as rs
    monkeypatch.setattr(rs, "MAX_EXPORT_ROWS", 1)
    queue = make_queue()
    for i in range(2):
        _ticket(db_session, make_student(), queue,
                created_at=datetime(2026, 6, 10, 1 + i, 0, tzinfo=UTC),
                ticket_number=i + 1)

    svc = ReportService(db_session)
    with pytest.raises(ValueError, match="Too many rows"):
        svc.get_all_transactions(
            date_from=date(2026, 6, 1), date_to=date(2026, 6, 30),
            kinds=["ticket"], statuses=["completed"], queue_id=None,
            student_number=None, priority=None,
        )
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd backend && python -m pytest tests/test_report_service.py -q -k "calendar or oversized"`
Expected: FAIL — `AttributeError: 'ReportService' object has no attribute 'get_calendar'`.

- [ ] **Step 3: Implement `get_calendar` and `get_all_transactions`**

Append these methods to `class ReportService` in
`backend/app/services/report_service.py`:

```python
    def get_all_transactions(self, *, date_from: date, date_to: date,
                             kinds: list[str], statuses: Optional[list[str]],
                             queue_id: Optional[int],
                             student_number: Optional[str],
                             priority: Optional[str]) -> list[TransactionRow]:
        if date_from > date_to:
            raise ValueError("date_from must not be after date_to")
        start_utc, end_utc = self._utc_window(date_from, date_to)
        rows, total = self._collect_rows(
            start_utc, end_utc, kinds, statuses, queue_id, student_number,
            priority, cap=MAX_EXPORT_ROWS + 1)
        if total > MAX_EXPORT_ROWS:
            raise ValueError(
                f"Too many rows to export ({total}). "
                f"Narrow the date range or filters.")
        return rows

    def get_calendar(self, *, year: int, month: int) -> CalendarSummary:
        try:
            first = date(year, month, 1)
        except ValueError as e:
            raise ValueError("Invalid year/month") from e
        if month == 12:
            next_first = date(year + 1, 1, 1)
        else:
            next_first = date(year, month + 1, 1)

        start_utc = datetime.combine(
            first, time.min, tzinfo=self.tz).astimezone(timezone.utc)
        end_utc = datetime.combine(
            next_first, time.min, tzinfo=self.tz).astimezone(timezone.utc)

        stats: dict[date, dict] = {}
        d = first
        while d < next_first:
            stats[d] = {"tickets": 0, "appointments": 0,
                        "by_status": defaultdict(int)}
            d += timedelta(days=1)
        hours = [0] * 24

        for created_at, status in self.db.query(
                TicketDB.created_at, TicketDB.status).filter(
                TicketDB.created_at >= start_utc,
                TicketDB.created_at < end_utc):
            local = created_at.astimezone(self.tz)
            bucket = stats[local.date()]
            bucket["tickets"] += 1
            bucket["by_status"][status.value] += 1
            hours[local.hour] += 1

        for created_at, status in self.db.query(
                AppointmentDB.created_at, AppointmentDB.status).filter(
                AppointmentDB.created_at >= start_utc,
                AppointmentDB.created_at < end_utc):
            local = created_at.astimezone(self.tz)
            bucket = stats[local.date()]
            bucket["appointments"] += 1
            bucket["by_status"][status.value] += 1
            hours[local.hour] += 1

        days: list[CalendarDay] = []
        peak_day: Optional[date] = None
        peak_count = 0
        month_total = 0
        for day in sorted(stats):
            b = stats[day]
            total = b["tickets"] + b["appointments"]
            month_total += total
            if total > peak_count:
                peak_day, peak_count = day, total
            days.append(CalendarDay(
                date=day, total=total, tickets=b["tickets"],
                appointments=b["appointments"], by_status=dict(b["by_status"])))

        return CalendarSummary(
            year=year, month=month, month_total=month_total,
            peak_day=peak_day, peak_count=peak_count,
            busiest_hours=hours, days=days)
```

- [ ] **Step 4: Run to verify they pass**

Run: `cd backend && python -m pytest tests/test_report_service.py -q`
Expected: PASS (9 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/report_service.py backend/tests/test_report_service.py
git commit -m "$(cat <<'EOF'
feat(reports): calendar aggregation + capped CSV row collection

get_calendar buckets a month of tickets+appointments by campus-local day
and hour, with peak-day and 24-bucket busiest-hours output. get_all_
transactions returns the full filtered set for export, refusing >10k rows.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0128ZcebyPQToRp5dUTSgdCp
EOF
)"
```

---

## Task 3: API router — `/reports/transactions` + `/reports/calendar`

**Files:**
- Create: `backend/app/api/reports.py`
- Modify: `backend/app/api/router.py`
- Test: `backend/tests/test_reports_api.py`

**Interfaces:**
- Consumes: `ReportService` (Tasks 1-2), `require_role`, `get_db`,
  `UserRole` (from `..db_models`), the `Report*` enums + response models
  from `..models.report`.
- Produces:
  - `GET /api/reports/transactions` → `TransactionHistoryPage`
  - `GET /api/reports/calendar` → `CalendarSummary`
  - module-level `router` (APIRouter) exported for `router.py`.

- [ ] **Step 1: Write the failing test file**

Create `backend/tests/test_reports_api.py`:

```python
"""Admin-only reports API: history + calendar endpoints."""
from datetime import datetime, timezone

from app.db_models import TicketDB, TicketDBStatus, UserRole

UTC = timezone.utc


def _login(client, user):
    return client.post("/api/auth/login",
                       data={"username": user.username,
                             "password": user._plain_password})


def _seed_completed_ticket(db_session, student, queue, when):
    row = TicketDB(
        ticket_number=1, student_id=student.id, queue_id=queue.id,
        purpose="Clearance", status=TicketDBStatus.COMPLETED, position=0,
        created_at=when, completed_at=when,
    )
    db_session.add(row)
    db_session.commit()


def test_admin_can_list_transactions(client, db_session, make_user, make_queue, make_student):
    admin = make_user(role=UserRole.ADMIN)
    _seed_completed_ticket(db_session, make_student(), make_queue(),
                           datetime(2026, 6, 10, 3, 0, tzinfo=UTC))
    _login(client, admin)

    r = client.get("/api/reports/transactions",
                   params={"date_from": "2026-06-01", "date_to": "2026-06-30"})

    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["kind"] == "ticket"


def test_admin_can_get_calendar(client, db_session, make_user, make_queue, make_student):
    admin = make_user(role=UserRole.ADMIN)
    _seed_completed_ticket(db_session, make_student(), make_queue(),
                           datetime(2026, 6, 10, 3, 0, tzinfo=UTC))
    _login(client, admin)

    r = client.get("/api/reports/calendar", params={"year": 2026, "month": 6})

    assert r.status_code == 200
    body = r.json()
    assert body["month_total"] == 1
    assert body["peak_day"] == "2026-06-10"
    assert len(body["busiest_hours"]) == 24
    assert len(body["days"]) == 30


def test_registrar_is_forbidden(client, make_user):
    registrar = make_user(role=UserRole.REGISTRAR)
    _login(client, registrar)
    assert client.get("/api/reports/transactions").status_code == 403
    assert client.get("/api/reports/calendar",
                      params={"year": 2026, "month": 6}).status_code == 403


def test_staff_is_forbidden(client, make_user):
    staff = make_user(role=UserRole.STAFF)
    _login(client, staff)
    assert client.get("/api/reports/transactions").status_code == 403


def test_unauthenticated_is_401(client):
    assert client.get("/api/reports/transactions").status_code == 401


def test_bad_params_are_422(client, make_user):
    admin = make_user(role=UserRole.ADMIN)
    _login(client, admin)
    assert client.get("/api/reports/transactions",
                      params={"limit": 0}).status_code == 422
    assert client.get("/api/reports/transactions",
                      params={"student_number": "abc"}).status_code == 422
    assert client.get("/api/reports/transactions",
                      params={"status": "nonsense"}).status_code == 422
    assert client.get("/api/reports/calendar",
                      params={"year": 2026, "month": 13}).status_code == 422


def test_date_from_after_date_to_is_400(client, make_user):
    admin = make_user(role=UserRole.ADMIN)
    _login(client, admin)
    r = client.get("/api/reports/transactions",
                   params={"date_from": "2026-06-30", "date_to": "2026-06-01"})
    assert r.status_code == 400
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd backend && python -m pytest tests/test_reports_api.py -q`
Expected: FAIL — 404s (routes not mounted yet).

- [ ] **Step 3: Create the router**

Create `backend/app/api/reports.py`:

```python
"""Admin-only reporting endpoints: transaction history + peak-volume calendar."""
from datetime import date, datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

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
    skip: int = Query(0, ge=0),
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
```

- [ ] **Step 4: Mount the router**

In `backend/app/api/router.py`:
- add after the other imports: `from .reports import router as reports_router`
- add after the last `include_router` line:
  `router.include_router(reports_router, prefix="/reports", tags=["reports"])`

- [ ] **Step 5: Run to verify they pass**

Run: `cd backend && python -m pytest tests/test_reports_api.py -q`
Expected: PASS (7 passed).

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/reports.py backend/app/api/router.py backend/tests/test_reports_api.py
git commit -m "$(cat <<'EOF'
feat(reports): admin-only GET /reports/transactions and /reports/calendar

Thin router over ReportService; require_role(ADMIN) on both routes.
Query params are enum/bounded so bad input 422s; a date_from>date_to
window 400s with a plain message.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0128ZcebyPQToRp5dUTSgdCp
EOF
)"
```

---

## Task 4: CSV audit export endpoint + `report.exported` audit event + docs

**Files:**
- Modify: `backend/app/api/reports.py`
- Test: `backend/tests/test_reports_api.py` (add cases)
- Modify: `CLAUDE.md` (audit-events list + API endpoint table row)

**Interfaces:**
- Consumes: `ReportService.get_all_transactions` (Task 2),
  `log_security_event` from `..core.audit`.
- Produces: `GET /api/reports/transactions.csv` → `text/csv` attachment.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_reports_api.py`:

```python
import json
import logging


def _audit_capture():
    logger = logging.getLogger("bsu.security")
    messages: list[str] = []

    class _Cap(logging.Handler):
        def emit(self, record):
            messages.append(record.getMessage())

    handler = _Cap()
    handler.setLevel(logging.INFO)
    logger.addHandler(handler)
    return handler, lambda: [json.loads(m) for m in messages]


def test_csv_export_returns_csv_and_logs_audit_event(client, db_session, make_user, make_queue, make_student):
    admin = make_user(role=UserRole.ADMIN)
    _seed_completed_ticket(db_session, make_student(), make_queue(),
                           datetime(2026, 6, 10, 3, 0, tzinfo=UTC))
    _login(client, admin)

    handler, events = _audit_capture()
    try:
        r = client.get("/api/reports/transactions.csv",
                       params={"date_from": "2026-06-01", "date_to": "2026-06-30"})
    finally:
        logging.getLogger("bsu.security").removeHandler(handler)

    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "attachment; filename=" in r.headers["content-disposition"]
    lines = [ln for ln in r.text.splitlines() if ln.strip()]
    assert lines[0].startswith("kind,reference,student_number")
    assert len(lines) == 2  # header + 1 data row

    exported = [e for e in events() if e["event"] == "report.exported"]
    assert len(exported) == 1
    assert exported[0]["actor"] == admin.username
    assert exported[0]["outcome"] == "success"


def test_csv_export_is_admin_only(client, make_user):
    _login(client, make_user(role=UserRole.REGISTRAR))
    assert client.get("/api/reports/transactions.csv").status_code == 403
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd backend && python -m pytest tests/test_reports_api.py -q -k csv`
Expected: FAIL — 404 (route missing).

- [ ] **Step 3: Add the CSV endpoint**

In `backend/app/api/reports.py`:

Add imports at the top:
```python
import csv
import io

from fastapi import Request
from fastapi.responses import StreamingResponse

from ..core.audit import log_security_event
```

Add this route after `list_transactions`:
```python
_CSV_COLUMNS = [
    "kind", "reference", "student_number", "student_name", "service",
    "queue_name", "status", "priority", "created_at", "occurred_at",
    "appointment_date",
]


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
            r.kind, r.reference, r.student_number, r.student_name, r.service,
            r.queue_name, r.status, r.priority or "",
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
```

- [ ] **Step 4: Run to verify they pass**

Run: `cd backend && python -m pytest tests/test_reports_api.py -q`
Expected: PASS (9 passed).

- [ ] **Step 5: Update `CLAUDE.md`**

In the audit-events list (under "Security audit log", the sentence beginning
"Events currently emitted:"), add `report.exported` to the list, e.g. after
`queue.deleted`:
```
`queue.deleted`, `report.exported`, `security.rate_limited`.
```

In the "API Endpoints" table, add three rows after the
`POST | /api/tickets/queue/{id}/next` row:
```
| GET | `/api/reports/transactions` | Admin | Filterable merged ticket+appointment history |
| GET | `/api/reports/calendar` | Admin | Per-day transaction volume for a month (peak/heatmap) |
| GET | `/api/reports/transactions.csv` | Admin | CSV audit export of the filtered history |
```

- [ ] **Step 6: Run the full backend suite**

Run: `cd backend && python -m pytest -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/reports.py backend/tests/test_reports_api.py CLAUDE.md
git commit -m "$(cat <<'EOF'
feat(reports): CSV audit export + report.exported security event

GET /reports/transactions.csv streams every filtered row and emits one
bsu.security "report.exported" record (actor + row count + window).
Documented the new events/endpoints in CLAUDE.md.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0128ZcebyPQToRp5dUTSgdCp
EOF
)"
```

---

## Task 5: Frontend store — history + calendar actions

**Files:**
- Modify: `frontend/src/stores/queue.js`
- Test: `frontend/src/stores/__tests__/queue.spec.js` (add cases)

**Interfaces:**
- Produces (Pinia store `queue`):
  - state: `transactionHistory` (default
    `{ items: [], total: 0, skip: 0, limit: 50 }`),
    `transactionCalendar` (default `null`)
  - `fetchTransactionHistory(params = {})` → GETs `/reports/transactions`
    with `{ params, paramsSerializer: { indexes: null } }`, stores response
    in `transactionHistory`, returns it; on error sets `this.error` and rethrows.
  - `fetchTransactionCalendar(year, month)` → GETs `/reports/calendar` with
    `{ params: { year, month } }`, stores in `transactionCalendar`, returns it.

- [ ] **Step 1: Write the failing tests**

Append to `frontend/src/stores/__tests__/queue.spec.js` (before the final
closing of the file, as a new `describe` block):

```javascript
describe('reports actions', () => {
  it('fetchTransactionHistory passes filters through and serializes arrays without brackets', async () => {
    const pageData = { items: [{ id: 1, kind: 'ticket' }], total: 1, skip: 0, limit: 50 }
    mockApi.get.mockReturnValueOnce(ok(pageData))
    const store = useQueueStore()

    const params = { date_from: '2026-06-01', date_to: '2026-06-30', kind: ['ticket', 'appointment'] }
    const result = await store.fetchTransactionHistory(params)

    expect(mockApi.get).toHaveBeenCalledWith('/reports/transactions', {
      params,
      paramsSerializer: { indexes: null },
    })
    expect(store.transactionHistory).toEqual(pageData)
    expect(result).toEqual(pageData)
  })

  it('fetchTransactionHistory surfaces the server error and rethrows', async () => {
    mockApi.get.mockReturnValueOnce(fail('Too many rows to export'))
    const store = useQueueStore()

    await expect(store.fetchTransactionHistory({})).rejects.toThrow()

    expect(store.error).toBe('Too many rows to export')
    expect(store.loading).toBe(false)
  })

  it('fetchTransactionCalendar sends year/month as query params', async () => {
    const cal = { year: 2026, month: 6, month_total: 3, days: [], busiest_hours: [] }
    mockApi.get.mockReturnValueOnce(ok(cal))
    const store = useQueueStore()

    await store.fetchTransactionCalendar(2026, 6)

    expect(mockApi.get).toHaveBeenCalledWith('/reports/calendar', {
      params: { year: 2026, month: 6 },
    })
    expect(store.transactionCalendar).toEqual(cal)
  })
})
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd frontend && npm run test -- --run src/stores/__tests__/queue.spec.js`
Expected: FAIL — `store.fetchTransactionHistory is not a function`.

- [ ] **Step 3: Add state**

In `frontend/src/stores/queue.js`, in the `state` object, after the
`// Dashboard` block (`dashboardSummary: null,`), add:

```javascript
    // Reports (admin transaction history + peak-volume calendar)
    transactionHistory: { items: [], total: 0, skip: 0, limit: 50 },
    transactionCalendar: null,
```

- [ ] **Step 4: Add actions**

In `frontend/src/stores/queue.js`, immediately after the
`// ============ DASHBOARD ACTIONS ============` block (after
`fetchDashboardSummary` closes), add:

```javascript
    // ============ REPORTS ACTIONS ============

    async fetchTransactionHistory(params = {}) {
      this.loading = true
      this.error = null
      try {
        // FastAPI reads repeated query params (`kind=ticket&kind=appointment`);
        // axios' default array serialization uses `kind[]=` which FastAPI
        // ignores. `indexes: null` repeats the bare key.
        const response = await api.get('/reports/transactions', {
          params,
          paramsSerializer: { indexes: null },
        })
        this.transactionHistory = response.data
        return response.data
      } catch (err) {
        this.error = err.response?.data?.detail || 'Failed to fetch transaction history'
        throw err
      } finally {
        this.loading = false
      }
    },

    async fetchTransactionCalendar(year, month) {
      this.loading = true
      this.error = null
      try {
        const response = await api.get('/reports/calendar', { params: { year, month } })
        this.transactionCalendar = response.data
        return response.data
      } catch (err) {
        this.error = err.response?.data?.detail || 'Failed to fetch transaction calendar'
        throw err
      } finally {
        this.loading = false
      }
    },
```

- [ ] **Step 5: Run to verify they pass**

Run: `cd frontend && npm run test -- --run src/stores/__tests__/queue.spec.js`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/stores/queue.js frontend/src/stores/__tests__/queue.spec.js
git commit -m "$(cat <<'EOF'
feat(reports): Pinia actions for transaction history + calendar

fetchTransactionHistory / fetchTransactionCalendar on the queue store,
with bracket-free array param serialization so FastAPI reads repeated
`kind`/`status` query params.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0128ZcebyPQToRp5dUTSgdCp
EOF
)"
```

---

## Task 6: Frontend route + sidebar link

**Files:**
- Modify: `frontend/src/router/index.js`
- Modify: `frontend/src/components/AdminLayout.vue`

**Interfaces:**
- Consumes: nothing from earlier frontend tasks.
- Produces: a named route `admin-reports` at path `/admin/reports`
  (admin-gated), reachable from an "History & Audit" sidebar link visible
  only to `role === 'admin'`.

- [ ] **Step 1: Add the route**

In `frontend/src/router/index.js`, inside the `/admin` route's `children`
array, after the `students` child object and before the `media` child object,
add:

```javascript
        {
          path: 'reports',
          name: 'admin-reports',
          component: () => import('../views/TransactionHistoryView.vue'),
          meta: { requiresAdmin: true }
        },
```

- [ ] **Step 2: Add the sidebar link**

In `frontend/src/components/AdminLayout.vue`, in the `<nav>` block, after the
`Students` `router-link` (the one `to="/admin/students"`) and before the
`Media & Announcements` link, add:

```html
          <router-link
            v-if="queueStore.currentUser?.role === 'admin'"
            to="/admin/reports"
            class="block px-4 py-2.5 rounded-xl text-sm font-medium transition-colors duration-150"
            :class="route.path === '/admin/reports' ? 'bg-bsu-primary text-white shadow-sm' : 'text-gray-600 hover:bg-bsu-primary/10 hover:text-bsu-primary-dark'"
          >
            History &amp; Audit
          </router-link>
```

- [ ] **Step 3: Create a placeholder view so the route resolves**

Create `frontend/src/views/TransactionHistoryView.vue` (replaced fully in
Task 7 — this is only so `npm run build` / the router import resolves now):

```vue
<template>
  <div>
    <h2 class="text-3xl font-bold text-bsu-ink">Transaction History &amp; Audit</h2>
  </div>
</template>

<script setup>
</script>
```

- [ ] **Step 4: Verify the frontend builds and tests pass**

Run: `cd frontend && npm run test && npm run build`
Expected: tests pass; build succeeds.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/router/index.js frontend/src/components/AdminLayout.vue frontend/src/views/TransactionHistoryView.vue
git commit -m "$(cat <<'EOF'
feat(reports): /admin/reports route + History & Audit sidebar link

Admin-only route and nav entry; view is a placeholder, filled in next.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0128ZcebyPQToRp5dUTSgdCp
EOF
)"
```

---

## Task 7: `TransactionHistoryView.vue` — calendar heatmap, busiest hours, filters, table, CSV

**Files:**
- Modify (full rewrite): `frontend/src/views/TransactionHistoryView.vue`

**Interfaces:**
- Consumes: `useQueueStore` — `fetchTransactionHistory(params)`,
  `fetchTransactionCalendar(year, month)`, `fetchQueues()`,
  `transactionHistory`, `transactionCalendar`, `queues`, `currentUser`.
- Consumes: `StatusBadge.vue` (`@/components/StatusBadge.vue`, prop `status`).
- Consumes: `date-fns` (`startOfMonth`, `endOfMonth`, `eachDayOfInterval`,
  `getDay`, `format`, `addMonths`, `subMonths`, `isSameDay`, `parseISO`).
- Consumes: `vue-chartjs` `Bar` + `chart.js` registration (same import
  shape as `DashboardView.vue`).
- Produces: nothing consumed by later tasks (final UI unit).

- [ ] **Step 1: Write the full view**

Replace the entire contents of
`frontend/src/views/TransactionHistoryView.vue` with:

```vue
<template>
  <div>
    <div class="mb-6">
      <h2 class="text-3xl font-bold text-bsu-ink">Transaction History &amp; Audit</h2>
      <p class="mt-2 text-gray-500">
        Past tickets and appointments, and a monthly view of when the registrar is busiest.
      </p>
    </div>

    <div v-if="error" class="bg-red-50 border border-red-100 rounded-2xl p-4 mb-6">
      <p class="text-sm text-red-700">{{ error }}</p>
    </div>

    <!-- Calendar + busiest hours -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
      <div class="panel overflow-hidden lg:col-span-2">
        <div class="panel-header flex items-center justify-between">
          <h3 class="text-lg font-semibold text-bsu-ink">Peak Transactions</h3>
          <div class="flex items-center gap-2">
            <button class="btn btn-sm btn-secondary" @click="shiftMonth(-1)">&larr;</button>
            <span class="text-sm font-medium text-bsu-ink w-32 text-center">
              {{ monthLabel }}
            </span>
            <button class="btn btn-sm btn-secondary" @click="shiftMonth(1)">&rarr;</button>
          </div>
        </div>
        <div class="p-6">
          <div class="grid grid-cols-7 gap-1 text-center text-xs font-semibold text-gray-400 mb-1">
            <div v-for="d in ['Sun','Mon','Tue','Wed','Thu','Fri','Sat']" :key="d">{{ d }}</div>
          </div>
          <div class="grid grid-cols-7 gap-1">
            <div v-for="n in leadingBlanks" :key="'b' + n"></div>
            <button
              v-for="cell in dayCells"
              :key="cell.iso"
              type="button"
              @click="selectDay(cell.iso)"
              class="aspect-square rounded-lg border text-left p-1.5 transition-colors"
              :class="[
                cell.intensity,
                selectedDay === cell.iso ? 'ring-2 ring-bsu-primary' : 'border-transparent',
                cell.isPeak ? 'outline outline-2 outline-bsu-gold' : '',
              ]"
            >
              <span class="text-[11px] font-semibold" :class="cell.count ? 'text-white' : 'text-gray-500'">
                {{ cell.day }}
              </span>
              <span v-if="cell.count" class="block text-[11px] font-bold text-white">{{ cell.count }}</span>
            </button>
          </div>
          <p class="mt-3 text-xs text-gray-500">
            <span v-if="calendar?.peak_day">
              Busiest day: <span class="font-semibold text-bsu-ink">{{ formatIso(calendar.peak_day) }}</span>
              ({{ calendar.peak_count }} transactions).
            </span>
            <span v-else>No transactions this month.</span>
            Click a day to filter the list below.
          </p>
        </div>
      </div>

      <div class="panel overflow-hidden">
        <div class="panel-header">
          <h3 class="text-lg font-semibold text-bsu-ink">Busiest Hours</h3>
        </div>
        <div class="p-6">
          <div v-if="hasHourData" class="h-64">
            <Bar :data="hourChartData" :options="hourChartOptions" />
          </div>
          <p v-else class="text-center text-gray-500 py-8">No data this month</p>
        </div>
      </div>
    </div>

    <!-- Filters -->
    <div class="panel p-4 mb-4">
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <label class="text-sm">
          <span class="block text-gray-600 mb-1">From</span>
          <input v-model="filters.date_from" type="date" class="field" />
        </label>
        <label class="text-sm">
          <span class="block text-gray-600 mb-1">To</span>
          <input v-model="filters.date_to" type="date" class="field" />
        </label>
        <label class="text-sm">
          <span class="block text-gray-600 mb-1">Queue</span>
          <select v-model="filters.queue_id" class="field">
            <option :value="null">All queues</option>
            <option v-for="q in queueStore.queues" :key="q.id" :value="q.id">{{ q.name }}</option>
          </select>
        </label>
        <label class="text-sm">
          <span class="block text-gray-600 mb-1">Student number</span>
          <input v-model="filters.student_number" maxlength="10" inputmode="numeric" placeholder="10 digits" class="field" />
        </label>
      </div>

      <div class="flex flex-wrap gap-4 mt-3 text-sm">
        <span class="text-gray-600">Type:</span>
        <label class="flex items-center gap-1">
          <input type="checkbox" value="ticket" v-model="filters.kind" /> Tickets
        </label>
        <label class="flex items-center gap-1">
          <input type="checkbox" value="appointment" v-model="filters.kind" /> Appointments
        </label>
      </div>

      <div class="flex flex-wrap gap-x-4 gap-y-1 mt-3 text-sm">
        <span class="text-gray-600">Status:</span>
        <label v-for="s in ALL_STATUSES" :key="s" class="flex items-center gap-1">
          <input type="checkbox" :value="s" v-model="filters.status" /> {{ s.replace('_', ' ') }}
        </label>
        <span class="text-gray-400">(none checked = attended only)</span>
      </div>

      <div class="flex gap-3 mt-4">
        <button class="btn btn-primary btn-sm" @click="applyFilters">Apply</button>
        <button class="btn btn-secondary btn-sm" @click="resetFilters">Reset</button>
        <button class="btn btn-secondary btn-sm ml-auto" @click="downloadCsv">Download CSV</button>
      </div>
    </div>

    <!-- Table -->
    <div class="panel overflow-hidden">
      <div class="overflow-x-auto">
        <table class="min-w-full text-sm">
          <thead class="bg-bsu-surface text-gray-500 text-xs uppercase tracking-wide">
            <tr>
              <th class="px-4 py-3 text-left">Reference</th>
              <th class="px-4 py-3 text-left">Type</th>
              <th class="px-4 py-3 text-left">Student</th>
              <th class="px-4 py-3 text-left">Service</th>
              <th class="px-4 py-3 text-left">Queue</th>
              <th class="px-4 py-3 text-left">Status</th>
              <th class="px-4 py-3 text-left">Priority</th>
              <th class="px-4 py-3 text-left">Created</th>
              <th class="px-4 py-3 text-left">Occurred</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-100">
            <tr v-for="row in history.items" :key="row.kind + '-' + row.id">
              <td class="px-4 py-3 font-medium text-bsu-ink">{{ row.reference }}</td>
              <td class="px-4 py-3 capitalize">{{ row.kind }}</td>
              <td class="px-4 py-3">
                <div class="text-bsu-ink">{{ row.student_name }}</div>
                <div class="text-xs text-gray-400">{{ row.student_number }}</div>
              </td>
              <td class="px-4 py-3">{{ row.service }}</td>
              <td class="px-4 py-3">{{ row.queue_name }}</td>
              <td class="px-4 py-3"><StatusBadge :status="row.status" /></td>
              <td class="px-4 py-3 capitalize">{{ row.priority || '—' }}</td>
              <td class="px-4 py-3 text-gray-500">{{ formatDateTime(row.created_at) }}</td>
              <td class="px-4 py-3 text-gray-500">{{ row.occurred_at ? formatDateTime(row.occurred_at) : '—' }}</td>
            </tr>
            <tr v-if="!history.items.length">
              <td colspan="9" class="px-4 py-10 text-center text-gray-500">No transactions match these filters.</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="flex items-center justify-between px-4 py-3 border-t border-gray-100 text-sm text-gray-500">
        <span>
          <template v-if="history.total">
            Showing {{ history.skip + 1 }}–{{ history.skip + history.items.length }} of {{ history.total }}
          </template>
          <template v-else>No results</template>
        </span>
        <div class="flex gap-2">
          <button class="btn btn-sm btn-secondary" :disabled="history.skip === 0" @click="changePage(-1)">Prev</button>
          <button class="btn btn-sm btn-secondary" :disabled="history.skip + history.limit >= history.total" @click="changePage(1)">Next</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import {
  addMonths, eachDayOfInterval, endOfMonth, format, getDay, startOfMonth, subMonths,
} from 'date-fns'
import { Bar } from 'vue-chartjs'
import {
  Chart as ChartJS, BarElement, CategoryScale, LinearScale, Tooltip, Legend,
} from 'chart.js'
import { useQueueStore } from '@/stores/queue'
import StatusBadge from '@/components/StatusBadge.vue'

ChartJS.register(BarElement, CategoryScale, LinearScale, Tooltip, Legend)

const queueStore = useQueueStore()
const error = ref('')

const ALL_STATUSES = [
  'waiting', 'serving', 'completed', 'cancelled', 'no_show',
  'booked', 'checked_in', 'expired',
]

const PAGE_SIZE = 50

const today = new Date()
const isoOf = (d) => format(d, 'yyyy-MM-dd')

const filters = reactive({
  date_from: isoOf(subMonths(today, 1)),
  date_to: isoOf(today),
  kind: ['ticket', 'appointment'],
  status: [],
  queue_id: null,
  student_number: '',
})

const calendarMonth = ref(startOfMonth(today))
const selectedDay = ref(null)

const history = computed(() => queueStore.transactionHistory)
const calendar = computed(() => queueStore.transactionCalendar)

const monthLabel = computed(() => format(calendarMonth.value, 'MMMM yyyy'))
const leadingBlanks = computed(() => getDay(startOfMonth(calendarMonth.value)))

const dayCells = computed(() => {
  const days = eachDayOfInterval({
    start: startOfMonth(calendarMonth.value),
    end: endOfMonth(calendarMonth.value),
  })
  const byIso = {}
  let max = 0
  for (const d of calendar.value?.days ?? []) {
    byIso[d.date] = d.total
    if (d.total > max) max = d.total
  }
  const peakIso = calendar.value?.peak_day ?? null
  return days.map((d) => {
    const iso = isoOf(d)
    const count = byIso[iso] ?? 0
    return {
      iso,
      day: format(d, 'd'),
      count,
      isPeak: !!count && iso === peakIso,
      intensity: intensityClass(count, max),
    }
  })
})

function intensityClass(count, max) {
  if (!count) return 'bg-gray-50'
  const ratio = max ? count / max : 0
  if (ratio > 0.8) return 'bg-bsu-primary'
  if (ratio > 0.6) return 'bg-bsu-primary/80'
  if (ratio > 0.4) return 'bg-bsu-primary/60'
  if (ratio > 0.2) return 'bg-bsu-primary/40'
  return 'bg-bsu-primary/25'
}

const hasHourData = computed(() => (calendar.value?.busiest_hours ?? []).some((n) => n > 0))
const hourChartData = computed(() => ({
  labels: Array.from({ length: 24 }, (_, h) => `${h}`),
  datasets: [{
    label: 'Transactions',
    data: calendar.value?.busiest_hours ?? [],
    backgroundColor: '#E85D8E',
    borderRadius: 4,
  }],
}))
const hourChartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { display: false } },
  scales: {
    y: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: '#F1F1F1' } },
    x: { grid: { display: false } },
  },
}

function buildParams(extra = {}) {
  const p = {
    date_from: filters.date_from,
    date_to: filters.date_to,
    kind: filters.kind,
    ...extra,
  }
  if (filters.status.length) p.status = filters.status
  if (filters.queue_id) p.queue_id = filters.queue_id
  if (/^\d{10}$/.test(filters.student_number)) p.student_number = filters.student_number
  return p
}

async function loadHistory(skip = 0) {
  error.value = ''
  try {
    await queueStore.fetchTransactionHistory(buildParams({ skip, limit: PAGE_SIZE }))
  } catch (err) {
    error.value = err.response?.data?.detail || 'Failed to load transaction history.'
  }
}

async function loadCalendar() {
  try {
    await queueStore.fetchTransactionCalendar(
      calendarMonth.value.getFullYear(), calendarMonth.value.getMonth() + 1,
    )
  } catch (err) {
    error.value = err.response?.data?.detail || 'Failed to load the calendar.'
  }
}

function shiftMonth(delta) {
  calendarMonth.value = delta < 0
    ? subMonths(calendarMonth.value, 1)
    : addMonths(calendarMonth.value, 1)
  loadCalendar()
}

function selectDay(iso) {
  selectedDay.value = iso
  filters.date_from = iso
  filters.date_to = iso
  loadHistory(0)
}

function applyFilters() {
  selectedDay.value = null
  loadHistory(0)
}

function resetFilters() {
  filters.date_from = isoOf(subMonths(today, 1))
  filters.date_to = isoOf(today)
  filters.kind = ['ticket', 'appointment']
  filters.status = []
  filters.queue_id = null
  filters.student_number = ''
  selectedDay.value = null
  loadHistory(0)
}

function changePage(dir) {
  const next = history.value.skip + dir * history.value.limit
  if (next < 0) return
  loadHistory(next)
}

function downloadCsv() {
  const usp = new URLSearchParams()
  usp.set('date_from', filters.date_from)
  usp.set('date_to', filters.date_to)
  for (const k of filters.kind) usp.append('kind', k)
  for (const s of filters.status) usp.append('status', s)
  if (filters.queue_id) usp.set('queue_id', filters.queue_id)
  if (/^\d{10}$/.test(filters.student_number)) usp.set('student_number', filters.student_number)
  window.open(`/api/reports/transactions.csv?${usp.toString()}`, '_blank')
}

function formatDateTime(value) {
  return format(new Date(value), 'MMM d, yyyy • h:mm a')
}
function formatIso(value) {
  return format(new Date(value + 'T00:00:00'), 'MMM d, yyyy')
}

onMounted(async () => {
  if (!queueStore.queues.length) {
    queueStore.fetchQueues().catch(() => {})
  }
  await Promise.all([loadCalendar(), loadHistory(0)])
})
</script>
```

- [ ] **Step 2: Run the frontend tests + build**

Run: `cd frontend && npm run test && npm run build`
Expected: tests pass; build succeeds with no errors.

- [ ] **Step 3: Manual verification with the run skill**

Invoke the `run-bsu-registrar-queue` skill to start backend + frontend.
Log in as an admin, open **History & Audit** in the sidebar. Confirm:
- the calendar renders the current month; days with data are shaded and show
  a count; the peak day is outlined.
- the busiest-hours bar chart renders (or shows "No data this month").
- clicking a day sets both date filters to that day and reloads the table.
- the status/kind/queue/student filters + Apply + Reset work.
- Prev/Next paginate; the "Showing X–Y of N" line is correct.
- "Download CSV" opens a CSV download.
- logging in as a **registrar** shows no "History & Audit" link, and visiting
  `/admin/reports` directly redirects to the dashboard.
Save screenshots of the calendar + table to the skill's screenshots folder.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/TransactionHistoryView.vue
git commit -m "$(cat <<'EOF'
feat(reports): TransactionHistoryView - heatmap, busiest hours, table, CSV

Month heatmap (date-fns grid, 5 intensity steps, peak day outlined,
click-to-filter), busiest-hours bar chart, filter row (date range, kind,
status, queue, student number), paginated table, and a CSV download.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0128ZcebyPQToRp5dUTSgdCp
EOF
)"
```

---

## Task 8: End-to-end verification + final suite run

**Files:** none (verification only; may touch `CLAUDE.md` if a gap is found).

- [ ] **Step 1: Full backend suite**

Run: `cd backend && python -m pytest -q`
Expected: all pass (including the pre-existing suite).

- [ ] **Step 2: Full frontend suite + production build**

Run: `cd frontend && npm run test && npm run build`
Expected: all pass; build clean.

- [ ] **Step 3: Lint check for accidental raw SQL**

Run: `cd backend && git grep -n "text(" -- app/services/report_service.py app/api/reports.py`
Expected: no matches (ORM-only rule holds).

- [ ] **Step 4: `pip-audit` / `npm audit` unaffected**

Run: `cd backend && pip-audit --ignore-vuln PYSEC-2026-1325` and
`cd frontend && npm audit --omit=dev --audit-level=high`
Expected: same result as before this branch (no new advisories — no deps added).

- [ ] **Step 5: Manual admin walkthrough (if not already done in Task 7)**

Use the `run-bsu-registrar-queue` skill: seed a few completed tickets across
different days (through the counter flow or a quick script), then confirm the
calendar heatmap, peak-day outline, busiest-hours chart, day-click filtering,
pagination, and CSV export all reflect the seeded data.

- [ ] **Step 6: Push the branch and open a PR**

```bash
git push -u origin feat/transaction-history-audit
gh pr create --base master --title "feat: admin transaction history + peak-transactions audit calendar" --body "$(cat <<'EOF'
Implements docs/superpowers/specs/2026-09-03-transaction-history-audit-design.md.

- New admin-only reporting module: `ReportService` + `/api/reports/*`
  (`transactions`, `calendar`, `transactions.csv`).
- Merged tickets+appointments history with date/status/kind/queue/student/
  priority filters and pagination; default view = attended rows.
- Monthly peak-volume heatmap + busiest-hours breakdown, campus-tz bucketed.
- CSV audit export, capped at 10k rows, emits a `report.exported` security event.
- New `TransactionHistoryView.vue` at `/admin/reports`.
- No schema change, no migration. New `CAMPUS_TIMEZONE` setting (default Asia/Manila).

Tests: `backend/tests/test_report_service.py`, `backend/tests/test_reports_api.py`,
new `reports actions` block in `frontend/src/stores/__tests__/queue.spec.js`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Self-Review

**1. Spec coverage:**

| Spec item | Task |
|---|---|
| `TransactionRow` normalized shape (tickets + appointments) | 1 |
| `get_transactions` filters (date/kind/status/queue/student/priority), pagination | 1 |
| Attended-status default with override | 1 (tested), 3 (wired) |
| `get_calendar` per-day + peak + busiest-hours, campus-tz bucketing | 2 |
| `CAMPUS_TIMEZONE` setting + `.env.example` | 1 |
| `/api/reports/transactions` admin-gated, bounded params | 3 |
| `/api/reports/calendar` admin-gated | 3 |
| `/api/reports/transactions.csv` + 10k cap + `report.exported` audit event | 2 (cap), 4 (endpoint + event) |
| CLAUDE.md audit-events + endpoint table | 4 |
| Route `/admin/reports` (`requiresAdmin`) + sidebar link (admin-only) | 6 |
| Pinia `fetchTransactionHistory` / `fetchTransactionCalendar` + state | 5 |
| Month heatmap (date-fns, 5 steps, click-to-filter), peak badge | 7 |
| Busiest-hours bar chart | 7 |
| Filter row, paginated table, Download CSV | 7 |
| Backend tests (service + API, incl. tz edge, 403/401, CSV) | 1–4 |
| Frontend store tests | 5 |
| Manual view verification | 7, 8 |

No gaps.

**2. Placeholder scan:** No "TBD"/"handle edge cases"/"similar to Task N".
Every code step has literal code. The Task 6 placeholder view is explicitly
labelled as replaced-in-full by Task 7 and its code is given.

**3. Type consistency:**
- `ReportService` method signatures identical between the Interfaces blocks
  and the code in Tasks 1–2.
- `TransactionRow` field names used identically in the service (Task 1),
  CSV writer (Task 4, `_CSV_COLUMNS` matches the `writerow` order and the
  model fields), and the Vue table (Task 7: `row.reference`, `row.kind`,
  `row.student_name`, `row.student_number`, `row.service`, `row.queue_name`,
  `row.status`, `row.priority`, `row.created_at`, `row.occurred_at`).
- `CalendarSummary` fields (`days`, `peak_day`, `peak_count`, `month_total`,
  `busiest_hours`) used consistently in Task 2 and Task 7
  (`calendar.value?.days`, `.peak_day`, `.peak_count`, `.busiest_hours`).
- Store action names (`fetchTransactionHistory`, `fetchTransactionCalendar`)
  and state (`transactionHistory`, `transactionCalendar`) identical across
  Tasks 5 and 7.
- Query-param names (`date_from`, `date_to`, `kind`, `status`, `queue_id`,
  `student_number`, `priority`, `skip`, `limit`) identical between the API
  (Task 3/4), the store's `buildParams` and CSV builder (Task 7).
- `intensityClass(count, max)` defined once in Task 7 and used once.

No inconsistencies found.
