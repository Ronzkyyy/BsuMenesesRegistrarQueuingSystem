"""
Security utilities for authentication: JWT tokens, password hashing
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from .audit import log_security_event
from .config import settings
from .database import get_db
from ..db_models import UserDB
from ..models.user import User, TokenData, UserRole


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# The JWT rides in an httpOnly cookie rather than an Authorization header, so
# it's never readable by page JavaScript - closes off token theft via XSS,
# a second, independent layer beyond the CSP that already blocks injected
# scripts from running in the first place. SameSite=Strict (set where this
# cookie is issued, in app/api/auth.py) is the CSRF defense for it - this app
# is same-origin with no legitimate cross-site request pattern, so that alone
# is a complete mitigation here, not a partial one.
COOKIE_NAME = "registrar_token"


def get_token_from_cookie(request: Request) -> str:
    """Extract the JWT from the httpOnly session cookie, 401 if absent."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return token


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt"""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[TokenData]:
    """Decode and validate a JWT token"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
        return TokenData(username=username)
    except JWTError:
        return None


async def get_current_user(
    token: str = Depends(get_token_from_cookie),
    db: Session = Depends(get_db)
) -> User:
    """Get the current authenticated user from JWT token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
    )
    token_data = decode_access_token(token)
    if token_data is None:
        raise credentials_exception

    user = db.query(UserDB).filter(UserDB.username == token_data.username).first()
    if user is None:
        raise credentials_exception

    return User.model_validate(user)


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Get current active user, raise exception if inactive"""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


def create_user_token(user: UserDB) -> str:
    """Create access token for a user"""
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return create_access_token(
        data={"sub": user.username, "role": user.role, "user_id": user.id},
        expires_delta=access_token_expires
    )


# Ascending privilege - CLAUDE.md documents this as "Admin > Registrar > Staff",
# so require_role() enforces an actual hierarchy rather than a flat allow-list:
# passing REGISTRAR permits Registrar *and* Admin, matching that documented
# mental model instead of silently locking Admins out of a Registrar-only
# route the way a bare `role != required` check would.
_ROLE_HIERARCHY = [UserRole.STAFF, UserRole.REGISTRAR, UserRole.ADMIN]


def require_role(minimum_role: UserRole):
    """Dependency to require at least `minimum_role`, per the Admin > Registrar >
    Staff hierarchy - any role at or above it is allowed."""
    minimum_level = _ROLE_HIERARCHY.index(minimum_role)

    def role_checker(
        request: Request,
        current_user: User = Depends(get_current_active_user),
    ) -> User:
        if _ROLE_HIERARCHY.index(current_user.role) < minimum_level:
            log_security_event(
                "authz.denied", outcome="denied", request=request,
                actor=current_user.username, actor_role=getattr(current_user.role, "value", str(current_user.role)),
                detail=f"requires at least: {minimum_role.value}",
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        return current_user
    return role_checker