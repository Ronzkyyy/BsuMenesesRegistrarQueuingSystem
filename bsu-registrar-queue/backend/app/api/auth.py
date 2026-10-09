"""
Authentication endpoints for registrar staff
"""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path, Request, Response, status, Form
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from math import ceil

from ..core.audit import log_security_event
from ..core.config import settings
from ..core.database import get_db
from ..core.limiter import limiter
from ..core.security import (
    verify_password,
    create_access_token,
    get_current_active_user,
    get_current_active_user_pending_password,
    generate_temporary_password,
    reset_user_password,
    create_user_token,
    require_role,
    COOKIE_NAME,
)
from ..db_models import EmailTokenPurpose, UserDB, UserRole
from ..models.user import (
    User, UserCreate, PasswordChange, PasswordResetResult,
    EmailUpdate, ForgotPasswordRequest, EmailTokenRequest, ResetPasswordWithToken,
)
from ..services import account_email
from ..services import QueueService, TicketService, StudentService


router = APIRouter()


@router.post("/login", response_model=User)
@limiter.limit("5/minute")
def login(
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    portal: str | None = Form(None),
    db: Session = Depends(get_db)
):
    """Staff login endpoint - sets an httpOnly session cookie.

    On top of the per-IP rate limit above, an account is locked for
    ACCOUNT_LOCKOUT_MINUTES after MAX_FAILED_LOGIN_ATTEMPTS consecutive failed
    passwords - blocking brute force even from a rotating set of IPs. Any
    successful login clears the counter.
    """
    now = datetime.now(timezone.utc)
    user = db.query(UserDB).filter(UserDB.username == form_data.username).first()

    if user and user.locked_until is not None:
        locked_until = user.locked_until
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=timezone.utc)
        if locked_until > now:
            minutes_left = max(1, ceil((locked_until - now).total_seconds() / 60))
            log_security_event(
                "auth.login", outcome="blocked", request=request,
                actor=form_data.username, detail="account locked",
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Too many failed attempts for this account. "
                    f"Try again in about {minutes_left} minute(s)."
                ),
            )

    if not user or not verify_password(form_data.password, user.hashed_password):
        if user is not None:
            user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
            if user.failed_login_attempts >= settings.MAX_FAILED_LOGIN_ATTEMPTS:
                user.locked_until = now + timedelta(minutes=settings.ACCOUNT_LOCKOUT_MINUTES)
                user.failed_login_attempts = 0
                log_security_event(
                    "auth.account_locked", outcome="blocked", request=request,
                    actor=user.username,
                    detail=f"{settings.MAX_FAILED_LOGIN_ATTEMPTS} consecutive failed attempts",
                )
            db.commit()
        log_security_event(
            "auth.login", outcome="failure", request=request,
            actor=form_data.username,
            detail="unknown username" if user is None else "bad password",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    if user.failed_login_attempts or user.locked_until is not None:
        user.failed_login_attempts = 0
        user.locked_until = None
        db.commit()

    if not user.is_active:
        log_security_event(
            "auth.login", outcome="denied", request=request,
            actor=user.username, detail="inactive account",
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user account"
        )

    if portal == "admin" and user.role != UserRole.ADMIN:
        log_security_event(
            "auth.portal_denied", outcome="denied", request=request,
            actor=user.username, actor_role=user.role.value, detail="admin portal",
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account does not have Admin portal access."
        )

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role, "user_id": user.id},
        expires_delta=access_token_expires
    )

    response.set_cookie(
        key=COOKIE_NAME,
        value=access_token,
        httponly=True,
        # Secure only in production (DEBUG=False) - local dev and the test
        # suite run over plain http, matching how HSTS/upgrade-insecure-
        # requests are already gated on settings.DEBUG elsewhere in this app.
        secure=not settings.DEBUG,
        samesite="strict",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )

    log_security_event(
        "auth.login", outcome="success", request=request,
        actor=user.username, actor_role=user.role.value,
    )
    return User.model_validate(user)


@router.post("/logout")
def logout(response: Response):
    """Staff logout endpoint - clears the session cookie"""
    response.delete_cookie(key=COOKIE_NAME, path="/")
    return {"message": "Successfully logged out"}


@router.get("/me", response_model=User)
def get_current_user_info(
    current_user: User = Depends(get_current_active_user_pending_password)
):
    """Get current authenticated user info - still answers while a password
    change is pending, so the frontend can send the user to that screen."""
    return current_user


