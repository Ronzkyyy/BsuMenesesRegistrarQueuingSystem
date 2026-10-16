"""
Machine-to-machine endpoints - called by scheduled jobs, not people.

POST /internal/appointment-reminders is called by the GitHub Actions
schedule (.github/workflows/appointment-reminders.yml) at 2:00, 3:00 and 4:00 AM
Manila. Render's free tier sleeps when idle, so this request is also what
wakes the server; a Celery beat schedule inside it can't be relied on.
"""
import hmac
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from ..core.audit import log_security_event
from ..core.config import settings
from ..core.database import get_db
from ..core.limiter import limiter
from ..services import appointment_email

router = APIRouter()


@router.post("/appointment-reminders")
@limiter.limit("6/hour")
def run_appointment_reminders(
    request: Request,
    x_cron_secret: Optional[str] = Header(default=None, max_length=256),
    db: Session = Depends(get_db),
):
    """Send today's appointment reminders (secret-gated, no user session).
    Idempotent: a reminder already sent is never sent again."""
    if not settings.CRON_SECRET:
        # Not configured: behave as if the endpoint doesn't exist.
        raise HTTPException(status_code=404, detail="Not Found")
    if not x_cron_secret or not hmac.compare_digest(
            x_cron_secret.encode(), settings.CRON_SECRET.encode()):
        log_security_event("appointment.reminders_run", outcome="denied",
                           request=request, actor="anonymous")
        raise HTTPException(status_code=403, detail="Forbidden")

    result = appointment_email.send_due_reminders(db)
    log_security_event(
        "appointment.reminders_run",
        outcome="success" if result["status"] == "ok" else "skipped",
        request=request, actor="cron",
        detail=f"status={result['status']}, due={result['due']}, sent={result['sent']}, failed={result['failed']}",
    )
    return result
