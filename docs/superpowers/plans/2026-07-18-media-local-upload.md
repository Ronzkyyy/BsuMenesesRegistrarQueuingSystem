# Local Media Upload Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let Admin/Registrar staff upload an image or video file from their own computer as an alternative to pasting a URL, for Media items shown on the display boards.

**Architecture:** A new `source` column (`upload`/`link`) on `MediaItemDB` records where a media item's URL came from. A new upload endpoint validates and saves a file to local disk, served back through the existing `/api` path via a `StaticFiles` mount, and returns the URL for the client to use with the existing create/update endpoints. The admin form gains an Upload/Paste-URL toggle; the display panel renders uploaded videos with a native `<video>` element instead of the `<iframe>` used for external embed links.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, Pydantic v2, `python-multipart` (already a dependency), `httpx` (already a dependency, used for verification) — backend. Vue 3 (Composition API), Pinia, Tailwind CSS — frontend.

## Global Constraints

- Allowed upload extensions: images `.jpg`, `.jpeg`, `.png`, `.gif`, `.webp`; videos `.mp4`, `.webm`, `.ogg`. Anything else → `400`.
- Size limits: images ≤ 5 MB, videos ≤ 50 MB. Over the limit → `400`.
- Uploaded files are saved to `backend/uploads/media/<uuid4><ext>` and served at `/api/uploads/media/<uuid4><ext>` — under `/api` specifically, so the existing dev-proxy rule (`frontend/vite.config.js` only proxies `/api/*`) reaches them with no new proxy configuration.
- Upload endpoint is Admin/Registrar-gated, same as every other Media mutation endpoint. It only saves the file and returns its URL/type — it does not create a `MediaItemDB` row itself; the client still calls the existing create/update endpoints with the returned URL.
- Deleting or replacing (re-uploading over) a `source=upload` item removes its old file from disk, best-effort (never fails the DB operation if the file is already gone).
- The existing "paste a URL" path (including external video embeds rendered via `<iframe>`) is unchanged and keeps working exactly as today; `source` defaults to `link` for backward compatibility with every existing row.
- No automated test framework is configured for this project — verification is manual against the real running dev stack, per prior specs in this project.
- Seeded dev accounts: `admin/admin123` (Admin), `registrar/registrar123` (Registrar), `staff/staff123` (Staff).

---

### Task 1: Backend — upload endpoint, schema, and cleanup

**Files:**
- Modify: `bsu-registrar-queue/backend/app/db_models.py`
- Modify: `bsu-registrar-queue/backend/app/models/media.py`
- Modify: `bsu-registrar-queue/backend/app/services/media_service.py`
- Modify: `bsu-registrar-queue/backend/app/api/media.py`
- Modify: `bsu-registrar-queue/backend/app/main.py`
- Modify: `.gitignore`

**Interfaces:**
- Produces: `POST /api/media/upload` (Admin/Registrar-gated, multipart `file` field) → `{"url": "/api/uploads/media/<uuid><ext>", "media_type": "image"|"video"}`. `MediaItem`/`MediaItemCreate`/`MediaItemUpdate` gain a `source: "upload"|"link"` field (default `"link"`). Static files under `backend/uploads/` are served at `/api/uploads/...`.

- [ ] **Step 1: Add the `source` column**

In `bsu-registrar-queue/backend/app/db_models.py`, change:

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
```

to:

```python
class MediaDBType(str, enum.Enum):
    IMAGE = "image"
    VIDEO = "video"


class MediaDBSource(str, enum.Enum):
    UPLOAD = "upload"
    LINK = "link"


class MediaItemDB(Base):
    __tablename__ = "media_items"

    id = Column(Integer, primary_key=True, index=True)
    media_type = Column(Enum(MediaDBType), nullable=False)
    url = Column(String, nullable=False)
    source = Column(Enum(MediaDBSource), default=MediaDBSource.LINK, nullable=False)
    display_duration_seconds = Column(Integer, default=10)
    display_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
