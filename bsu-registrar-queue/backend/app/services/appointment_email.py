"""
Student appointment emails: a confirmation right after booking and a
reminder on the morning of the appointment, both carrying the check-in QR.

The reminder batch is triggered by GitHub Actions calling
POST /api/internal/appointment-reminders (Render's free tier sleeps when
idle, so a Celery beat schedule inside it can't be relied on overnight).

Never logs a student's name or address - subjects carry only the
reference code, because email_sender logs subjects.
"""
import io
import logging
from datetime import timedelta
from decimal import Decimal
from html import escape
from typing import Optional

import segno
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..core import campus_time
from ..core.config import settings
from ..core.database import SessionLocal, engine
from ..db_models import AppointmentDB, AppointmentDBStatus, DocumentDB
from . import email_sender
from .appointment_service import GRACE_MINUTES_AFTER, GRACE_MINUTES_BEFORE, REMINDER_MAX_ATTEMPTS

logger = logging.getLogger("bsu.email")

QR_CID = "qr@bsu"
# Arbitrary constant naming "the reminder batch" for pg_try_advisory_xact_lock.
_REMINDER_LOCK_KEY = 72_610_013
_ACCENT = "#E85D8E"


# ---- formatting ---------------------------------------------------------

def _clock(t) -> str:
    return f"{t.hour % 12 or 12}:{t.minute:02d} {'AM' if t.hour < 12 else 'PM'}"


def _long_date(d) -> str:
    return f"{d:%A}, {d:%B} {d.day}, {d.year}"


def _peso(amount: Decimal) -> str:
    return f"₱{amount:,.2f}"


def _fee_label(fee: Optional[Decimal]) -> str:
    if fee is None:
        return ""
    return "Free" if fee == 0 else _peso(fee)


def _total_label(documents) -> str:
    """Same rule as the kiosk (frontend services/documentFees.js)."""
    fees = [d.fee for d in documents if d.fee is not None]
    if not fees:
        return ""
    label = "Total of listed fees" if len(fees) < len(documents) else "Total"
    return f"{label} {_peso(sum(fees, Decimal('0')))}"


def qr_png(token: str) -> bytes:
    """The check-in QR - encodes the same qr_token string the booking page does."""
    buf = io.BytesIO()
    segno.make(token, error="m").save(buf, kind="png", scale=8, border=2)
    return buf.getvalue()


# ---- the email ------------------------------------------------------------

def build_appointment_email(db: Session, appt: AppointmentDB, kind: str) -> dict:
    """kwargs for email_sender.send_email. kind: "confirmation" | "reminder"."""
    student, queue = appt.student, appt.queue
    start, end = _clock(appt.slot_start_time), _clock(appt.slot_end_time)
    slot_start = campus_time.campus_datetime(appt.appointment_date, appt.slot_start_time)
    slot_end = campus_time.campus_datetime(appt.appointment_date, appt.slot_end_time)
    window = (f"{_clock((slot_start - timedelta(minutes=GRACE_MINUTES_BEFORE)).time())} until "
              f"{_clock((slot_end + timedelta(minutes=GRACE_MINUTES_AFTER)).time())}")
    when = _long_date(appt.appointment_date)
    place = f"Registrar's Office, {settings.CAMPUS_NAME}"

    if kind == "reminder":
        subject = f"Reminder: your registrar appointment is today at {start} — {appt.reference_code}"
        intro = "This is a reminder of your registrar appointment today."
    else:
        subject = f"Your registrar appointment is booked — {appt.reference_code}"
        intro = "Your registrar appointment is booked. Keep this email - you'll show the QR code below at the counter."

    documents = list(appt.documents)
    requirements = []
    if documents:
        notes = dict(db.query(DocumentDB.id, DocumentDB.requirements).filter(
            DocumentDB.id.in_([d.document_id for d in documents])).all())
        requirements = [(d.name, notes.get(d.document_id)) for d in documents if notes.get(d.document_id)]

    # ---- plain text ----
    lines = [
        f"Hello {student.first_name},",
        "",
        intro,
        "",
        f"Service: {queue.name}",
        f"Date: {when}",
        f"Time: {start} – {end}",
        f"Check in: from {window}",
        f"Reference code: {appt.reference_code}",
        f"Place: {place}",
    ]
    if documents:
        lines += ["", "Requested documents:"]
        lines += [f"  - {d.name}" + (f" ({_fee_label(d.fee)})" if _fee_label(d.fee) else "") for d in documents]
        if _total_label(documents):
            lines.append(_total_label(documents))
        if requirements:
            lines += ["", "What to bring:"] + [f"  - {name}: {note}" for name, note in requirements]
    lines += ["", "Show the QR code in this email (or tell the counter your reference code) when you check in.",
              "", "This is an automated message - replies are not read."]
    text_body = "\n".join(lines)

    # ---- HTML (tables + inline styles: mail clients ignore <style>) ----
    e = escape

    def row(label, value):
        return (f'<tr><td style="padding:4px 12px 4px 0;color:#6b7280;white-space:nowrap;vertical-align:top">{e(label)}</td>'
                f'<td style="padding:4px 0;color:#2d2d2d;font-weight:600">{e(value)}</td></tr>')

    docs_html = ""
    if documents:
        items = "".join(
            f'<tr><td style="padding:6px 0;border-top:1px solid #f1f1f1">{e(d.name)}</td>'
            f'<td style="padding:6px 0 6px 12px;border-top:1px solid #f1f1f1;text-align:right;white-space:nowrap">{e(_fee_label(d.fee))}</td></tr>'
            for d in documents)
        total = (f'<p style="margin:6px 0 0;text-align:right;font-weight:700">{e(_total_label(documents))}</p>'
                 if _total_label(documents) else "")
        bring = ""
        if requirements:
            bring = ('<p style="margin:16px 0 4px;font-weight:700">What to bring</p><ul style="margin:0;padding-left:20px">'
                     + "".join(f"<li><strong>{e(name)}:</strong> {e(note)}</li>" for name, note in requirements)
                     + "</ul>")
        docs_html = (f'<p style="margin:20px 0 4px;font-weight:700;color:{_ACCENT}">Requested documents</p>'
                     f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="font-size:14px">{items}</table>'
                     f'{total}{bring}')

    html_body = f"""<!doctype html>
<html><body style="margin:0;padding:0;background:#f8f9fa">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f8f9fa;padding:24px 12px">
<tr><td align="center">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;background:#ffffff;border-radius:16px;padding:24px;font-family:Arial,Helvetica,sans-serif;font-size:15px;color:#2d2d2d">
<tr><td>
<p style="margin:0 0 4px;font-size:12px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:{_ACCENT}">{e(settings.CAMPUS_NAME)} Registrar</p>
<h1 style="margin:0 0 12px;font-size:20px">{"Appointment reminder" if kind == "reminder" else "Appointment booked"}</h1>
<p style="margin:0 0 4px">Hello {e(student.first_name)},</p>
<p style="margin:0 0 16px">{e(intro)}</p>
<table role="presentation" cellpadding="0" cellspacing="0" style="font-size:14px">
{row("Service", queue.name)}{row("Date", when)}{row("Time", f"{start} – {end}")}{row("Check in", f"from {window}")}{row("Place", place)}
</table>
<div style="text-align:center;margin:20px 0 8px">
<img src="cid:{QR_CID}" width="220" height="220" alt="Check-in QR code" style="display:block;margin:0 auto;border:1px solid #e5e7eb;border-radius:12px">
<p style="margin:8px 0 0;font-size:22px;font-weight:700;letter-spacing:1px">{e(appt.reference_code)}</p>
<p style="margin:4px 0 0;font-size:12px;color:#6b7280">Show this QR code (or the code above) at the registrar counter.</p>
</div>
{docs_html}
<p style="margin:24px 0 0;font-size:12px;color:#9ca3af">This is an automated message - replies are not read.</p>
</td></tr></table>
</td></tr></table>
</body></html>"""

    return dict(to=student.email, subject=subject, text=text_body, html=html_body,
                inline_images=[(QR_CID, qr_png(appt.qr_token))])


