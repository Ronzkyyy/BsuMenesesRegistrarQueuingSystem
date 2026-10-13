"""
Document catalog service - the Admin-managed list of documents offered under
the Request Documents service
"""
from typing import List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..db_models import DocumentDB
from ..models.document import DocumentCreate, DocumentUpdate


class DocumentService:
    def __init__(self, db: Session):
        self.db = db

    def list_active(self) -> List[DocumentDB]:
        return self.db.query(DocumentDB).filter(
            DocumentDB.is_active.is_(True)
        ).order_by(DocumentDB.display_order, DocumentDB.id).all()

    def list_all(self) -> List[DocumentDB]:
        """Every entry, active first, each group in display order."""
        return self.db.query(DocumentDB).order_by(
            DocumentDB.is_active.desc(), DocumentDB.display_order, DocumentDB.id
        ).all()

    def _check_unique(self, name: Optional[str], short_name: Optional[str],
                      exclude_id: Optional[int] = None) -> None:
        """Readable 400s ahead of the case-insensitive unique indexes."""
        for column, value, label in (
            (DocumentDB.name, name, "name"),
            (DocumentDB.short_name, short_name, "short name"),
        ):
            if value is None:
                continue
            q = self.db.query(DocumentDB.id).filter(func.lower(column) == value.lower())
            if exclude_id is not None:
                q = q.filter(DocumentDB.id != exclude_id)
            if q.first():
                raise ValueError(f"Another document already uses this {label}.")

    def create(self, data: DocumentCreate) -> DocumentDB:
        self._check_unique(data.name, data.short_name)
        last = self.db.query(func.max(DocumentDB.display_order)).scalar() or 0
        document = DocumentDB(**data.model_dump(), display_order=last + 1, is_active=True)
        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)
        return document

    def update(self, document_id: int, data: DocumentUpdate) -> Tuple[Optional[DocumentDB], List[str]]:
        """Apply the fields the caller sent. Returns (document, changed field
        names), or (None, []) when the id doesn't exist."""
        document = self.db.get(DocumentDB, document_id)
        if not document:
            return None, []
        changes = data.model_dump(exclude_unset=True)
        self._check_unique(changes.get("name"), changes.get("short_name"), exclude_id=document_id)

        if changes.get("is_active") is False and document.is_active:
            others = self.db.query(func.count(DocumentDB.id)).filter(
                DocumentDB.is_active.is_(True), DocumentDB.id != document_id
            ).scalar()
            if not others:
                raise ValueError(
                    "At least one document must stay active, or students could not "
                    "request documents at all."
                )

        changed = [field for field, value in changes.items() if getattr(document, field) != value]
        for field in changed:
            setattr(document, field, changes[field])
        if changed:
            self.db.commit()
            self.db.refresh(document)
        return document, changed

    def reorder(self, document_ids: List[int]) -> List[DocumentDB]:
        """Set display_order from a full ordering of every catalog id."""
        documents = {d.id: d for d in self.db.query(DocumentDB).all()}
        if len(set(document_ids)) != len(document_ids) or set(document_ids) != set(documents):
            raise ValueError("The new order must list every document exactly once.")
        for order, document_id in enumerate(document_ids, start=1):
            documents[document_id].display_order = order
        self.db.commit()
        return self.list_all()