@router.post("/register", response_model=User)
def register_user(
    request: Request,
    user_data: UserCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN))
):
    """Register a new staff user (admin only). Emails the new address a
    verification link."""
    # Check if username exists
    existing = db.query(UserDB).filter(UserDB.username == user_data.username).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    try:
        email = account_email.check_email_available(db, user_data.email)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    from ..core.security import get_password_hash
    hashed_password = get_password_hash(user_data.password)

    db_user = UserDB(
        username=user_data.username,
        full_name=user_data.full_name,
        role=UserRole(user_data.role.value),
        hashed_password=hashed_password,
        is_active=True,
        email=email,
    )
    db.add(db_user)
    db.flush()
    message = account_email.start_email_verification(db, db_user)
    db.commit()
    db.refresh(db_user)
    background_tasks.add_task(account_email.send, message)

    log_security_event(
        "auth.user_created", outcome="success", request=request,
        actor=current_user.username, target=db_user.username,
        detail=f"role={db_user.role.value}",
    )
    return User.model_validate(db_user)


@router.post("/change-password")
def change_password(
    request: Request,
    payload: PasswordChange,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_pending_password)
):
    """Change your own password (any active staff account).

    Also the only way out of must_change_password after an admin reset - the
    temporary password is the `current_password` here, and the new one must
    differ from it.
    """
    user = db.query(UserDB).filter(UserDB.id == current_user.id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    if not verify_password(payload.current_password, user.hashed_password):
        log_security_event(
            "auth.password_changed", outcome="failure", request=request,
            actor=user.username, detail="current password incorrect",
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )

    if payload.new_password == payload.current_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from the current one"
        )

    from ..core.security import get_password_hash
    user.hashed_password = get_password_hash(payload.new_password)
    user.must_change_password = False
    db.commit()
    log_security_event(
        "auth.password_changed", outcome="success", request=request,
        actor=user.username,
    )
    return {"message": "Password changed successfully"}


@router.get("/users", response_model=list[User])
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN))
):
    """List all staff users (admin only)"""
    users = db.query(UserDB).all()
    return [User.model_validate(u) for u in users]


@router.post("/users/{user_id}/reset-password", response_model=PasswordResetResult)
def reset_password(
    request: Request,
    response: Response,
    user_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN))
):
    """Reset another account's forgotten password (admin only).

    Generates a temporary password, returns it once for the admin to hand
    over, unlocks the account, and forces a change at its next login - so the
    admin never knows the password the user ends up with.
    """
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Use Change Password to change your own password"
        )

    user = db.query(UserDB).filter(UserDB.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    temporary_password = generate_temporary_password()
    reset_user_password(user, temporary_password, must_change=True)
    db.commit()

    # The body carries a live credential - keep it out of every cache.
    response.headers["Cache-Control"] = "no-store"
    log_security_event(
        "auth.password_reset", outcome="success", request=request,
        actor=current_user.username, target=user.username,
        detail="temporary password issued",
    )
    return PasswordResetResult(username=user.username, temporary_password=temporary_password)


@router.patch("/users/{user_id}/deactivate")
def deactivate_user(
    request: Request,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN))
):
    """Deactivate a user (admin only)"""
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate yourself"
        )

    user = db.query(UserDB).filter(UserDB.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    user.is_active = False
    db.commit()
    log_security_event(
        "auth.user_deactivated", outcome="success", request=request,
        actor=current_user.username, target=user.username,
    )
    return {"message": "User deactivated successfully"}


@router.patch("/users/{user_id}/activate")
def activate_user(
    request: Request,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN))
):
    """Activate a user (admin only)"""
    user = db.query(UserDB).filter(UserDB.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    user.is_active = True
    db.commit()
    log_security_event(
        "auth.user_activated", outcome="success", request=request,
        actor=current_user.username, target=user.username,
    )
    return {"message": "User activated successfully"}


# ---------------------------------------------------------------------------
# Email address + self-service password reset
# ---------------------------------------------------------------------------

def _set_email(db: Session, user: UserDB, raw_email: str) -> tuple[str, dict | None]:
    """Change an account's email, un-verify it and issue a verification link.
    Returns (previous email or "", message to send or None if unchanged).
    Caller commits."""
    try:
        email = account_email.check_email_available(db, raw_email, exclude_user_id=user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    previous = user.email or ""
    if email == user.email:
        return previous, None
    user.email = email
    user.email_verified_at = None
    return previous, account_email.start_email_verification(db, user)


def _resend_verification(db: Session, user: UserDB, background_tasks: BackgroundTasks) -> dict:
    if not user.email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This account has no email address.")
    if user.email_verified_at is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This email is already confirmed.")
    message = account_email.start_email_verification(db, user)
    db.commit()
    background_tasks.add_task(account_email.send, message)
    return {"message": f"Verification link sent to {user.email}."}


@router.put("/me/email", response_model=User)
@limiter.limit("5/minute")
def set_my_email(
    request: Request,
    payload: EmailUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_pending_password),
):
    """Add your own email - how an account from before emails gets past the
    email requirement. Once confirmed, only an admin can change it, so a
    hijacked session can't redirect future reset links."""
    user = db.query(UserDB).filter(UserDB.id == current_user.id).first()
    if user.email and user.email_verified_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Your email is already confirmed. Ask an administrator to change it.",
        )
    previous, message = _set_email(db, user, payload.email)
    db.commit()
    db.refresh(user)
    if message:
        background_tasks.add_task(account_email.send, message)
        log_security_event(
            "auth.email_changed", outcome="success", request=request,
            actor=user.username, target=user.username,
            detail="replaced unconfirmed email" if previous else "added",
        )
    return User.model_validate(user)