# ---- confirmation -------------------------------------------------------

def send_confirmation(appointment_id: int) -> bool:
    """Background-task entry point (after the booking/resend response).
    Opens its own session - the request's is closed by then. Never raises."""
    db = SessionLocal()
    try:
        appt = db.get(AppointmentDB, appointment_id)
        if not appt or appt.status != AppointmentDBStatus.BOOKED or not appt.student.email:
            return False
        sent = email_sender.send_email(**build_appointment_email(db, appt, "confirmation"))
        if sent:
            appt.confirmation_sent_at = campus_time.campus_now()
            db.commit()
        return sent
    except Exception:
        logger.exception("Appointment confirmation for appointment#%s failed", appointment_id)
        return False
    finally:
        db.close()


# ---- reminder batch -----------------------------------------------------

def send_due_reminders(db: Session) -> dict:
    """Send today's not-yet-sent reminders. Counts only in the result.

    One run at a time: a transaction-scoped advisory lock is held on a
    dedicated connection for the whole run (transaction-scoped so it also
    works through Supabase's transaction-mode pooler). A second, overlapping
    run (a retry run, a manual run) returns "already_running" instead of
    emailing anyone twice."""
    with engine.connect() as lock_conn:
        with lock_conn.begin():
            got_lock = lock_conn.execute(
                text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": _REMINDER_LOCK_KEY}
            ).scalar()
            if not got_lock:
                return {"status": "already_running", "due": 0, "sent": 0, "failed": 0}
            return _send_due_reminders_locked(db)


def _send_due_reminders_locked(db: Session) -> dict:
    now = campus_time.campus_now()
    candidates = db.query(AppointmentDB).filter(
        AppointmentDB.status == AppointmentDBStatus.BOOKED,
        AppointmentDB.appointment_date == campus_time.campus_today(),
        AppointmentDB.reminder_sent_at.is_(None),
        AppointmentDB.reminder_attempts < REMINDER_MAX_ATTEMPTS,
    ).order_by(AppointmentDB.slot_start_time, AppointmentDB.id).all()
    due = [a for a in candidates
           if campus_time.campus_datetime(a.appointment_date, a.slot_end_time) > now]

    sent = failed = 0
    for appt in due:
        # Count the attempt before sending, so a crash mid-send can't retry forever.
        claimed = db.query(AppointmentDB).filter(
            AppointmentDB.id == appt.id,
            AppointmentDB.reminder_sent_at.is_(None),
            AppointmentDB.reminder_attempts < REMINDER_MAX_ATTEMPTS,
        ).update({"reminder_attempts": AppointmentDB.reminder_attempts + 1},
                 synchronize_session=False)
        db.commit()
        if not claimed:
            continue
        db.refresh(appt)
        try:
            ok = bool(appt.student.email) and email_sender.send_email(
                **build_appointment_email(db, appt, "reminder"))
        except Exception:
            logger.exception("Building the reminder for appointment#%s failed", appt.id)
            ok = False
        if ok:
            appt.reminder_sent_at = campus_time.campus_now()
            db.commit()
            sent += 1
        else:
            failed += 1
    return {"status": "ok", "due": len(due), "sent": sent, "failed": failed}
