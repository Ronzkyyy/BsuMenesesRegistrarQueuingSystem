"""
User model for registrar staff/admin accounts
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from enum import Enum


class UserRole(str, Enum):
    ADMIN = "admin"
    REGISTRAR = "registrar"
    STAFF = "staff"


class UserBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_.-]+$")
    full_name: str = Field(..., min_length=1, max_length=100)
    role: UserRole


class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=72)
    email: EmailStr = Field(..., max_length=254)


class User(UserBase):
    id: int
    is_active: bool = True
    must_change_password: bool = False
    # None only on accounts from before emails existed - see EmailUpdate.
    email: Optional[EmailStr] = None
    email_verified_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserInDB(User):
    hashed_password: str


class PasswordChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_password: str = Field(..., min_length=1, max_length=72)
    new_password: str = Field(..., min_length=8, max_length=72)


class EmailUpdate(BaseModel):
    """Set an account's email (admin, or the user adding a missing one)."""
    model_config = ConfigDict(extra="forbid")

    email: EmailStr = Field(..., max_length=254)


class ForgotPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr = Field(..., max_length=254)


class EmailTokenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # token_urlsafe(32) is 43 chars; leave headroom, refuse anything huge.
    token: str = Field(..., min_length=20, max_length=128)


class ResetPasswordWithToken(EmailTokenRequest):
    new_password: str = Field(..., min_length=8, max_length=72)


class PasswordResetResult(BaseModel):
    """Returned once to the admin who reset an account - never stored."""
    username: str
    temporary_password: str


class TokenData(BaseModel):
    username: Optional[str] = None