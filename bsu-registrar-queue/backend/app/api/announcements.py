"""
Announcement management endpoints (display-board ticker)
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from ..core.database import get_db
from ..core.security import require_role
from ..db_models import UserRole
from ..models.announcement import Announcement, AnnouncementCreate, AnnouncementUpdate
from ..models.user import User
from ..services.announcement_service import AnnouncementService


router = APIRouter()


@router.get("/active", response_model=List[Announcement])
def list_active_announcements(
    db: Session = Depends(get_db)
):
    """List active announcements for the display boards (public endpoint)"""
    service = AnnouncementService(db)
    return service.get_active()


@router.get("", response_model=List[Announcement])
def list_announcements(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.REGISTRAR))
):
    """List all announcements, including inactive (admin/registrar only)"""
    service = AnnouncementService(db)
    return service.get_all()


@router.post("", response_model=Announcement)
def create_announcement(
    data: AnnouncementCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.REGISTRAR))
):
    """Create a new announcement (admin/registrar only)"""
    service = AnnouncementService(db)
    return service.create(data)


@router.patch("/{item_id}", response_model=Announcement)
def update_announcement(
    item_id: int,
    data: AnnouncementUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.REGISTRAR))
):
    """Update an announcement (admin/registrar only)"""
    service = AnnouncementService(db)
    item = service.update(item_id, data)
    if not item:
        raise HTTPException(status_code=404, detail="Announcement not found")
    return item


@router.delete("/{item_id}")
def delete_announcement(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.REGISTRAR))
):
    """Delete an announcement (admin/registrar only)"""
    service = AnnouncementService(db)
    if not service.delete(item_id):
        raise HTTPException(status_code=404, detail="Announcement not found")
    return {"message": "Announcement deleted successfully"}
