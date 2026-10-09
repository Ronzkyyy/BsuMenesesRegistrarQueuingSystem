"""
Staff email addresses: verification links and self-service password reset.

Tokens are 256-bit random strings handed out once in an email link; only
their SHA-256 is stored. Each is single-use and short-lived, and issuing a
new one of the same purpose retires the older ones for that account.
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from html import escape
from typing import Optional

from sqlalchemy.orm import Session

from ..core.config import settings
from ..db_models import EmailTokenDB, EmailTokenPurpose, UserDB
from . import email_sender
from .student_service import validate_email_deliverable

INVALID_LINK_DETAIL = "This link is invalid or has expired. Please request a new one."


def normalize_email(email: str) -> str:
    return email.strip().lower()


def check_email_available(db: Session, email: str, *, exclude_user_id: Optional[int] = None) -> str:
    """Normalize, confirm the domain takes mail, and confirm no other account
    uses it. Raises ValueError with a user-facing message."""
    email = normalize_email(email)
    validate_email_deliverable(email)
    query = db.query(UserDB).filter(UserDB.email == email)
    if exclude_user_id is not None:
        query = query.filter(UserDB.id != exclude_user_id)
    if query.first():
        raise ValueError("That email is already used by another account.")
    return email


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _retire_open_tokens(db: Session, user: UserDB, purpose: EmailTokenPurpose) -> None:
    db.query(EmailTokenDB).filter(
        EmailTokenDB.user_id == user.id,
        EmailTokenDB.purpose == purpose,
        EmailTokenDB.used_at.is_(None),
    ).update({EmailTokenDB.used_at: _now()}, synchronize_session=False)


def issue_token(db: Session, user: UserDB, purpose: EmailTokenPurpose, lifetime: timedelta) -> str:
    """Create a new one-time token (retiring older open ones). Caller commits."""
    _retire_open_tokens(db, user, purpose)
    token = secrets.token_urlsafe(32)
    db.add(EmailTokenDB(
        user_id=user.id,
        purpose=purpose,
        token_hash=_hash(token),
        email=user.email,
        expires_at=_now() + lifetime,
    ))
    return token


def consume_token(db: Session, token: str, purpose: EmailTokenPurpose) -> Optional[UserDB]:
    """Mark a valid token used and return its account, or None if the token
    is unknown, used, expired, for another purpose, or was sent to an address
    the account no longer has. Caller commits."""
    row = db.query(EmailTokenDB).filter(EmailTokenDB.token_hash == _hash(token)).first()
    if row is None or row.purpose != purpose or row.used_at is not None:
        return None
    if _aware(row.expires_at) <= _now():
        return None
    user = db.query(UserDB).filter(UserDB.id == row.user_id).first()
    if user is None or not user.is_active or user.email != row.email:
        return None
    row.used_at = _now()
    return user


def recent_reset_count(db: Session, user: UserDB) -> int:
    since = _now() - timedelta(minutes=settings.PASSWORD_RESET_TOKEN_MINUTES)
    return db.query(EmailTokenDB).filter(
        EmailTokenDB.user_id == user.id,
        EmailTokenDB.purpose == EmailTokenPurpose.RESET_PASSWORD,
        EmailTokenDB.created_at >= since,
    ).count()


def _link(path: str, token: str) -> str:
    # Token in the URL fragment, not the query string: browsers never send
    # the fragment to any server, so it stays out of access logs and Referer.
    return f"{settings.FRONTEND_URL.rstrip('/')}{path}#token={token}"


def _render(greeting: str, lines: list[str], link: str, button: str, footer: str) -> tuple[str, str]:
    text = "\n\n".join([greeting, *lines, link, footer, f"- {settings.CAMPUS_NAME} Registrar"])
    paragraphs = "".join(f"<p>{escape(line)}</p>" for line in lines)
    html = (
        '<div style="font-family:Arial,sans-serif;font-size:15px;color:#1f2937;max-width:520px">'
        f"<p>{escape(greeting)}</p>{paragraphs}"
        f'<p><a href="{escape(link, quote=True)}" style="display:inline-block;padding:10px 18px;'
        'background:#b91c1c;color:#ffffff;text-decoration:none;border-radius:8px">'
        f"{escape(button)}</a></p>"
        f'<p style="font-size:13px;color:#6b7280">{escape(footer)}</p>'
        f'<p style="font-size:13px;color:#6b7280">- {escape(settings.CAMPUS_NAME)} Registrar</p>'
        "</div>"
    )
    return text, html


def verification_email(user: UserDB, token: str) -> dict:
    hours = settings.EMAIL_VERIFICATION_TOKEN_HOURS
    text, html = _render(
        f"Hi {user.full_name},",
        [
            f"This address was added to the registrar queue system account '{user.username}'.",
            "Confirm it so you can reset your password by email if you ever forget it.",
        ],
        _link("/verify-email", token),
        "Confirm email address",
        f"This link expires in {hours} hours. If you don't recognise this account, ignore this email.",
    )
    return dict(to=user.email, subject="Confirm your email - BSU Registrar Queue", text=text, html=html)


def reset_email(user: UserDB, token: str) -> dict:
    minutes = settings.PASSWORD_RESET_TOKEN_MINUTES
    text, html = _render(
        f"Hi {user.full_name},",
        [
            f"Someone asked to reset the password for the account '{user.username}'.",
            "Use the link below to choose a new password. It works once.",
        ],
        _link("/reset-password", token),
        "Reset password",
        f"This link expires in {minutes} minutes. If you didn't ask for this, ignore this email - "
        "your password stays the same.",
    )
    return dict(to=user.email, subject="Reset your password - BSU Registrar Queue", text=text, html=html)


def start_email_verification(db: Session, user: UserDB) -> dict:
    """Issue a verification token and return the email to send (after the
    caller commits). Caller commits."""
    token = issue_token(
        db, user, EmailTokenPurpose.VERIFY_EMAIL,
        timedelta(hours=settings.EMAIL_VERIFICATION_TOKEN_HOURS),
    )
    return verification_email(user, token)


def send(message: dict) -> None:
    """Background-task entry point - looked up through the module so tests
    can capture outgoing mail by patching email_sender.send_email."""
    email_sender.send_email(**message)
