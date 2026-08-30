"""
Announcement model for display-board ticker
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class AnnouncementBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    text: str = Field(..., min_length=1, max_length=500)
    display_order: int = 0
    is_active: bool = True


class AnnouncementCreate(AnnouncementBase):
    pass


class AnnouncementUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    text: Optional[str] = Field(default=None, min_length=1, max_length=500)
    display_order: Optional[int] = None
    is_active: Optional[bool] = None

    @field_validator("text")
    @classmethod
    def reject_explicit_null(cls, v):
        if v is None:
            raise ValueError("This field cannot be set to null")
        return v


class Announcement(AnnouncementBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
