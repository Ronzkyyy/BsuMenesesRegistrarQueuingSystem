"""
Media item management endpoints (display-board playlist)
"""
import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import List

from ..core.database import get_db
from ..core.security import require_role
from ..db_models import UserRole
from ..models.media import MediaItem, MediaItemCreate, MediaItemUpdate, MediaUploadResponse
from ..models.user import User
from ..services.media_service import MediaService


router = APIRouter()

UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "uploads" / "media"
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".webm", ".ogg"}
MAX_IMAGE_SIZE = 5 * 1024 * 1024
MAX_VIDEO_SIZE = 50 * 1024 * 1024


@router.get("/active", response_model=List[MediaItem])
def list_active_media(
    db: Session = Depends(get_db)
):
    """List active media items for the display boards (public endpoint)"""
    service = MediaService(db)
    return service.get_active()


@router.post("/upload", response_model=MediaUploadResponse)
async def upload_media_file(
    file: UploadFile = File(...),
    current_user: User = Depends(require_role(UserRole.REGISTRAR))
):
    """Upload an image or video file for use as a media item (admin/registrar only)"""
    extension = Path(file.filename or "").suffix.lower()

    if extension in ALLOWED_IMAGE_EXTENSIONS:
        media_type = "image"
        max_size = MAX_IMAGE_SIZE
    elif extension in ALLOWED_VIDEO_EXTENSIONS:
        media_type = "video"
        max_size = MAX_VIDEO_SIZE
    else:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file type '{extension}'. Allowed: "
                f"images ({', '.join(sorted(ALLOWED_IMAGE_EXTENSIONS))}), "
                f"videos ({', '.join(sorted(ALLOWED_VIDEO_EXTENSIONS))})"
            )
        )

    contents = await file.read()
    if len(contents) > max_size:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size for {media_type} is {max_size // (1024 * 1024)}MB"
        )

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4()}{extension}"
    file_path = UPLOAD_DIR / filename
    with open(file_path, "wb") as f:
        f.write(contents)

    return MediaUploadResponse(url=f"/api/uploads/media/{filename}", media_type=media_type)


@router.get("", response_model=List[MediaItem])
def list_media(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.REGISTRAR))
):
    """List all media items, including inactive (admin/registrar only)"""
    service = MediaService(db)
    return service.get_all()


@router.post("", response_model=MediaItem)
def create_media(
    data: MediaItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.REGISTRAR))
):
    """Create a new media item (admin/registrar only)"""
    service = MediaService(db)
    return service.create(data)


@router.patch("/{item_id}", response_model=MediaItem)
def update_media(
    item_id: int,
    data: MediaItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.REGISTRAR))
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
    current_user: User = Depends(require_role(UserRole.REGISTRAR))
):
    """Delete a media item (admin/registrar only)"""
    service = MediaService(db)
    if not service.delete(item_id):
        raise HTTPException(status_code=404, detail="Media item not found")
    return {"message": "Media item deleted successfully"}
