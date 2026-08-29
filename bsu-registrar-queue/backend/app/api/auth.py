"""
Authentication endpoints for registrar staff
"""
from fastapi import APIRouter, Depends, HTTPException, Request, status, Form
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from math import ceil

from ..core.config import settings
from ..core.database import get_db
from ..core.limiter import limiter
from ..core.security import (
    verify_password,
    create_access_token,
    get_current_active_user,
    create_user_token,
    require_role,
)
from ..db_models import UserDB, UserRole
from ..models.user import Token, TokenData, User, UserCreate, PasswordChange, UserRole as UserRoleModel
from ..services import QueueService, TicketService, StudentService


router = APIRouter()


@router.post("/login", response_model=Token)
@limiter.limit("5/minute")
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    portal: str | None = Form(None),
    db: Session = Depends(get_db)
):
    """Staff login endpoint - returns JWT token.

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
            db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user.failed_login_attempts or user.locked_until is not None:
        user.failed_login_attempts = 0
        user.locked_until = None
        db.commit()

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user account"
        )

    if portal == "admin" and user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account does not have Admin portal access."
        )

    access_token_expires = timedelta(minutes=30)
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role, "user_id": user.id},
        expires_delta=access_token_expires
    )

    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/logout")
def logout():
    """Staff logout endpoint (client-side token removal)"""
    return {"message": "Successfully logged out"}


@router.get("/me", response_model=User)
def get_current_user_info(
    current_user: User = Depends(get_current_active_user)
):
    """Get current authenticated user info"""
    return current_user


@router.post("/register", response_model=User)
def register_user(
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
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )

    from ..core.security import get_password_hash
    user.hashed_password = get_password_hash(payload.new_password)
    db.commit()
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
    return {"message": "User deactivated successfully"}


@router.patch("/users/{user_id}/activate")
def activate_user(
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
    return {"message": "User activated successfully"}