```

- [ ] **Step 2: Add `source` to the Pydantic schemas and a new upload-response schema**

Replace the full contents of `bsu-registrar-queue/backend/app/models/media.py`:

```python
"""
Media item model for display-board media playlist
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator
from enum import Enum


class MediaType(str, Enum):
    IMAGE = "image"
    VIDEO = "video"


class MediaSource(str, Enum):
    UPLOAD = "upload"
    LINK = "link"


class MediaItemBase(BaseModel):
    media_type: MediaType
    url: str
    source: MediaSource = MediaSource.LINK
    display_duration_seconds: int = Field(default=10, ge=1, le=300)
    display_order: int = 0
    is_active: bool = True


class MediaItemCreate(MediaItemBase):
    pass


class MediaItemUpdate(BaseModel):
    media_type: Optional[MediaType] = None
    url: Optional[str] = None
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


class MediaItem(MediaItemBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class MediaUploadResponse(BaseModel):
    url: str
    media_type: MediaType
```

- [ ] **Step 3: Update `MediaService` for `source` and file cleanup**

Replace the full contents of `bsu-registrar-queue/backend/app/services/media_service.py`:

```python
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
```

- [ ] **Step 4: Add the upload endpoint**

In `bsu-registrar-queue/backend/app/api/media.py`, change the imports from:

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
```

to:

```python
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
```

Then, immediately after `list_active_media` and before `list_media`, insert this new endpoint:

```python
@router.post("/upload", response_model=MediaUploadResponse)
async def upload_media_file(
    file: UploadFile = File(...),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.REGISTRAR))
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
```

(No route-ordering concern here: this is a literal `POST /upload` path, distinct from `POST ""` and from the `PATCH/DELETE /{item_id}` routes both in path shape and HTTP method — it cannot be shadowed regardless of where it's placed in the file.)

- [ ] **Step 5: Mount the uploads directory as static files**

In `bsu-registrar-queue/backend/app/main.py`, change:

```python
"""
BSU Registrar Queue System - Main Application
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .core.config import settings
from .api import router

