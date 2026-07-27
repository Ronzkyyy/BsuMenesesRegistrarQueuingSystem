"""
Authentication endpoints for registrar staff
"""
from fastapi import APIRouter, Depends, HTTPException, Request, status, Form
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta

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
from ..models.user import Token, TokenData, User, UserCreate, UserRole as UserRoleModel
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
    """Staff login endpoint - returns JWT token"""
    user = db.query(UserDB).filter(UserDB.username == form_data.username).first()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

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