"""
Media service - business logic for display-board media playlist
"""
from pathlib import Path
from sqlalchemy.orm import Session
from typing import List, Optional

from ..db_models import MediaItemDB, MediaDBType, MediaDBSource
from ..models.media import MediaItem, MediaItemCreate, MediaItemUpdate

UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "uploads" / "media"


class MediaService:
    def __init__(self, db: Session):
        self.db = db

    def create(self, data: MediaItemCreate) -> MediaItem:
        db_item = MediaItemDB(
            media_type=MediaDBType(data.media_type.value),
            url=data.url,
            source=MediaDBSource(data.source.value),
            display_duration_seconds=data.display_duration_seconds,
            display_order=data.display_order,
            is_active=data.is_active,
        )
        self.db.add(db_item)
        self.db.commit()
        self.db.refresh(db_item)
        return self._to_schema(db_item)

    def get_all(self) -> List[MediaItem]:
        items = self.db.query(MediaItemDB).order_by(MediaItemDB.display_order).all()
        return [self._to_schema(i) for i in items]

    def get_active(self) -> List[MediaItem]:
        items = self.db.query(MediaItemDB).filter(
            MediaItemDB.is_active == True
        ).order_by(MediaItemDB.display_order).all()
        return [self._to_schema(i) for i in items]

    def update(self, item_id: int, data: MediaItemUpdate) -> Optional[MediaItem]:
        item = self.db.query(MediaItemDB).filter(MediaItemDB.id == item_id).first()
        if not item:
            return None

        old_url = item.url
        old_source = item.source

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if field == "media_type" and value is not None:
                value = MediaDBType(value)
            if field == "source" and value is not None:
                value = MediaDBSource(value)
            setattr(item, field, value)

        self.db.commit()
        self.db.refresh(item)

        if old_source == MediaDBSource.UPLOAD and "url" in update_data and item.url != old_url:
            self._delete_file(old_url)

        return self._to_schema(item)

    def delete(self, item_id: int) -> bool:
        item = self.db.query(MediaItemDB).filter(MediaItemDB.id == item_id).first()
        if not item:
            return False
        source = item.source
        url = item.url
        self.db.delete(item)
        self.db.commit()
        if source == MediaDBSource.UPLOAD:
            self._delete_file(url)
        return True

    def _delete_file(self, url: str) -> None:
        """Best-effort delete of an uploaded file from disk - never raises."""
        try:
            file_path = UPLOAD_DIR / Path(url).name
            if file_path.exists():
                file_path.unlink()
        except OSError:
            pass

    def _to_schema(self, db_item: MediaItemDB) -> MediaItem:
        return MediaItem(
            id=db_item.id,
            media_type=db_item.media_type.value,
            url=db_item.url,
            source=db_item.source.value,
            display_duration_seconds=db_item.display_duration_seconds,
            display_order=db_item.display_order,
            is_active=db_item.is_active,
            created_at=db_item.created_at,
            updated_at=db_item.updated_at,
        )
