"""
Campus wall-clock time (settings.CAMPUS_TIMEZONE, Asia/Manila).

The production container runs on UTC, so date.today() / datetime.now() are
8 hours behind the registrar's day: "today" was still yesterday until 8am
Manila, and slot times (stored as plain campus-local Date + Time) were
compared against UTC, so check-in windows and appointment expiry were off by
8 hours. Anything that means "the campus's today/now" goes through here.

Call these through the module (`campus_time.campus_now()`) so tests can
monkeypatch campus_now to pin the clock.
"""
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from .config import settings


def campus_tz() -> ZoneInfo:
    return ZoneInfo(settings.CAMPUS_TIMEZONE)


def campus_now() -> datetime:
    """Timezone-aware current time on campus."""
    return datetime.now(campus_tz())


def campus_today() -> date:
    return campus_now().date()


def campus_today_start() -> datetime:
    """Timezone-aware midnight at the start of today on campus."""
    return datetime.combine(campus_today(), time.min, tzinfo=campus_tz())


def campus_datetime(day: date, at: time) -> datetime:
    """A campus-local date + time (e.g. an appointment slot) as an aware datetime."""
    return datetime.combine(day, at, tzinfo=campus_tz())