app = FastAPI(
    title="BSU Registrar Queue System",
    description="Queue management for Bulacan State University Meneses Campus Registrar",
    version="1.0.0",
    # The frontend calls collection endpoints without a trailing slash (e.g. /api/queues).
    # Starlette's default trailing-slash redirect breaks on preflighted cross-origin
    # requests (browsers refuse to follow a redirect after a CORS preflight), so routes
    # are defined to match the no-trailing-slash path exactly instead of redirecting.
    redirect_slashes=False,
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")


@app.get("/")
def root():
    return {"message": "BSU Registrar Queue System API", "status": "running"}
```

to:

```python
"""
BSU Registrar Queue System - Main Application
"""
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from .core.config import settings
from .api import router

app = FastAPI(
    title="BSU Registrar Queue System",
    description="Queue management for Bulacan State University Meneses Campus Registrar",
    version="1.0.0",
    # The frontend calls collection endpoints without a trailing slash (e.g. /api/queues).
    # Starlette's default trailing-slash redirect breaks on preflighted cross-origin
    # requests (browsers refuse to follow a redirect after a CORS preflight), so routes
    # are defined to match the no-trailing-slash path exactly instead of redirecting.
    redirect_slashes=False,
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")

# Serves uploaded media (backend/uploads/media/<file>) at /api/uploads/media/<file> -
# mounted under /api specifically so the frontend dev proxy (which only forwards /api/*)
# and any production reverse-proxy rule for /api reach it with no extra configuration.
UPLOADS_DIR = Path(__file__).resolve().parent.parent / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/api/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")


@app.get("/")
def root():
    return {"message": "BSU Registrar Queue System API", "status": "running"}
```

- [ ] **Step 6: Ignore the uploads directory**

In `.gitignore` (repo root), change:

```
# Backend env / local db
backend/.env
bsu-registrar-queue/backend/.env
*.db
bsu_queue.db
```

to:

```
# Backend env / local db
backend/.env
bsu-registrar-queue/backend/.env
*.db
bsu_queue.db

# Uploaded media (runtime data, not source)
backend/uploads/
bsu-registrar-queue/backend/uploads/
```

- [ ] **Step 7: Re-create tables and start the backend**

From `bsu-registrar-queue/backend`, run `.venv/Scripts/python.exe seed.py` to add the new `source` column to the existing `media_items` table's schema definition (SQLAlchemy's `Base.metadata.create_all` only creates missing *tables*, not new *columns* on an existing table — if your dev DB already has a `media_items` table from the prior Media & Announcements work, delete just that table or recreate the dev DB before running seed, since a column addition isn't picked up automatically). Then start the backend: `.venv/Scripts/python.exe -m uvicorn app.main:app --port 8000` (or `.\dev.ps1` from `bsu-registrar-queue/` if the whole stack isn't already running).

- [ ] **Step 8: Verify — upload endpoint (valid image, valid video, rejections, role gating)**

Use `httpx` (already a project dependency) for these checks, since it handles multipart uploads directly:

```bash
cd bsu-registrar-queue/backend
.venv/Scripts/python.exe -c "
import httpx

base = 'http://localhost:8000/api'

# Login as admin
resp = httpx.post(f'{base}/auth/login', data={'username': 'admin', 'password': 'admin123'})
token = resp.json()['access_token']
headers = {'Authorization': f'Bearer {token}'}

# Valid image upload (tiny 1x1 PNG bytes)
png_bytes = bytes.fromhex('89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000a49444154789c6360000002000155a24f5a0000000049454e44ae426082')
r = httpx.post(f'{base}/media/upload', headers=headers, files={'file': ('test.png', png_bytes, 'image/png')})
print('image upload:', r.status_code, r.json())
image_url = r.json()['url']

# Reachable via the backend directly
r2 = httpx.get(f'http://localhost:8000{image_url}')
print('image reachable:', r2.status_code, len(r2.content), 'bytes')

# Disallowed extension
r3 = httpx.post(f'{base}/media/upload', headers=headers, files={'file': ('test.exe', b'not a real exe', 'application/octet-stream')})
print('disallowed extension:', r3.status_code, r3.json())

# Over size limit (6MB fake 'image')
big = b'0' * (6 * 1024 * 1024)
r4 = httpx.post(f'{base}/media/upload', headers=headers, files={'file': ('big.png', big, 'image/png')})
print('over size limit:', r4.status_code, r4.json())

# Registrar can also upload (same allowed role as admin)
registrar_resp = httpx.post(f'{base}/auth/login', data={'username': 'registrar', 'password': 'registrar123'})
registrar_token = registrar_resp.json()['access_token']
r5 = httpx.post(f'{base}/media/upload', headers={'Authorization': f'Bearer {registrar_token}'}, files={'file': ('test2.png', png_bytes, 'image/png')})
print('registrar upload:', r5.status_code, r5.json())

# Staff is rejected
staff_resp = httpx.post(f'{base}/auth/login', data={'username': 'staff', 'password': 'staff123'})
staff_token = staff_resp.json()['access_token']
r6 = httpx.post(f'{base}/media/upload', headers={'Authorization': f'Bearer {staff_token}'}, files={'file': ('test.png', png_bytes, 'image/png')})
print('staff upload attempt:', r6.status_code)
"
```

Expected: `image upload: 200 {'url': '/api/uploads/media/<uuid>.png', 'media_type': 'image'}`; `image reachable: 200 <n> bytes` (matches the PNG's byte length); `disallowed extension: 400 {...}`; `over size limit: 400 {...}`; `registrar upload: 200 {...}`; `staff upload attempt: 403`.

- [ ] **Step 9: Verify — create a media item from the uploaded URL, then delete it and confirm the file is removed**

```bash
cd bsu-registrar-queue/backend
.venv/Scripts/python.exe -c "
import httpx
from pathlib import Path

base = 'http://localhost:8000/api'
resp = httpx.post(f'{base}/auth/login', data={'username': 'admin', 'password': 'admin123'})
token = resp.json()['access_token']
headers = {'Authorization': f'Bearer {token}'}

png_bytes = bytes.fromhex('89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000a49444154789c6360000002000155a24f5a0000000049454e44ae426082')
upload = httpx.post(f'{base}/media/upload', headers=headers, files={'file': ('test.png', png_bytes, 'image/png')}).json()

create = httpx.post(f'{base}/media', headers=headers, json={
    'media_type': upload['media_type'], 'url': upload['url'], 'source': 'upload',
    'display_duration_seconds': 10, 'display_order': 0, 'is_active': True
})
print('create:', create.status_code, create.json())
item_id = create.json()['id']

file_path = Path('uploads/media') / Path(upload['url']).name
print('file exists before delete:', file_path.exists())

delete = httpx.delete(f'{base}/media/{item_id}', headers=headers)
print('delete:', delete.status_code)
print('file exists after delete:', file_path.exists())
"
```

Expected: `create: 200 {...'source': 'upload'...}`; `file exists before delete: True`; `delete: 200`; `file exists after delete: False`.

- [ ] **Step 10: Verify — replacing an uploaded item's file on edit removes the old file from disk**

```bash
cd bsu-registrar-queue/backend
.venv/Scripts/python.exe -c "
import httpx
from pathlib import Path

base = 'http://localhost:8000/api'
resp = httpx.post(f'{base}/auth/login', data={'username': 'admin', 'password': 'admin123'})
token = resp.json()['access_token']
headers = {'Authorization': f'Bearer {token}'}

png_bytes = bytes.fromhex('89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000a49444154789c6360000002000155a24f5a0000000049454e44ae426082')

upload_a = httpx.post(f'{base}/media/upload', headers=headers, files={'file': ('a.png', png_bytes, 'image/png')}).json()
create = httpx.post(f'{base}/media', headers=headers, json={
    'media_type': upload_a['media_type'], 'url': upload_a['url'], 'source': 'upload',
    'display_duration_seconds': 10, 'display_order': 0, 'is_active': True
}).json()
item_id = create['id']
file_a = Path('uploads/media') / Path(upload_a['url']).name
print('file A exists after create:', file_a.exists())

upload_b = httpx.post(f'{base}/media/upload', headers=headers, files={'file': ('b.png', png_bytes, 'image/png')}).json()
update = httpx.patch(f'{base}/media/{item_id}', headers=headers, json={
    'url': upload_b['url'], 'media_type': upload_b['media_type']
})
print('update:', update.status_code)
file_b = Path('uploads/media') / Path(upload_b['url']).name
print('file A exists after replace:', file_a.exists())
print('file B exists after replace:', file_b.exists())

httpx.delete(f'{base}/media/{item_id}', headers=headers)
print('file B exists after delete:', file_b.exists())
"
```

Expected: `file A exists after create: True`; `update: 200`; `file A exists after replace: False` (old file cleaned up); `file B exists after replace: True`; `file B exists after delete: False`.

- [ ] **Step 11: Verify — explicit-null rejection still works with the new `source` field**

```bash
cd bsu-registrar-queue/backend
.venv/Scripts/python.exe -c "
import httpx
base = 'http://localhost:8000/api'
resp = httpx.post(f'{base}/auth/login', data={'username': 'admin', 'password': 'admin123'})
token = resp.json()['access_token']
headers = {'Authorization': f'Bearer {token}'}

create = httpx.post(f'{base}/media', headers=headers, json={
    'media_type': 'image', 'url': 'https://example.com/pic.jpg', 'source': 'link',
    'display_duration_seconds': 10, 'display_order': 0, 'is_active': True
}).json()
item_id = create['id']

r = httpx.patch(f'{base}/media/{item_id}', headers=headers, json={'source': None})
print('explicit null source:', r.status_code, r.json())

httpx.delete(f'{base}/media/{item_id}', headers=headers)
"
```

Expected: `explicit null source: 422 {...}` (not `500`), confirming the existing null-rejection validator (extended to `source`) still works.

- [ ] **Step 12: Commit**

```bash
git add bsu-registrar-queue/backend/app/db_models.py \
        bsu-registrar-queue/backend/app/models/media.py \
        bsu-registrar-queue/backend/app/services/media_service.py \
        bsu-registrar-queue/backend/app/api/media.py \
        bsu-registrar-queue/backend/app/main.py \
        .gitignore
git commit -m "feat(media): add local file upload for media items"
```

---

### Task 2: Frontend — store upload action and admin form

**Files:**
- Modify: `bsu-registrar-queue/frontend/src/stores/queue.js`
- Modify: `bsu-registrar-queue/frontend/src/views/MediaAnnouncementsView.vue`

**Interfaces:**
- Consumes: Task 1's `POST /api/media/upload` and the `source` field on the existing create/update endpoints.
- Produces: `queueStore.uploadMediaFile(file)` returning `{ url, media_type }`.

- [ ] **Step 1: Add the `uploadMediaFile` store action**

In `bsu-registrar-queue/frontend/src/stores/queue.js`, change:

```js
    async fetchActiveMediaItems() {
      try {
        const response = await api.get('/media/active')
        this.activeMediaItems = response.data
        return response.data
      } catch (err) {
        this.error = err.response?.data?.detail || 'Failed to fetch active media items'
        throw err
      }
    },

    // ============ ANNOUNCEMENT ACTIONS ============
```

to:

```js
    async fetchActiveMediaItems() {
      try {
        const response = await api.get('/media/active')
        this.activeMediaItems = response.data
        return response.data
      } catch (err) {
        this.error = err.response?.data?.detail || 'Failed to fetch active media items'
        throw err
      }
    },

    async uploadMediaFile(file) {
      this.loading = true
      this.error = null
      try {
        const formData = new FormData()
        formData.append('file', file)
        const response = await api.post('/media/upload', formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
          timeout: 60000,
        })
        return response.data
      } catch (err) {
        const detail = err.response?.data?.detail
        this.error = Array.isArray(detail) ? detail.map((d) => d.msg).join('; ') : detail || 'Failed to upload file'
        throw err
      } finally {
        this.loading = false
      }
    },

    // ============ ANNOUNCEMENT ACTIONS ============
```

(The 60-second timeout override is deliberate: the store's shared axios instance has a 10-second default timeout, which is fine for small JSON requests but too short for a large video upload.)

- [ ] **Step 2: Add the Upload/Paste-URL toggle to the Media modal template**

In `bsu-registrar-queue/frontend/src/views/MediaAnnouncementsView.vue`, change:

```html
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
```

to:

```html
        <div class="px-6 py-4 space-y-4">
          <div class="flex rounded-md border border-gray-300 overflow-hidden">
            <button
              type="button"
              @click="mediaMode = 'upload'"
              class="flex-1 px-3 py-2 text-sm font-medium"
              :class="mediaMode === 'upload' ? 'bg-bsu-primary text-white' : 'bg-white text-gray-700 hover:bg-gray-50'"
            >
              Upload File
            </button>
            <button
              type="button"
              @click="mediaMode = 'link'"
              class="flex-1 px-3 py-2 text-sm font-medium"
              :class="mediaMode === 'link' ? 'bg-bsu-primary text-white' : 'bg-white text-gray-700 hover:bg-gray-50'"
            >
              Paste URL
            </button>
          </div>

          <div v-if="mediaMode === 'link'">
            <label class="block text-sm font-medium text-gray-700 mb-1">Type</label>
            <select
              v-model="mediaForm.media_type"
              class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-bsu-primary"
            >
              <option value="image">Image</option>
              <option value="video">Video (embeddable URL, e.g. YouTube /embed/ link)</option>
            </select>
          </div>

          <div v-if="mediaMode === 'link'">
            <label class="block text-sm font-medium text-gray-700 mb-1">URL</label>
            <input
              v-model="mediaForm.url"
              type="text"
              class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-bsu-primary"
              placeholder="https://..."
            />
          </div>

          <div v-else>
            <label class="block text-sm font-medium text-gray-700 mb-1">File</label>
            <input
              type="file"
              accept="image/*,video/*"
              @change="onMediaFileSelected"
              class="w-full text-sm text-gray-700 file:mr-3 file:px-3 file:py-2 file:rounded-md file:border-0 file:bg-bsu-primary file:text-white file:text-sm hover:file:bg-pink-800"
            />
            <p v-if="editingMediaId && !selectedFile" class="mt-1 text-xs text-gray-500">Leave empty to keep the current file.</p>
            <p class="mt-1 text-xs text-gray-500">Images up to 5MB (jpg, png, gif, webp); videos up to 50MB (mp4, webm, ogg).</p>
          </div>

          <div class="grid grid-cols-2 gap-4">
```

- [ ] **Step 3: Show the item's source in the Media table**

In the same file, change:

```html
              <tr v-for="item in queueStore.mediaItems" :key="item.id">
                <td class="px-4 py-4 text-sm text-gray-900 capitalize">{{ item.media_type }}</td>
                <td class="px-4 py-4 text-sm text-gray-500 max-w-xs truncate">{{ item.url }}</td>
```

to:

```html
              <tr v-for="item in queueStore.mediaItems" :key="item.id">
                <td class="px-4 py-4 text-sm text-gray-900 capitalize">{{ item.media_type }}</td>
                <td class="px-4 py-4 text-sm text-gray-500 max-w-xs">
                  <span class="block truncate">{{ item.url }}</span>
                  <span class="block text-xs text-gray-400">{{ item.source === 'upload' ? 'Uploaded file' : 'External link' }}</span>
                </td>
```

- [ ] **Step 4: Add `mediaMode`/`selectedFile` state and the file-selection handler**

In the same file's `<script setup>`, change:

```js
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
```

to:

```js
// Media state
const mediaError = ref('')
const mediaModalError = ref('')
const mediaActionLoading = ref(false)
const showMediaModal = ref(false)
const editingMediaId = ref(null)
const mediaMode = ref('link')
const selectedFile = ref(null)
const mediaForm = ref({
  media_type: 'image',
  url: '',
  display_duration_seconds: 10,
  display_order: 0,
})

const ALLOWED_IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
const ALLOWED_VIDEO_EXTENSIONS = ['.mp4', '.webm', '.ogg']
const MAX_IMAGE_SIZE = 5 * 1024 * 1024
const MAX_VIDEO_SIZE = 50 * 1024 * 1024

const validateSelectedFile = (file) => {
  const ext = '.' + (file.name.split('.').pop() || '').toLowerCase()
  const isImage = ALLOWED_IMAGE_EXTENSIONS.includes(ext)
  const isVideo = ALLOWED_VIDEO_EXTENSIONS.includes(ext)
  if (!isImage && !isVideo) {
    return `Unsupported file type '${ext}'. Allowed: images (${ALLOWED_IMAGE_EXTENSIONS.join(', ')}), videos (${ALLOWED_VIDEO_EXTENSIONS.join(', ')})`
  }
  const maxSize = isImage ? MAX_IMAGE_SIZE : MAX_VIDEO_SIZE
  if (file.size > maxSize) {
    return `File too large. Maximum size for ${isImage ? 'image' : 'video'} is ${maxSize / (1024 * 1024)}MB`
  }
  return null
}

const onMediaFileSelected = (event) => {
  const file = event.target.files[0] || null
  if (file) {
    const validationError = validateSelectedFile(file)
    if (validationError) {
      mediaModalError.value = validationError
      selectedFile.value = null
      event.target.value = ''
      return
    }
  }
  mediaModalError.value = ''
  selectedFile.value = file
}

const openCreateMediaModal = () => {
  mediaModalError.value = ''
  editingMediaId.value = null
  mediaMode.value = 'link'
  selectedFile.value = null
  mediaForm.value = { media_type: 'image', url: '', display_duration_seconds: 10, display_order: 0 }
  showMediaModal.value = true
}

const openEditMediaModal = (item) => {
  mediaModalError.value = ''
  editingMediaId.value = item.id
  mediaMode.value = item.source === 'upload' ? 'upload' : 'link'
  selectedFile.value = null
  mediaForm.value = {
    media_type: item.media_type,
    url: item.url,
    display_duration_seconds: item.display_duration_seconds,
    display_order: item.display_order,
  }
  showMediaModal.value = true
}

const saveMedia = async () => {
  if (mediaMode.value === 'link' && !mediaForm.value.url) return
  if (mediaMode.value === 'upload' && !editingMediaId.value && !selectedFile.value) {
    mediaModalError.value = 'Please choose a file to upload.'
    return
  }

  mediaActionLoading.value = true
  mediaModalError.value = ''
  try {
    let payload = { ...mediaForm.value, source: mediaMode.value }

    if (mediaMode.value === 'upload' && selectedFile.value) {
      const uploadResult = await queueStore.uploadMediaFile(selectedFile.value)
      payload = { ...payload, url: uploadResult.url, media_type: uploadResult.media_type }
    }

    if (editingMediaId.value) {
      await queueStore.updateMediaItem(editingMediaId.value, payload)
    } else {
      await queueStore.createMediaItem(payload)
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
```

- [ ] **Step 5: Start the full dev stack**

From `bsu-registrar-queue/`, run `.\dev.ps1` (or restart the frontend/backend windows if already running).

- [ ] **Step 6: Verify — upload an image and a video through the admin UI**

Log in as `admin`/`admin123`, go to `/admin/media`. Click "Add Media Item", leave it on "Upload File" mode, choose a small image file from your computer, set a duration, click Create. Confirm it appears in the table marked "Uploaded file". Repeat with a small `.mp4` video file. Confirm both entries' URLs (visible via browser dev tools or by hovering) point to `/api/uploads/media/...` and are reachable.

- [ ] **Step 7: Verify — Paste URL mode still works unchanged**

Click "Add Media Item", switch to "Paste URL", enter an external image URL, save. Confirm it appears marked "External link".

- [ ] **Step 8: Verify — editing an uploaded item without picking a new file keeps the existing file**

Edit the uploaded image item from Step 6 without selecting a new file (just change the duration) and save. Confirm the URL/source are unchanged and the file still displays correctly.

- [ ] **Step 9: Verify — client-side validation catches bad files before upload**

Try selecting a `.txt` file and an oversized file (if you have one handy) in Upload mode; confirm the modal shows a clear error immediately, without a network request, and the file input clears.

- [ ] **Step 10: Commit**

```bash
git add bsu-registrar-queue/frontend/src/stores/queue.js \
        bsu-registrar-queue/frontend/src/views/MediaAnnouncementsView.vue
git commit -m "feat(media): add upload/paste-URL toggle to the Media admin form"
```

---

### Task 3: Frontend — display panel renders uploaded videos natively

**Files:**
- Modify: `bsu-registrar-queue/frontend/src/components/MediaAnnouncementPanel.vue`

**Interfaces:**
- Consumes: the `source` field now present on every item in `queueStore.activeMediaItems` (Task 1 + Task 2).

- [ ] **Step 1: Branch video rendering on `source`**

In `bsu-registrar-queue/frontend/src/components/MediaAnnouncementPanel.vue`, change:

```html
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
```

to:

```html
        <img
          v-if="currentItem.media_type === 'image'"
          :src="currentItem.url"
          :alt="`Media item ${currentItem.id}`"
          class="w-full h-full object-contain"
        />
        <video
          v-else-if="currentItem.source === 'upload'"
          :key="currentItem.id"
          :src="currentItem.url"
          class="w-full h-full object-contain"
          autoplay
          muted
          loop
          playsinline
        ></video>
        <iframe
          v-else
          :src="currentItem.url"
          class="w-full h-full"
          frameborder="0"
          allow="autoplay; encrypted-media"
          allowfullscreen
        ></iframe>
```

The `:key="currentItem.id"` on the `<video>` element is deliberate: when rotation advances from one uploaded video to another, Vue would otherwise reuse the same `<video>` DOM element and just change its `src` attribute, which doesn't reliably restart playback of the new source in every browser. Keying by item id forces Vue to tear down and recreate the element on every rotation to a different uploaded video, so the new file always loads and autoplays correctly. `<img>` and `<iframe>` don't need this — swapping their `src` already reloads reliably.

- [ ] **Step 2: Start the full dev stack**

From `bsu-registrar-queue/`, run `.\dev.ps1` (or restart the frontend if already running).

- [ ] **Step 3: Verify — uploaded video plays natively; linked video embed still works**

With at least one uploaded video and one external-embed video (e.g. a YouTube `/embed/` link) both active, watch the display board (`/display/:id` or `/display/overview`) rotate through them. Confirm the uploaded video plays inline (native browser video player, autoplaying, muted, looping) while the external link still renders inside an `<iframe>` exactly as before.

- [ ] **Step 4: Verify — rotation between two different uploaded videos actually restarts playback**

With two different uploaded videos both active (short durations, e.g. 5-8s each, to see the rotation quickly), confirm that when rotation switches from one to the other, the new video visibly starts playing from the beginning rather than showing a frozen frame or continuing to show the previous video.

- [ ] **Step 5: Commit**

```bash
git add bsu-registrar-queue/frontend/src/components/MediaAnnouncementPanel.vue
git commit -m "feat(media): render uploaded videos natively instead of in an iframe"
```