@router.post("/me/email/resend-verification")
@limiter.limit("3/minute")
def resend_my_verification(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user_pending_password),
):
    """Send yourself a fresh verification link."""
    user = db.query(UserDB).filter(UserDB.id == current_user.id).first()
    return _resend_verification(db, user, background_tasks)


@router.patch("/users/{user_id}/email", response_model=User)
def set_user_email(
    request: Request,
    payload: EmailUpdate,
    background_tasks: BackgroundTasks,
    user_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Set or change any account's email (admin only). Reset links only go to
    it once its owner confirms it."""
    user = db.query(UserDB).filter(UserDB.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    previous, message = _set_email(db, user, payload.email)
    db.commit()
    db.refresh(user)
    if message:
        background_tasks.add_task(account_email.send, message)
        log_security_event(
            "auth.email_changed", outcome="success", request=request,
            actor=current_user.username, target=user.username,
            detail="changed" if previous else "added",
        )
    return User.model_validate(user)


@router.post("/users/{user_id}/resend-verification")
def resend_user_verification(
    background_tasks: BackgroundTasks,
    user_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Re-send the verification link for an account's unconfirmed email."""
    user = db.query(UserDB).filter(UserDB.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return _resend_verification(db, user, background_tasks)


@router.post("/verify-email")
@limiter.limit("10/minute")
def verify_email(
    request: Request,
    payload: EmailTokenRequest,
    db: Session = Depends(get_db),
):
    """Confirm an email address from the link in the verification email."""
    user = account_email.consume_token(db, payload.token, EmailTokenPurpose.VERIFY_EMAIL)
    if user is None:
        db.rollback()
        log_security_event(
            "auth.email_verified", outcome="failure", request=request,
            detail="invalid or expired link",
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=account_email.INVALID_LINK_DETAIL)
    user.email_verified_at = datetime.now(timezone.utc)
    db.commit()
    log_security_event("auth.email_verified", outcome="success", request=request, target=user.username)
    return {"message": "Email confirmed. You can now reset your password by email if you forget it."}


FORGOT_PASSWORD_REPLY = (
    "If that email belongs to a staff account with a confirmed email, "
    "a reset link is on its way. It expires in {minutes} minutes."
)


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("3/minute")
def forgot_password(
    request: Request,
    payload: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Email a one-time reset link. Always the same reply, so the form can't
    be used to find out which addresses have accounts; the email itself goes
    out after the response."""
    reply = {"message": FORGOT_PASSWORD_REPLY.format(minutes=settings.PASSWORD_RESET_TOKEN_MINUTES)}
    email = account_email.normalize_email(payload.email)
    user = db.query(UserDB).filter(UserDB.email == email).first()

    if user is None or not user.is_active or user.email_verified_at is None:
        if user is None:
            reason = "no account with that email"
        elif not user.is_active:
            reason = "inactive account"
        else:
            reason = "email not confirmed"
        log_security_event(
            "auth.password_reset_requested", outcome="failure", request=request,
            target=user.username if user else None, detail=reason,
        )
        return reply

    if account_email.recent_reset_count(db, user) >= settings.MAX_PASSWORD_RESET_EMAILS:
        log_security_event(
            "auth.password_reset_requested", outcome="blocked", request=request,
            target=user.username, detail="per-account email limit reached",
        )
        return reply

    token = account_email.issue_token(
        db, user, EmailTokenPurpose.RESET_PASSWORD,
        timedelta(minutes=settings.PASSWORD_RESET_TOKEN_MINUTES),
    )
    db.commit()
    background_tasks.add_task(account_email.send, account_email.reset_email(user, token))
    log_security_event(
        "auth.password_reset_requested", outcome="success", request=request, target=user.username,
    )
    return reply


@router.post("/reset-password")
@limiter.limit("10/minute")
def reset_password_with_token(
    request: Request,
    payload: ResetPasswordWithToken,
    db: Session = Depends(get_db),
):
    """Set a new password from an emailed reset link. Also unlocks the
    account and clears a pending forced change."""
    user = account_email.consume_token(db, payload.token, EmailTokenPurpose.RESET_PASSWORD)
    if user is None:
        db.rollback()
        log_security_event(
            "auth.password_reset_completed", outcome="failure", request=request,
            detail="invalid or expired link",
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=account_email.INVALID_LINK_DETAIL)

    reset_user_password(user, payload.new_password, must_change=False)
    db.commit()
    log_security_event(
        "auth.password_reset_completed", outcome="success", request=request, target=user.username,
    )
    return {"message": "Password updated. You can now log in with your new password."}
