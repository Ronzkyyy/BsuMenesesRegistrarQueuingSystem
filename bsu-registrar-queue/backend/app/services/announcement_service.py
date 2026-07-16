"""
Announcement service - business logic for display-board announcements
"""
from sqlalchemy.orm import Session
from typing import List, Optional

from ..db_models import AnnouncementDB
from ..models.announcement import Announcement, AnnouncementCreate, AnnouncementUpdate


class AnnouncementService:
    def __init__(self, db: Session):
        self.db = db

    def create(self, data: AnnouncementCreate) -> Announcement:
        db_item = AnnouncementDB(
            text=data.text,
            display_order=data.display_order,
            is_active=data.is_active,
        )
        self.db.add(db_item)
        self.db.commit()
        self.db.refresh(db_item)
        return self._to_schema(db_item)

    def get_all(self) -> List[Announcement]:
        items = self.db.query(AnnouncementDB).order_by(AnnouncementDB.display_order).all()
        return [self._to_schema(i) for i in items]

    def get_active(self) -> List[Announcement]:
        items = self.db.query(AnnouncementDB).filter(
            AnnouncementDB.is_active == True
        ).order_by(AnnouncementDB.display_order).all()
        return [self._to_schema(i) for i in items]

    def update(self, item_id: int, data: AnnouncementUpdate) -> Optional[Announcement]:
        item = self.db.query(AnnouncementDB).filter(AnnouncementDB.id == item_id).first()
        if not item:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(item, field, value)

        self.db.commit()
        self.db.refresh(item)
        return self._to_schema(item)

    def delete(self, item_id: int) -> bool:
        item = self.db.query(AnnouncementDB).filter(AnnouncementDB.id == item_id).first()
        if not item:
            return False
        self.db.delete(item)
        self.db.commit()
        return True

    def _to_schema(self, db_item: AnnouncementDB) -> Announcement:
        return Announcement(
            id=db_item.id,
            text=db_item.text,
            display_order=db_item.display_order,
            is_active=db_item.is_active,
            created_at=db_item.created_at,
            updated_at=db_item.updated_at,
        )
