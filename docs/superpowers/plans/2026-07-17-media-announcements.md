# Media & Announcements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let Admin/Registrar staff manage a media playlist (images/videos) and a list of text announcements, and show both on the display boards (`/display/:id` and `/display/overview`) as a rotating media panel and a scrolling ticker.

**Architecture:** Two new SQLAlchemy models/tables, each with a standard CRUD service+router (Admin/Registrar-gated) plus a public `/active` read endpoint. A new Pinia store layer exposes both the admin-side and public-side data. One combined admin page manages both entities. One shared Vue component polls the public endpoints, rotates media items on their own configured duration, and renders a continuous marquee ticker from the announcement texts — embedded identically into both existing display-board screens.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, Pydantic v2 (backend); Vue 3 (Composition API), Pinia, Vue Router, Tailwind CSS (frontend).

## Global Constraints

- CRUD endpoints (create/list-all/update/delete) for both entities are gated `require_role(UserRole.ADMIN, UserRole.REGISTRAR)`. The `GET /active` endpoints are public, no auth — same convention as `/api/queues/active` and `/api/tickets/queue/{id}/display`.
- `is_active` is a simple on/off flag — no scheduling windows (start/end dates).
- Media URLs only — no file uploads/hosting. **Video items must be an iframe-embeddable URL (e.g. a YouTube `/embed/VIDEO_ID` link)** — the panel always renders video items in an `<iframe>`, never a native `<video>` tag. This resolves an ambiguity in the original design spec ("depending on URL shape") in favor of the simplest option: one rendering path per media type, no URL-shape sniffing.
- Both display boards must degrade gracefully: if there are zero active media items, the media panel section doesn't render at all; if there are zero active announcements, the ticker bar doesn't render at all. A media/announcement fetch failure must never block or hide the core "now serving" content — fail silent on this panel specifically.
- No automated test framework is configured for this project — verification is manual against the real running dev stack, per prior specs in this project.
- New tables are created automatically the next time `init_db()` runs (`Base.metadata.create_all` only creates tables that don't already exist) — re-running `seed.py` against the existing dev DB is enough, no Alembic migration needed.
- Seeded dev accounts: `admin/admin123` (Admin), `registrar/registrar123` (Registrar), `staff/staff123` (Staff).

---

### Task 1: Backend — Media & Announcement models, services, and endpoints

**Files:**
- Modify: `bsu-registrar-queue/backend/app/db_models.py`
- Create: `bsu-registrar-queue/backend/app/models/media.py`
- Create: `bsu-registrar-queue/backend/app/models/announcement.py`
- Create: `bsu-registrar-queue/backend/app/services/media_service.py`
- Create: `bsu-registrar-queue/backend/app/services/announcement_service.py`
- Modify: `bsu-registrar-queue/backend/app/services/__init__.py`
- Create: `bsu-registrar-queue/backend/app/api/media.py`
- Create: `bsu-registrar-queue/backend/app/api/announcements.py`
- Modify: `bsu-registrar-queue/backend/app/api/router.py`

**Interfaces:**
- Produces: `GET/POST /api/media`, `PATCH/DELETE /api/media/{id}`, `GET /api/media/active`; the same five shapes under `/api/announcements`. Response shape for a media item:
  ```json
  {"id": 1, "media_type": "image", "url": "https://example.com/pic.jpg", "display_duration_seconds": 10, "display_order": 0, "is_active": true, "created_at": "...", "updated_at": null}
  ```
  Response shape for an announcement:
  ```json
  {"id": 1, "text": "Welcome to BSU Meneses Campus", "display_order": 0, "is_active": true, "created_at": "...", "updated_at": null}
  ```

- [ ] **Step 1: Add the two new DB models**

In `bsu-registrar-queue/backend/app/db_models.py`, append at the end of the file:

```python


class MediaDBType(str, enum.Enum):
    IMAGE = "image"
    VIDEO = "video"


class MediaItemDB(Base):
    __tablename__ = "media_items"

    id = Column(Integer, primary_key=True, index=True)
    media_type = Column(Enum(MediaDBType), nullable=False)
    url = Column(String, nullable=False)
    display_duration_seconds = Column(Integer, default=10)
    display_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class AnnouncementDB(Base):
    __tablename__ = "announcements"

    id = Column(Integer, primary_key=True, index=True)
    text = Column(Text, nullable=False)
    display_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
```

- [ ] **Step 2: Create the Media Pydantic schemas**

Create `bsu-registrar-queue/backend/app/models/media.py`:

```python
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
```

- [ ] **Step 3: Create the Announcement Pydantic schemas**

Create `bsu-registrar-queue/backend/app/models/announcement.py`:

```python
"""
Announcement model for display-board ticker
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class AnnouncementBase(BaseModel):
    text: str = Field(..., min_length=1, max_length=500)
    display_order: int = 0
    is_active: bool = True


class AnnouncementCreate(AnnouncementBase):
    pass


class AnnouncementUpdate(BaseModel):
    text: Optional[str] = Field(default=None, min_length=1, max_length=500)
    display_order: Optional[int] = None
    is_active: Optional[bool] = None


class Announcement(AnnouncementBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
```

- [ ] **Step 4: Create `MediaService`**

Create `bsu-registrar-queue/backend/app/services/media_service.py`:

```python
"""
Media service - business logic for display-board media playlist
"""
from sqlalchemy.orm import Session
from typing import List, Optional

from ..db_models import MediaItemDB, MediaDBType
from ..models.media import MediaItem, MediaItemCreate, MediaItemUpdate


class MediaService:
    def __init__(self, db: Session):
        self.db = db

    def create(self, data: MediaItemCreate) -> MediaItem:
        db_item = MediaItemDB(
            media_type=MediaDBType(data.media_type.value),
            url=data.url,
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

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if field == "media_type" and value is not None:
                value = MediaDBType(value)
            setattr(item, field, value)

        self.db.commit()
        self.db.refresh(item)
        return self._to_schema(item)

    def delete(self, item_id: int) -> bool:
        item = self.db.query(MediaItemDB).filter(MediaItemDB.id == item_id).first()
        if not item:
            return False
        self.db.delete(item)
        self.db.commit()
        return True

    def _to_schema(self, db_item: MediaItemDB) -> MediaItem:
        return MediaItem(
            id=db_item.id,
            media_type=db_item.media_type.value,
            url=db_item.url,
            display_duration_seconds=db_item.display_duration_seconds,
            display_order=db_item.display_order,
            is_active=db_item.is_active,
            created_at=db_item.created_at,
            updated_at=db_item.updated_at,
        )
```

- [ ] **Step 5: Create `AnnouncementService`**

Create `bsu-registrar-queue/backend/app/services/announcement_service.py`:

```python
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
```

- [ ] **Step 6: Register the new services**

In `bsu-registrar-queue/backend/app/services/__init__.py`, replace:

```python
from .queue_service import QueueService
from .ticket_service import TicketService
from .student_service import StudentService

__all__ = ["QueueService", "TicketService", "StudentService"]
```

with:

```python
from .queue_service import QueueService
from .ticket_service import TicketService
from .student_service import StudentService
from .media_service import MediaService
from .announcement_service import AnnouncementService

__all__ = ["QueueService", "TicketService", "StudentService", "MediaService", "AnnouncementService"]
```

- [ ] **Step 7: Create the Media API router**

Create `bsu-registrar-queue/backend/app/api/media.py`:

```python
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
```

- [ ] **Step 8: Create the Announcements API router**

Create `bsu-registrar-queue/backend/app/api/announcements.py`:

```python
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
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.REGISTRAR))
):
    """List all announcements, including inactive (admin/registrar only)"""
    service = AnnouncementService(db)
    return service.get_all()


@router.post("", response_model=Announcement)
def create_announcement(
    data: AnnouncementCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.REGISTRAR))
):
    """Create a new announcement (admin/registrar only)"""
    service = AnnouncementService(db)
    return service.create(data)


@router.patch("/{item_id}", response_model=Announcement)
def update_announcement(
    item_id: int,
    data: AnnouncementUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.REGISTRAR))
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
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.REGISTRAR))
):
    """Delete an announcement (admin/registrar only)"""
    service = AnnouncementService(db)
    if not service.delete(item_id):
        raise HTTPException(status_code=404, detail="Announcement not found")
    return {"message": "Announcement deleted successfully"}
```

- [ ] **Step 9: Register both routers**

In `bsu-registrar-queue/backend/app/api/router.py`, replace the full contents:

```python
"""
Main API router combining all endpoints
"""
from fastapi import APIRouter
from .queues import router as queues_router
from .tickets import router as tickets_router
from .students import router as students_router
from .auth import router as auth_router
from .media import router as media_router
from .announcements import router as announcements_router

router = APIRouter()

router.include_router(auth_router, prefix="/auth", tags=["auth"])
router.include_router(queues_router, prefix="/queues", tags=["queues"])
router.include_router(tickets_router, prefix="/tickets", tags=["tickets"])
router.include_router(students_router, prefix="/students", tags=["students"])
router.include_router(media_router, prefix="/media", tags=["media"])
router.include_router(announcements_router, prefix="/announcements", tags=["announcements"])
```

- [ ] **Step 10: Re-create tables and start the backend**

From `bsu-registrar-queue/backend`, run the venv's Python against `seed.py` to pick up the two new tables in the existing dev DB (safe — `Base.metadata.create_all` only adds missing tables, `seed_initial_data` no-ops since already seeded):

```bash
.venv/Scripts/python.exe seed.py
```

Expected output includes `Database tables created successfully` and `Database already seeded, skipping...`.

Then start the backend: `.venv/Scripts/python.exe -m uvicorn app.main:app --port 8000` (or `.\dev.ps1` from `bsu-registrar-queue/` if the whole stack isn't already running). Wait for `Uvicorn running on http://0.0.0.0:8000`.

- [ ] **Step 11: Verify — Media CRUD + role gating + public endpoint**

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=admin123" | python -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

# Create
CREATE_RESP=$(curl -s -X POST http://localhost:8000/api/media \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"media_type": "image", "url": "https://example.com/pic.jpg", "display_duration_seconds": 8, "display_order": 1}')
echo "CREATE: $CREATE_RESP"
MEDIA_ID=$(echo "$CREATE_RESP" | python -c "import sys, json; print(json.load(sys.stdin)['id'])")

# Public active list includes it
curl -s http://localhost:8000/api/media/active
echo ""

# Update (deactivate)
curl -s -X PATCH http://localhost:8000/api/media/$MEDIA_ID \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"is_active": false}'
echo ""

# Public active list no longer includes it
curl -s http://localhost:8000/api/media/active
echo ""

# Staff (non-admin/registrar) is rejected
STAFF_TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=staff&password=staff123" | python -c "import sys, json; print(json.load(sys.stdin)['access_token'])")
curl -s -o /dev/null -w "staff create attempt: %{http_code}\n" -X POST http://localhost:8000/api/media \
  -H "Authorization: Bearer $STAFF_TOKEN" -H "Content-Type: application/json" \
  -d '{"media_type": "image", "url": "https://example.com/x.jpg"}'

# Delete
curl -s -o /dev/null -w "delete: %{http_code}\n" -X DELETE http://localhost:8000/api/media/$MEDIA_ID -H "Authorization: Bearer $TOKEN"
```

Expected: `CREATE` returns `200` with the new item; the first `/media/active` call includes it; after deactivating, the second `/media/active` call does NOT include it; `staff create attempt: 403`; `delete: 200`.

- [ ] **Step 12: Verify — Announcements CRUD + role gating + public endpoint**

```bash
CREATE_RESP=$(curl -s -X POST http://localhost:8000/api/announcements \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"text": "Welcome to BSU Meneses Campus", "display_order": 1}')
echo "CREATE: $CREATE_RESP"
ANN_ID=$(echo "$CREATE_RESP" | python -c "import sys, json; print(json.load(sys.stdin)['id'])")

curl -s http://localhost:8000/api/announcements/active
echo ""

curl -s -X PATCH http://localhost:8000/api/announcements/$ANN_ID \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"text": "Updated announcement text"}'
echo ""

curl -s -o /dev/null -w "staff create attempt: %{http_code}\n" -X POST http://localhost:8000/api/announcements \
  -H "Authorization: Bearer $STAFF_TOKEN" -H "Content-Type: application/json" \
  -d '{"text": "should be rejected"}'

curl -s -o /dev/null -w "delete: %{http_code}\n" -X DELETE http://localhost:8000/api/announcements/$ANN_ID -H "Authorization: Bearer $TOKEN"
```

Expected: `CREATE` returns `200`; `/announcements/active` includes it; the PATCH updates the text (confirm via a follow-up `GET /api/announcements`); `staff create attempt: 403`; `delete: 200`.

- [ ] **Step 13: Commit**

```bash
git add bsu-registrar-queue/backend/app/db_models.py \
        bsu-registrar-queue/backend/app/models/media.py \
        bsu-registrar-queue/backend/app/models/announcement.py \
        bsu-registrar-queue/backend/app/services/media_service.py \
        bsu-registrar-queue/backend/app/services/announcement_service.py \
        bsu-registrar-queue/backend/app/services/__init__.py \
        bsu-registrar-queue/backend/app/api/media.py \
        bsu-registrar-queue/backend/app/api/announcements.py \
        bsu-registrar-queue/backend/app/api/router.py
git commit -m "feat(media): add Media and Announcement models, services, and CRUD endpoints"
```

---

### Task 2: Frontend — store data layer

**Files:**
- Modify: `bsu-registrar-queue/frontend/src/stores/queue.js`

**Interfaces:**
- Consumes: Task 1's `/api/media*` and `/api/announcements*` endpoints.
- Produces: new state `mediaItems`, `activeMediaItems`, `announcements`, `activeAnnouncements`; new actions `fetchMediaItems()`, `createMediaItem(data)`, `updateMediaItem(id, data)`, `deleteMediaItem(id)`, `fetchActiveMediaItems()`, and the same 5 for announcements (`fetchAnnouncements`, `createAnnouncement`, `updateAnnouncement`, `deleteAnnouncement`, `fetchActiveAnnouncements`) — all following the store's existing `loading`/`error` pattern, except the two `fetchActive*` actions which follow the no-loading-toggle polling convention used by `fetchQueueDisplay`/`fetchNowServingOverview` (since these will be called on a recurring poll from the display panel, and toggling `loading` on every poll tick would cause UI flicker).

- [ ] **Step 1: Add the new state fields**

In `bsu-registrar-queue/frontend/src/stores/queue.js`, change:

```js
    // Users
    users: [],

    // UI State
```

to:

```js
    // Users
    users: [],

    // Media & Announcements
    mediaItems: [],
    activeMediaItems: [],
    announcements: [],
    activeAnnouncements: [],

    // UI State
```

- [ ] **Step 2: Add the Media and Announcement actions**

In the same file, change:

```js
    async deactivateUser(userId) {
      this.loading = true
      this.error = null
      try {
        await api.patch(`/auth/users/${userId}/deactivate`)
        const idx = this.users.findIndex(u => u.id === userId)
        if (idx !== -1) this.users[idx].is_active = false
      } catch (err) {
        this.error = err.response?.data?.detail || 'Failed to deactivate user'
        throw err
      } finally {
        this.loading = false
      }
    },

    // ============ QUEUE ACTIONS ============
```

to:

```js
    async deactivateUser(userId) {
      this.loading = true
      this.error = null
      try {
        await api.patch(`/auth/users/${userId}/deactivate`)
        const idx = this.users.findIndex(u => u.id === userId)
        if (idx !== -1) this.users[idx].is_active = false
      } catch (err) {
        this.error = err.response?.data?.detail || 'Failed to deactivate user'
        throw err
      } finally {
        this.loading = false
      }
    },

    // ============ MEDIA ACTIONS ============

    async fetchMediaItems() {
      this.loading = true
      this.error = null
      try {
        const response = await api.get('/media')
        this.mediaItems = response.data
        return response.data
      } catch (err) {
        this.error = err.response?.data?.detail || 'Failed to fetch media items'
        throw err
      } finally {
        this.loading = false
      }
    },

    async createMediaItem(data) {
      this.loading = true
      this.error = null
      try {
        const response = await api.post('/media', data)
        this.mediaItems.push(response.data)
        return response.data
      } catch (err) {
        this.error = err.response?.data?.detail || 'Failed to create media item'
        throw err
      } finally {
        this.loading = false
      }
    },

    async updateMediaItem(itemId, data) {
      this.loading = true
      this.error = null
      try {
        const response = await api.patch(`/media/${itemId}`, data)
        const idx = this.mediaItems.findIndex(m => m.id === itemId)
        if (idx !== -1) this.mediaItems[idx] = response.data
        return response.data
      } catch (err) {
        this.error = err.response?.data?.detail || 'Failed to update media item'
        throw err
      } finally {
        this.loading = false
      }
    },

    async deleteMediaItem(itemId) {
      this.loading = true
      this.error = null
      try {
        await api.delete(`/media/${itemId}`)
        this.mediaItems = this.mediaItems.filter(m => m.id !== itemId)
      } catch (err) {
        this.error = err.response?.data?.detail || 'Failed to delete media item'
        throw err
      } finally {
        this.loading = false
      }
    },

    async fetchActiveMediaItems() {
      try {
        const response = await api.get('/media/active')
        this.activeMediaItems = response.data
        return response.data
      } catch (err) {
        throw err
      }
    },

    // ============ ANNOUNCEMENT ACTIONS ============

    async fetchAnnouncements() {
      this.loading = true
      this.error = null
      try {
        const response = await api.get('/announcements')
        this.announcements = response.data
        return response.data
      } catch (err) {
        this.error = err.response?.data?.detail || 'Failed to fetch announcements'
        throw err
      } finally {
        this.loading = false
      }
    },

    async createAnnouncement(data) {
      this.loading = true
      this.error = null
      try {
        const response = await api.post('/announcements', data)
        this.announcements.push(response.data)
        return response.data
      } catch (err) {
        this.error = err.response?.data?.detail || 'Failed to create announcement'
        throw err
      } finally {
        this.loading = false
      }
    },

    async updateAnnouncement(itemId, data) {
      this.loading = true
      this.error = null
      try {
        const response = await api.patch(`/announcements/${itemId}`, data)
        const idx = this.announcements.findIndex(a => a.id === itemId)
        if (idx !== -1) this.announcements[idx] = response.data
        return response.data
      } catch (err) {
        this.error = err.response?.data?.detail || 'Failed to update announcement'
        throw err
      } finally {
        this.loading = false
      }
    },

    async deleteAnnouncement(itemId) {
      this.loading = true
      this.error = null
      try {
        await api.delete(`/announcements/${itemId}`)
        this.announcements = this.announcements.filter(a => a.id !== itemId)
      } catch (err) {
        this.error = err.response?.data?.detail || 'Failed to delete announcement'
        throw err
      } finally {
        this.loading = false
      }
    },

    async fetchActiveAnnouncements() {
      try {
        const response = await api.get('/announcements/active')
        this.activeAnnouncements = response.data
        return response.data
      } catch (err) {
        throw err
      }
    },

    // ============ QUEUE ACTIONS ============
```

- [ ] **Step 3: Verify — build succeeds**

From `bsu-registrar-queue/frontend`, run `npm run build`. Expected: builds successfully with no errors (this task adds no new `.vue` files, so this is a syntax check on `queue.js`).

- [ ] **Step 4: Commit**

```bash
git add bsu-registrar-queue/frontend/src/stores/queue.js
git commit -m "feat(media): add media/announcement store actions"
```

---

### Task 3: Frontend — admin management page

**Files:**
- Create: `bsu-registrar-queue/frontend/src/views/MediaAnnouncementsView.vue`
- Modify: `bsu-registrar-queue/frontend/src/router/index.js`
- Modify: `bsu-registrar-queue/frontend/src/components/AdminLayout.vue`

**Interfaces:**
- Consumes: Task 2's store actions (`fetchMediaItems`, `createMediaItem`, `updateMediaItem`, `deleteMediaItem`, `fetchAnnouncements`, `createAnnouncement`, `updateAnnouncement`, `deleteAnnouncement`).
- Produces: route `/admin/media` (name `admin-media`), a new `requiresRegistrarOrAdmin` router-guard tier, and a new sidebar link.

- [ ] **Step 1: Create `MediaAnnouncementsView.vue`**

Create `bsu-registrar-queue/frontend/src/views/MediaAnnouncementsView.vue`:

```vue
<template>
  <div>
    <div class="mb-8">
      <h2 class="text-3xl font-bold text-gray-900">Media & Announcements</h2>
      <p class="mt-2 text-gray-600">Manage the media playlist and announcement ticker shown on display boards</p>
    </div>

    <!-- Media Section -->
    <div class="bg-white rounded-xl shadow-sm border border-gray-100 mb-8">
      <div class="bg-bsu-primary/5 border-b border-bsu-primary/10 px-6 py-4 flex items-center justify-between">
        <h3 class="text-xl font-bold text-gray-900">Media Playlist</h3>
        <button
          @click="openCreateMediaModal"
          class="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-bsu-primary hover:bg-pink-800 focus:outline-none focus:ring-2 focus:ring-bsu-primary"
        >
          Add Media Item
        </button>
      </div>
      <div class="p-6">
        <div v-if="mediaError" class="bg-red-50 border border-red-200 rounded-lg p-4 mb-4">
          <p class="text-sm text-red-700">{{ mediaError }}</p>
        </div>

        <div class="overflow-hidden">
          <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
              <tr>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Type</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">URL</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Duration</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Order</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                <th class="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-200">
              <tr v-for="item in queueStore.mediaItems" :key="item.id">
                <td class="px-4 py-4 text-sm text-gray-900 capitalize">{{ item.media_type }}</td>
                <td class="px-4 py-4 text-sm text-gray-500 max-w-xs truncate">{{ item.url }}</td>
                <td class="px-4 py-4 text-sm text-gray-500">{{ item.display_duration_seconds }}s</td>
                <td class="px-4 py-4 text-sm text-gray-500">{{ item.display_order }}</td>
                <td class="px-4 py-4">
                  <StatusBadge :status="item.is_active ? 'active' : 'inactive'" />
                </td>
                <td class="px-4 py-4 text-right space-x-2 whitespace-nowrap">
                  <button
                    @click="toggleMediaActive(item)"
                    :disabled="mediaActionLoading"
                    class="px-3 py-1.5 text-sm font-medium rounded-md bg-gray-100 text-gray-700 hover:bg-gray-200 disabled:opacity-50"
                  >
                    {{ item.is_active ? 'Deactivate' : 'Activate' }}
                  </button>
                  <button
                    @click="openEditMediaModal(item)"
                    :disabled="mediaActionLoading"
                    class="px-3 py-1.5 text-sm font-medium rounded-md bg-blue-100 text-blue-800 hover:bg-blue-200 disabled:opacity-50"
                  >
                    Edit
                  </button>
                  <button
                    @click="removeMediaItem(item.id)"
                    :disabled="mediaActionLoading"
                    class="px-3 py-1.5 text-sm font-medium rounded-md bg-red-100 text-red-800 hover:bg-red-200 disabled:opacity-50"
                  >
                    Delete
                  </button>
                </td>
              </tr>
              <tr v-if="queueStore.mediaItems.length === 0">
                <td colspan="6" class="px-4 py-8 text-center text-gray-500">No media items yet.</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- Announcements Section -->
    <div class="bg-white rounded-xl shadow-sm border border-gray-100">
      <div class="bg-bsu-primary/5 border-b border-bsu-primary/10 px-6 py-4 flex items-center justify-between">
        <h3 class="text-xl font-bold text-gray-900">Announcements</h3>
        <button
          @click="openCreateAnnouncementModal"
          class="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-bsu-primary hover:bg-pink-800 focus:outline-none focus:ring-2 focus:ring-bsu-primary"
        >
          Add Announcement
        </button>
      </div>
      <div class="p-6">
        <div v-if="announcementError" class="bg-red-50 border border-red-200 rounded-lg p-4 mb-4">
          <p class="text-sm text-red-700">{{ announcementError }}</p>
        </div>

        <div class="overflow-hidden">
          <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
              <tr>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Text</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Order</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                <th class="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-200">
              <tr v-for="item in queueStore.announcements" :key="item.id">
                <td class="px-4 py-4 text-sm text-gray-900 max-w-md truncate">{{ item.text }}</td>
                <td class="px-4 py-4 text-sm text-gray-500">{{ item.display_order }}</td>
                <td class="px-4 py-4">
                  <StatusBadge :status="item.is_active ? 'active' : 'inactive'" />
                </td>
                <td class="px-4 py-4 text-right space-x-2 whitespace-nowrap">
                  <button
                    @click="toggleAnnouncementActive(item)"
                    :disabled="announcementActionLoading"
                    class="px-3 py-1.5 text-sm font-medium rounded-md bg-gray-100 text-gray-700 hover:bg-gray-200 disabled:opacity-50"
                  >
                    {{ item.is_active ? 'Deactivate' : 'Activate' }}
                  </button>
                  <button
                    @click="openEditAnnouncementModal(item)"
                    :disabled="announcementActionLoading"
                    class="px-3 py-1.5 text-sm font-medium rounded-md bg-blue-100 text-blue-800 hover:bg-blue-200 disabled:opacity-50"
                  >
                    Edit
                  </button>
                  <button
                    @click="removeAnnouncement(item.id)"
                    :disabled="announcementActionLoading"
                    class="px-3 py-1.5 text-sm font-medium rounded-md bg-red-100 text-red-800 hover:bg-red-200 disabled:opacity-50"
                  >
                    Delete
                  </button>
                </td>
              </tr>
              <tr v-if="queueStore.announcements.length === 0">
                <td colspan="4" class="px-4 py-8 text-center text-gray-500">No announcements yet.</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- Media Modal -->
    <div v-if="showMediaModal" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div class="bg-white rounded-xl shadow-xl max-w-md w-full mx-4">
        <div class="px-6 py-4 border-b border-gray-200">
          <h3 class="text-lg font-bold text-gray-900">{{ editingMediaId ? 'Edit Media Item' : 'Add Media Item' }}</h3>
        </div>
        <div class="px-6 py-4 space-y-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Type</label>
            <select
              v-model="mediaForm.media_type"
              class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-bsu-primary"
            >
              <option value="image">Image</option>
              <option value="video">Video (embeddable URL, e.g. YouTube /embed/ link)</option>
            </select>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">URL</label>
            <input
              v-model="mediaForm.url"
              type="text"
              class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-bsu-primary"
              placeholder="https://..."
            />
          </div>
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">Duration (seconds)</label>
              <input
                v-model.number="mediaForm.display_duration_seconds"
                type="number"
                min="1"
                max="300"
                class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-bsu-primary"
              />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">Order</label>
              <input
                v-model.number="mediaForm.display_order"
                type="number"
                min="0"
                class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-bsu-primary"
              />
            </div>
          </div>
          <div v-if="mediaModalError" class="p-3 bg-red-50 border border-red-200 rounded-lg">
            <p class="text-sm text-red-700">{{ mediaModalError }}</p>
          </div>
        </div>
        <div class="px-6 py-4 border-t border-gray-200 flex justify-end space-x-3">
          <button
            @click="showMediaModal = false"
            class="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200 focus:outline-none focus:ring-2 focus:ring-bsu-primary"
          >
            Cancel
          </button>
          <button
            @click="saveMedia"
            :disabled="mediaActionLoading"
            class="px-4 py-2 text-sm font-medium text-white bg-bsu-primary rounded-md hover:bg-pink-800 focus:outline-none focus:ring-2 focus:ring-bsu-primary disabled:opacity-50"
          >
            {{ editingMediaId ? 'Save' : 'Create' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Announcement Modal -->
    <div v-if="showAnnouncementModal" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div class="bg-white rounded-xl shadow-xl max-w-md w-full mx-4">
        <div class="px-6 py-4 border-b border-gray-200">
          <h3 class="text-lg font-bold text-gray-900">{{ editingAnnouncementId ? 'Edit Announcement' : 'Add Announcement' }}</h3>
        </div>
        <div class="px-6 py-4 space-y-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Text</label>
            <textarea
              v-model="announcementForm.text"
              rows="3"
              maxlength="500"
              class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-bsu-primary"
              placeholder="e.g., Enrollment for AY 2026-2027 is now open"
            ></textarea>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Order</label>
            <input
              v-model.number="announcementForm.display_order"
              type="number"
              min="0"
              class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-bsu-primary"
            />
          </div>
          <div v-if="announcementModalError" class="p-3 bg-red-50 border border-red-200 rounded-lg">
            <p class="text-sm text-red-700">{{ announcementModalError }}</p>
          </div>
        </div>
        <div class="px-6 py-4 border-t border-gray-200 flex justify-end space-x-3">
          <button
            @click="showAnnouncementModal = false"
            class="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200 focus:outline-none focus:ring-2 focus:ring-bsu-primary"
          >
            Cancel
          </button>
          <button
            @click="saveAnnouncement"
            :disabled="announcementActionLoading"
            class="px-4 py-2 text-sm font-medium text-white bg-bsu-primary rounded-md hover:bg-pink-800 focus:outline-none focus:ring-2 focus:ring-bsu-primary disabled:opacity-50"
          >
            {{ editingAnnouncementId ? 'Save' : 'Create' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useQueueStore } from '@/stores/queue'
import StatusBadge from '@/components/StatusBadge.vue'

const queueStore = useQueueStore()

// Media state
const mediaError = ref('')
const mediaModalError = ref('')
const mediaActionLoading = ref(false)
const showMediaModal = ref(false)
const editingMediaId = ref(null)
const mediaForm = ref({
  media_type: 'image',
  url: '',
  display_duration_seconds: 10,
  display_order: 0,
})

const openCreateMediaModal = () => {
  mediaModalError.value = ''
  editingMediaId.value = null
  mediaForm.value = { media_type: 'image', url: '', display_duration_seconds: 10, display_order: 0 }
  showMediaModal.value = true
}

const openEditMediaModal = (item) => {
  mediaModalError.value = ''
  editingMediaId.value = item.id
  mediaForm.value = {
    media_type: item.media_type,
    url: item.url,
    display_duration_seconds: item.display_duration_seconds,
    display_order: item.display_order,
  }
  showMediaModal.value = true
}

const saveMedia = async () => {
  if (!mediaForm.value.url) return

  mediaActionLoading.value = true
  mediaModalError.value = ''
  try {
    if (editingMediaId.value) {
      await queueStore.updateMediaItem(editingMediaId.value, mediaForm.value)
    } else {
      await queueStore.createMediaItem(mediaForm.value)
    }
    showMediaModal.value = false
  } catch (err) {
    const detail = err.response?.data?.detail
    mediaModalError.value = Array.isArray(detail)
      ? detail.map((d) => d.msg).join('; ')
      : detail || 'Failed to save media item'
  } finally {
    mediaActionLoading.value = false
  }
}

const toggleMediaActive = async (item) => {
  mediaActionLoading.value = true
  mediaError.value = ''
  try {
    await queueStore.updateMediaItem(item.id, { is_active: !item.is_active })
  } catch (err) {
    mediaError.value = err.response?.data?.detail || 'Failed to update media item'
  } finally {
    mediaActionLoading.value = false
  }
}

const removeMediaItem = async (itemId) => {
  if (!confirm('Delete this media item? This cannot be undone.')) return
  mediaActionLoading.value = true
  mediaError.value = ''
  try {
    await queueStore.deleteMediaItem(itemId)
  } catch (err) {
    mediaError.value = err.response?.data?.detail || 'Failed to delete media item'
  } finally {
    mediaActionLoading.value = false
  }
}

// Announcement state
const announcementError = ref('')
const announcementModalError = ref('')
const announcementActionLoading = ref(false)
const showAnnouncementModal = ref(false)
const editingAnnouncementId = ref(null)
const announcementForm = ref({
  text: '',
  display_order: 0,
})

const openCreateAnnouncementModal = () => {
  announcementModalError.value = ''
  editingAnnouncementId.value = null
  announcementForm.value = { text: '', display_order: 0 }
  showAnnouncementModal.value = true
}

const openEditAnnouncementModal = (item) => {
  announcementModalError.value = ''
  editingAnnouncementId.value = item.id
  announcementForm.value = { text: item.text, display_order: item.display_order }
  showAnnouncementModal.value = true
}

const saveAnnouncement = async () => {
  if (!announcementForm.value.text) return

  announcementActionLoading.value = true
  announcementModalError.value = ''
  try {
    if (editingAnnouncementId.value) {
      await queueStore.updateAnnouncement(editingAnnouncementId.value, announcementForm.value)
    } else {
      await queueStore.createAnnouncement(announcementForm.value)
    }
    showAnnouncementModal.value = false
  } catch (err) {
    const detail = err.response?.data?.detail
    announcementModalError.value = Array.isArray(detail)
      ? detail.map((d) => d.msg).join('; ')
      : detail || 'Failed to save announcement'
  } finally {
    announcementActionLoading.value = false
  }
}

const toggleAnnouncementActive = async (item) => {
  announcementActionLoading.value = true
  announcementError.value = ''
  try {
    await queueStore.updateAnnouncement(item.id, { is_active: !item.is_active })
  } catch (err) {
    announcementError.value = err.response?.data?.detail || 'Failed to update announcement'
  } finally {
    announcementActionLoading.value = false
  }
}

const removeAnnouncement = async (itemId) => {
  if (!confirm('Delete this announcement? This cannot be undone.')) return
  announcementActionLoading.value = true
  announcementError.value = ''
  try {
    await queueStore.deleteAnnouncement(itemId)
  } catch (err) {
    announcementError.value = err.response?.data?.detail || 'Failed to delete announcement'
  } finally {
    announcementActionLoading.value = false
  }
}

onMounted(async () => {
  try {
    await queueStore.fetchMediaItems()
  } catch (err) {
    mediaError.value = err.response?.data?.detail || 'Failed to load media items'
  }
  try {
    await queueStore.fetchAnnouncements()
  } catch (err) {
    announcementError.value = err.response?.data?.detail || 'Failed to load announcements'
  }
})
</script>
```

- [ ] **Step 2: Add the `/admin/media` route and `requiresRegistrarOrAdmin` guard**

In `bsu-registrar-queue/frontend/src/router/index.js`, change the `/admin` route's `children` array from:

```js
      children: [
        {
          path: '',
          name: 'admin-dashboard',
          component: () => import('../views/DashboardView.vue')
        },
        {
          path: 'queues',
          name: 'admin-queues',
          component: () => import('../views/QueueManagementView.vue')
        },
        {
          path: 'users',
          name: 'admin-users',
          component: () => import('../views/UserManagementView.vue'),
          meta: { requiresAdmin: true }
        }
      ]
```

to:

```js
      children: [
        {
          path: '',
          name: 'admin-dashboard',
          component: () => import('../views/DashboardView.vue')
        },
        {
          path: 'queues',
          name: 'admin-queues',
          component: () => import('../views/QueueManagementView.vue')
        },
        {
          path: 'media',
          name: 'admin-media',
          component: () => import('../views/MediaAnnouncementsView.vue'),
          meta: { requiresRegistrarOrAdmin: true }
        },
        {
          path: 'users',
          name: 'admin-users',
          component: () => import('../views/UserManagementView.vue'),
          meta: { requiresAdmin: true }
        }
      ]
```

Then change the `beforeEach` guard from:

```js
router.beforeEach(async (to) => {
  const queueStore = useQueueStore()

  if (to.meta.requiresAuth && !queueStore.isAuthenticated) {
    return { name: 'login' }
  }

  if (to.meta.requiresAdmin) {
    if (!queueStore.currentUser) {
      try {
        await queueStore.fetchCurrentUser()
      } catch (err) {
        return { name: 'login' }
      }
    }
    if (queueStore.currentUser?.role !== 'admin') {
      return { name: 'admin-dashboard' }
    }
  }
})
```

to:

```js
router.beforeEach(async (to) => {
  const queueStore = useQueueStore()

  if (to.meta.requiresAuth && !queueStore.isAuthenticated) {
    return { name: 'login' }
  }

  if (to.meta.requiresAdmin) {
    if (!queueStore.currentUser) {
      try {
        await queueStore.fetchCurrentUser()
      } catch (err) {
        return { name: 'login' }
      }
    }
    if (queueStore.currentUser?.role !== 'admin') {
      return { name: 'admin-dashboard' }
    }
  }

  if (to.meta.requiresRegistrarOrAdmin) {
    if (!queueStore.currentUser) {
      try {
        await queueStore.fetchCurrentUser()
      } catch (err) {
        return { name: 'login' }
      }
    }
    if (!['admin', 'registrar'].includes(queueStore.currentUser?.role)) {
      return { name: 'admin-dashboard' }
    }
  }
})
```

- [ ] **Step 3: Add the sidebar link in `AdminLayout.vue`**

In `bsu-registrar-queue/frontend/src/components/AdminLayout.vue`, change:

```html
          <router-link
            v-if="queueStore.currentUser?.role === 'admin'"
            to="/admin/users"
            class="block px-3 py-2 rounded-md text-sm font-medium"
            :class="route.path === '/admin/users' ? 'bg-bsu-primary/10 text-bsu-primary' : 'text-gray-700 hover:bg-gray-100'"
          >
            User Management
          </router-link>
        </nav>
```

to:

```html
          <router-link
            v-if="['admin', 'registrar'].includes(queueStore.currentUser?.role)"
            to="/admin/media"
            class="block px-3 py-2 rounded-md text-sm font-medium"
            :class="route.path === '/admin/media' ? 'bg-bsu-primary/10 text-bsu-primary' : 'text-gray-700 hover:bg-gray-100'"
          >
            Media & Announcements
          </router-link>
          <router-link
            v-if="queueStore.currentUser?.role === 'admin'"
            to="/admin/users"
            class="block px-3 py-2 rounded-md text-sm font-medium"
            :class="route.path === '/admin/users' ? 'bg-bsu-primary/10 text-bsu-primary' : 'text-gray-700 hover:bg-gray-100'"
          >
            User Management
          </router-link>
        </nav>
```

- [ ] **Step 4: Start the full dev stack**

From `bsu-registrar-queue/`, run `.\dev.ps1` (or restart the frontend/backend windows if already running, to pick up the router/store/component changes).

- [ ] **Step 5: Verify — Admin sees the new sidebar link and can manage both lists**

Log in as `admin` / `admin123`, portal Admin. Expected: sidebar shows "Media & Announcements" between Queue Management and User Management. Click it (`/admin/media`): both sections render (empty tables initially, or with items from Task 1's curl verification if not cleaned up). Add a media item and an announcement via the modals; confirm they appear in their tables; toggle Activate/Deactivate on each; edit one of each and confirm the change persists; delete one of each.

- [ ] **Step 6: Verify — Registrar has access, Staff does not**

Log out, log in as `registrar` / `registrar123` (portal Counter). Expected: sidebar shows "Media & Announcements" (but not "User Management"), and `/admin/media` works fully.

Log out, log in as `staff` / `staff123` (portal Counter). Expected: sidebar shows neither "Media & Announcements" nor "User Management". Manually navigate to `http://localhost:5173/admin/media`. Expected: redirected back to `/admin` (the dashboard).

- [ ] **Step 7: Commit**

```bash
git add bsu-registrar-queue/frontend/src/views/MediaAnnouncementsView.vue \
        bsu-registrar-queue/frontend/src/router/index.js \
        bsu-registrar-queue/frontend/src/components/AdminLayout.vue
git commit -m "feat(media): add Media & Announcements admin page"
```

---

### Task 4: Frontend — display-board media panel and ticker

**Files:**
- Create: `bsu-registrar-queue/frontend/src/components/MediaAnnouncementPanel.vue`
- Modify: `bsu-registrar-queue/frontend/src/views/DisplayBoardView.vue`
- Modify: `bsu-registrar-queue/frontend/src/views/DisplayOverviewView.vue`

**Interfaces:**
- Consumes: Task 2's `fetchActiveMediaItems()`/`fetchActiveAnnouncements()` store actions and `activeMediaItems`/`activeAnnouncements` state.
- Produces: a `<MediaAnnouncementPanel />` component embedded, unstyled-prop, in both display screens.

- [ ] **Step 1: Create `MediaAnnouncementPanel.vue`**

Create `bsu-registrar-queue/frontend/src/components/MediaAnnouncementPanel.vue`:

```vue
<template>
  <div>
    <!-- Media Panel -->
    <section v-if="mediaItems.length > 0 && currentItem" class="mt-10 max-w-5xl mx-auto px-8">
      <div class="rounded-2xl overflow-hidden border border-white/10 bg-black aspect-video flex items-center justify-center">
        <img
          v-if="currentItem.media_type === 'image'"
          :src="currentItem.url"
          :alt="`Media item ${currentItem.id}`"
          class="w-full h-full object-contain"
        />
        <iframe
          v-else
          :src="currentItem.url"
          class="w-full h-full"
          frameborder="0"
          allow="autoplay; encrypted-media"
          allowfullscreen
        ></iframe>
      </div>
    </section>

    <!-- Announcement Ticker -->
    <div v-if="tickerText" class="mt-6 bg-bsu-gold text-gray-900 overflow-hidden py-2">
      <div class="whitespace-nowrap inline-block animate-marquee font-semibold px-4">
        {{ tickerText }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useQueueStore } from '@/stores/queue'

const queueStore = useQueueStore()

const currentIndex = ref(0)
let rotationTimer = null
let refreshTimer = null

const mediaItems = computed(() => queueStore.activeMediaItems)
const currentItem = computed(() => mediaItems.value[currentIndex.value] || null)

const announcements = computed(() => queueStore.activeAnnouncements)
const tickerText = computed(() =>
  announcements.value.length > 0
    ? announcements.value.map((a) => a.text).join('     •     ')
    : ''
)

const scheduleNextRotation = () => {
  if (rotationTimer) clearTimeout(rotationTimer)
  if (mediaItems.value.length === 0) return
  const duration = (currentItem.value?.display_duration_seconds || 10) * 1000
  rotationTimer = setTimeout(() => {
    currentIndex.value = (currentIndex.value + 1) % mediaItems.value.length
    scheduleNextRotation()
  }, duration)
}

const refreshContent = async () => {
  const hadItems = mediaItems.value.length > 0
  try {
    await queueStore.fetchActiveMediaItems()
    await queueStore.fetchActiveAnnouncements()
  } catch (err) {
    // Fail silent - this is a non-critical decorative panel on a live public screen;
    // the core "now serving" content must never be blocked or hidden by this failing.
  }
  if (currentIndex.value >= mediaItems.value.length) {
    currentIndex.value = 0
  }
  if (!hadItems && mediaItems.value.length > 0) {
    scheduleNextRotation()
  }
}

onMounted(async () => {
  await refreshContent()
  if (mediaItems.value.length > 0) {
    scheduleNextRotation()
  }
  refreshTimer = setInterval(refreshContent, 30000)
})

onUnmounted(() => {
  if (rotationTimer) clearTimeout(rotationTimer)
  if (refreshTimer) clearInterval(refreshTimer)
})
</script>

<style scoped>
@keyframes marquee {
  0% { transform: translateX(100vw); }
  100% { transform: translateX(-100%); }
}
.animate-marquee {
  animation: marquee 20s linear infinite;
}
</style>
```

- [ ] **Step 2: Embed the panel in `DisplayBoardView.vue`**

In `bsu-registrar-queue/frontend/src/views/DisplayBoardView.vue`, change:

```html
          <p v-else class="text-center text-white/30">No one is waiting right now</p>
        </section>
      </div>
    </main>

    <footer class="text-center py-4 text-xs text-white/30 border-t border-white/10">
      Bulacan State University - Meneses Campus &middot; Registrar Queue Management System
      <span class="inline-block w-1.5 h-1.5 rounded-full bg-green-500 ml-2 align-middle animate-pulse"></span>
    </footer>
```

to:

```html
          <p v-else class="text-center text-white/30">No one is waiting right now</p>
        </section>
      </div>
    </main>

    <MediaAnnouncementPanel />

    <footer class="text-center py-4 text-xs text-white/30 border-t border-white/10">
      Bulacan State University - Meneses Campus &middot; Registrar Queue Management System
      <span class="inline-block w-1.5 h-1.5 rounded-full bg-green-500 ml-2 align-middle animate-pulse"></span>
    </footer>
```

Then change the `<script setup>` imports from:

```js
import { onMounted, onUnmounted, ref, computed } from 'vue'
import { useRoute } from 'vue-router'
import { format } from 'date-fns'
import { useQueueStore } from '@/stores/queue'
```

to:

```js
import { onMounted, onUnmounted, ref, computed } from 'vue'
import { useRoute } from 'vue-router'
import { format } from 'date-fns'
import { useQueueStore } from '@/stores/queue'
import MediaAnnouncementPanel from '@/components/MediaAnnouncementPanel.vue'
```

- [ ] **Step 3: Embed the panel in `DisplayOverviewView.vue`**

In `bsu-registrar-queue/frontend/src/views/DisplayOverviewView.vue`, change:

```html
      </div>
    </main>

    <footer class="text-center py-4 text-xs text-white/30 border-t border-white/10">
      Bulacan State University - Meneses Campus &middot; Registrar Queue Management System
      <span class="inline-block w-1.5 h-1.5 rounded-full bg-green-500 ml-2 align-middle animate-pulse"></span>
    </footer>
```

to:

```html
      </div>
    </main>

    <MediaAnnouncementPanel />

    <footer class="text-center py-4 text-xs text-white/30 border-t border-white/10">
      Bulacan State University - Meneses Campus &middot; Registrar Queue Management System
      <span class="inline-block w-1.5 h-1.5 rounded-full bg-green-500 ml-2 align-middle animate-pulse"></span>
    </footer>
```

Then change the `<script setup>` imports from:

```js
import { onMounted, onUnmounted, ref, computed } from 'vue'
import { format } from 'date-fns'
import { useQueueStore } from '@/stores/queue'
```

to:

```js
import { onMounted, onUnmounted, ref, computed } from 'vue'
import { format } from 'date-fns'
import { useQueueStore } from '@/stores/queue'
import MediaAnnouncementPanel from '@/components/MediaAnnouncementPanel.vue'
```

- [ ] **Step 4: Start the full dev stack**

From `bsu-registrar-queue/`, run `.\dev.ps1` (or restart the frontend if already running).

- [ ] **Step 5: Verify — panels render on both display screens**

Using the admin page from Task 3, ensure at least one active image media item and one active announcement exist. Open `http://localhost:5173/display/1` (or any active queue's board) and separately `http://localhost:5173/display/overview`. Expected on both: the media panel appears below the queue content showing the image, and a scrolling gold ticker bar appears at the very bottom with the announcement text moving continuously.

- [ ] **Step 6: Verify — rotation, multiple items, and graceful empty state**

In the admin page, add a second media item with a short `display_duration_seconds` (e.g. 5) and a second announcement. Confirm on a display board that the media panel switches to the second item after its configured duration and loops back to the first, and the ticker now scrolls both announcement texts joined together. Then deactivate all media items and all announcements; confirm both the media panel and the ticker bar disappear entirely (no empty box, no empty bar) while the rest of the display board keeps working normally.

- [ ] **Step 7: Commit**

```bash
git add bsu-registrar-queue/frontend/src/components/MediaAnnouncementPanel.vue \
        bsu-registrar-queue/frontend/src/views/DisplayBoardView.vue \
        bsu-registrar-queue/frontend/src/views/DisplayOverviewView.vue
git commit -m "feat(media): show media panel and announcement ticker on display boards"
```
