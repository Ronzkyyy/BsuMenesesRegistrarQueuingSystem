"""
Media item model for display-board media playlist
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from enum import Enum


class MediaType(str, Enum):
    IMAGE = "image"
    VIDEO = "video"


class MediaItemBase(BaseModel):
    media_type: MediaType
    url: str
    display_duration_seconds: int = Field(default=10, ge=1, le=300)
    display_order: int = 0
    is_active: bool = True


class MediaItemCreate(MediaItemBase):
    pass


class MediaItemUpdate(BaseModel):
    media_type: Optional[MediaType] = None
    url: Optional[str] = None
    display_duration_seconds: Optional[int] = Field(default=None, ge=1, le=300)
    display_order: Optional[int] = None
    is_active: Optional[bool] = None


class MediaItem(MediaItemBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
