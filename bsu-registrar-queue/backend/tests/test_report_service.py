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
