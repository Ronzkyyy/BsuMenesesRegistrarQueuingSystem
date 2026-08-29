"""
Media item model for display-board media playlist
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator
from enum import Enum


_ALLOWED_URL_PREFIXES = ("http://", "https://", "/api/uploads/media/")


def _validate_media_url(v: str) -> str:
    """Reject anything that isn't a plain http(s) URL or an app-hosted upload path.

    The display board renders this value as an <img>/<video> src, so schemes
    like javascript:, data:, or file: must never get through.
    """
    v = v.strip()
    if not v:
        raise ValueError("url cannot be blank")
    if not v.startswith(_ALLOWED_URL_PREFIXES):
        raise ValueError(
            "url must be an http(s) URL or an /api/uploads/media/ path"
        )
    return v


class MediaType(str, Enum):
    IMAGE = "image"
    VIDEO = "video"


class MediaSource(str, Enum):
    UPLOAD = "upload"
    LINK = "link"


class MediaItemBase(BaseModel):
    media_type: MediaType
    url: str = Field(..., min_length=1, max_length=2048)
    source: MediaSource = MediaSource.LINK
    display_duration_seconds: int = Field(default=10, ge=1, le=300)
    display_order: int = 0
    is_active: bool = True

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        return _validate_media_url(v)


class MediaItemCreate(MediaItemBase):
    pass


class MediaItemUpdate(BaseModel):
    media_type: Optional[MediaType] = None
    url: Optional[str] = Field(default=None, min_length=1, max_length=2048)
    source: Optional[MediaSource] = None
    display_duration_seconds: Optional[int] = Field(default=None, ge=1, le=300)
    display_order: Optional[int] = None
    is_active: Optional[bool] = None

    @field_validator("media_type", "url", "source")
    @classmethod
    def reject_explicit_null(cls, v):
        if v is None:
            raise ValueError("This field cannot be set to null")
        return v

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        return _validate_media_url(v)


class MediaItem(MediaItemBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class MediaUploadResponse(BaseModel):
    url: str
    media_type: MediaType
