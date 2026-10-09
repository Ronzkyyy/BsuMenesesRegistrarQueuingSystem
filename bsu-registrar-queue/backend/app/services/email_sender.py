"""
Outgoing email - the one place the app sends mail from.

Two backends, picked by settings.EMAIL_BACKEND:

- "gmail": the Gmail API over HTTPS. Render's free tier blocks outbound SMTP
  (ports 25/465/587), so SMTP isn't an option there. A long-lived OAuth
  refresh token (from `python -m app.cli gmail-auth`) is exchanged for a
  short-lived access token on every send.
- "console" (default): log instead of sending. The body - which carries the
  one-time link - is logged only when DEBUG=True.

send_email() never raises: it runs as a background task after the response
has gone out, so a delivery failure is logged, not shown to the requester
(who must not learn whether the address exists anyway).
"""
import base64
import logging
from email.message import EmailMessage

import httpx

from ..core.config import settings

logger = logging.getLogger("bsu.email")

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GMAIL_SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"
_TIMEOUT = httpx.Timeout(10.0)


class EmailNotConfigured(RuntimeError):
    pass


def build_message(to: str, subject: str, text: str, html: str | None = None) -> EmailMessage:
    msg = EmailMessage()
    msg["To"] = to
    msg["From"] = settings.EMAIL_FROM
    msg["Subject"] = subject
    msg.set_content(text)
    if html:
        msg.add_alternative(html, subtype="html")
    return msg


def _gmail_access_token(client: httpx.Client) -> str:
    if not (settings.GMAIL_CLIENT_ID and settings.GMAIL_CLIENT_SECRET and settings.GMAIL_REFRESH_TOKEN):
        raise EmailNotConfigured("GMAIL_CLIENT_ID / GMAIL_CLIENT_SECRET / GMAIL_REFRESH_TOKEN not set")
    resp = client.post(GOOGLE_TOKEN_URL, data={
        "client_id": settings.GMAIL_CLIENT_ID,
        "client_secret": settings.GMAIL_CLIENT_SECRET,
        "refresh_token": settings.GMAIL_REFRESH_TOKEN,
        "grant_type": "refresh_token",
    })
    if resp.status_code != 200:
        # Google's error body names the problem (e.g. invalid_grant = the
        # refresh token was revoked or expired) and holds no secret.
        raise RuntimeError(f"Google token refresh failed ({resp.status_code}): {resp.text[:200]}")
    return resp.json()["access_token"]


def _send_gmail(msg: EmailMessage) -> None:
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")
    with httpx.Client(timeout=_TIMEOUT) as client:
        token = _gmail_access_token(client)
        resp = client.post(
            GMAIL_SEND_URL,
            headers={"Authorization": f"Bearer {token}"},
            json={"raw": raw},
        )
    if resp.status_code not in (200, 202):
        raise RuntimeError(f"Gmail send failed ({resp.status_code}): {resp.text[:200]}")


def send_email(to: str, subject: str, text: str, html: str | None = None) -> bool:
    """Send one email; True if it was handed to the mail provider."""
    backend = settings.EMAIL_BACKEND.lower()
    if backend == "console":
        if settings.DEBUG:
            logger.warning("EMAIL (console backend, not sent)\nTo: %s\nSubject: %s\n\n%s", to, subject, text)
        else:
            logger.error(
                "EMAIL_BACKEND is 'console' outside DEBUG - '%s' was NOT sent. "
                "Configure the Gmail backend.", subject,
            )
        return False

    if backend != "gmail":
        logger.error("Unknown EMAIL_BACKEND %r - '%s' was NOT sent.", settings.EMAIL_BACKEND, subject)
        return False

    try:
        _send_gmail(build_message(to, subject, text, html))
    except Exception:
        logger.exception("Sending '%s' failed", subject)
        return False
    logger.info("Sent '%s'", subject)
    return True
