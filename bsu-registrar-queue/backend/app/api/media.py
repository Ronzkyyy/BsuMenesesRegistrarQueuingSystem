"""
Media item management endpoints (display-board playlist)
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from ..core.database import get_db
from ..core.security import require_role
from ..db_models import UserRole
from ..models.media import MediaItem, MediaItemCreate, MediaItemUpdate
from ..models.user import User
from ..services.media_service import MediaService


router = APIRouter()


@router.get("/active", response_model=List[MediaItem])
def list_active_media(
    db: Session = Depends(get_db)
):
    """List active media items for the display boards (public endpoint)"""
    service = MediaService(db)
    return service.get_active()


@router.get("", response_model=List[MediaItem])
def list_media(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.REGISTRAR))
):
    """List all media items, including inactive (admin/registrar only)"""
    service = MediaService(db)
    return service.get_all()


@router.post("", response_model=MediaItem)
def create_media(
    data: MediaItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.REGISTRAR))
):
    """Create a new media item (admin/registrar only)"""
    service = MediaService(db)
    return service.create(data)


@router.patch("/{item_id}", response_model=MediaItem)
def update_media(
    item_id: int,
    data: MediaItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.REGISTRAR))
):
    """Update a media item (admin/registrar only)"""
    service = MediaService(db)
    item = service.update(item_id, data)
    if not item:
        raise HTTPException(status_code=404, detail="Media item not found")
    return item


@router.delete("/{item_id}")
def delete_media(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.REGISTRAR))
):
    """Delete a media item (admin/registrar only)"""
    service = MediaService(db)
    if not service.delete(item_id):
        raise HTTPException(status_code=404, detail="Media item not found")
    return {"message": "Media item deleted successfully"}
