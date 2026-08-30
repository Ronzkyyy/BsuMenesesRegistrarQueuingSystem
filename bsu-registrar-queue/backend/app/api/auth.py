"""
Authentication endpoints for registrar staff
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status, Form
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
    create_user_token,
    require_role,
    COOKIE_NAME,
)
from ..db_models import UserDB, UserRole
from ..models.user import User, UserCreate, PasswordChange, UserRole as UserRoleModel
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
    return User(
        id=user.id,
        username=user.username,
        full_name=user.full_name,
        role=UserRoleModel(user.role.value),
        is_active=user.is_active,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.post("/logout")
def logout(response: Response):
    """Staff logout endpoint - clears the session cookie"""
    response.delete_cookie(key=COOKIE_NAME, path="/")
    return {"message": "Successfully logged out"}


@router.get("/me", response_model=User)
def get_current_user_info(
    current_user: User = Depends(get_current_active_user)
):
    """Get current authenticated user info"""
    return current_user


@router.post("/register", response_model=User)
def register_user(
    request: Request,
    user_data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN))
):
    """Register a new staff user (admin only)"""
    # Check if username exists
    existing = db.query(UserDB).filter(UserDB.username == user_data.username).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )

    from ..core.security import get_password_hash
    hashed_password = get_password_hash(user_data.password)

    db_user = UserDB(
        username=user_data.username,
        full_name=user_data.full_name,
        role=UserRole(user_data.role.value),
        hashed_password=hashed_password,
        is_active=True,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    log_security_event(
        "auth.user_created", outcome="success", request=request,
        actor=current_user.username, target=db_user.username,
        detail=f"role={db_user.role.value}",
    )
    return User(
        id=db_user.id,
        username=db_user.username,
        full_name=db_user.full_name,
        role=UserRoleModel(db_user.role.value),
        is_active=db_user.is_active,
        created_at=db_user.created_at,
        updated_at=db_user.updated_at,
    )


@router.post("/change-password")
def change_password(
    request: Request,
    payload: PasswordChange,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN))
):
    """Change the current admin's own password (admin only)"""
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

    from ..core.security import get_password_hash
    user.hashed_password = get_password_hash(payload.new_password)
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
    return [
        User(
            id=u.id,
            username=u.username,
            full_name=u.full_name,
            role=UserRoleModel(u.role.value),
            is_active=u.is_active,
            created_at=u.created_at,
            updated_at=u.updated_at,
        )
        for u in users
    ]


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