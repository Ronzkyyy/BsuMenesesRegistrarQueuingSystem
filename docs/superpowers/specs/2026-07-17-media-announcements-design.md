# Media & Announcements — Design Spec

**Date:** 2026-07-17
**Status:** Approved by user, ready for implementation planning

## Background

Following the "Now Serving Overview" spec (`2026-07-17-now-serving-overview-design.md`), the user wants the display boards to also show a rotating media panel (images/videos) and a scrolling text-announcement ticker, inspired by the reference video's `display board.png` screenshot (a single-queue board with a side-by-side media panel and a bottom announcement bar). This also fulfills the "Media" sidebar section that was explicitly deferred in the earlier admin-dashboard spec.

**Dependency:** this spec assumes the "Now Serving Overview" page (`frontend/src/views/DisplayOverviewView.vue`) is already implemented, so the shared media/ticker component has both real display screens to embed into from the start. Implement that spec first.

## Current State (before this change)

- No media or announcement concept exists anywhere in the backend (`db_models.py` has no such tables) or frontend.
- `AdminLayout.vue`'s sidebar currently has 3 links: Dashboard, Queue Management, User Management — the last gated to `queueStore.currentUser?.role === 'admin'` only. The router's `beforeEach` guard (`router/index.js`) has two tiers: `requiresAuth` (any authenticated role) and `requiresAdmin` (Admin only, awaiting `fetchCurrentUser()` if needed).
- `backend/app/core/init_db.py`'s `init_db()` calls `Base.metadata.create_all(bind=engine)`, which only creates tables that don't already exist — safe to re-run against the existing dev DB to pick up new models without a migration tool (this project has no Alembic wiring in practice, per prior project notes).
- Existing service/router conventions: one service class per entity in `backend/app/services/`, one Pydantic schema module per entity in `backend/app/models/`, one router module per entity in `backend/app/api/`, registered in `backend/app/api/router.py`.
- `DisplayBoardView.vue` and the (not-yet-built) `DisplayOverviewView.vue` are both dark, full-screen, TV-style display boards.

## Scope

Add:
1. Backend CRUD (Admin/Registrar-gated) + public read-only endpoints for a Media playlist and an Announcements list.
2. One combined admin page ("Media & Announcements") to manage both.
3. A shared display component embedded into both display-board screens, showing a rotating media panel and a scrolling announcement ticker.

## Design

### Backend

- **New models** (`backend/app/db_models.py`):
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
- **New Pydantic schemas**: `backend/app/models/media.py` (`MediaType` enum, `MediaItemBase`/`MediaItemCreate`/`MediaItem`/`MediaItemUpdate`), `backend/app/models/announcement.py` (`AnnouncementBase`/`AnnouncementCreate`/`Announcement`/`AnnouncementUpdate`) — following the existing `models/queue.py` pattern (Base/Create/response classes, `Config.from_attributes = True`).
- **New services**: `backend/app/services/media_service.py` (`MediaService`), `backend/app/services/announcement_service.py` (`AnnouncementService`) — each with `create`, `get_all` (admin, includes inactive), `get_active` (public, `is_active=True` ordered by `display_order`), `update`, `delete`.
- **New routers**: `backend/app/api/media.py`, `backend/app/api/announcements.py`, registered in `backend/app/api/router.py` with prefixes `/media` and `/announcements`:
  - `POST /`, `GET /` (all, incl. inactive), `PATCH /{id}`, `DELETE /{id}` — gated `require_role(UserRole.ADMIN, UserRole.REGISTRAR)`.
  - `GET /active` — public, no auth, ordered by `display_order`.
- **Table creation**: re-running `seed.py` (which calls `init_db()` unconditionally, then `seed_initial_data()` which no-ops if already seeded) against the existing dev SQLite DB creates the two new tables without affecting existing data.

### Frontend

- **`frontend/src/stores/queue.js`**: new state `mediaItems`, `announcements` (admin, all items) and `activeMediaItems`, `activeAnnouncements` (public); actions `fetchMediaItems`, `createMediaItem`, `updateMediaItem`, `deleteMediaItem`, `fetchActiveMediaItems`, and the equivalent 4 for announcements — all following the existing `loading`/`error` action pattern.
- **New admin page** `frontend/src/views/MediaAnnouncementsView.vue`: one page with two sections — a Media list (type, url, duration, order, active toggle; create/edit/delete) and an Announcements list (text, order, active toggle; create/edit/delete). Same Tailwind card/table/modal conventions as `UserManagementView.vue`.
- **Router** (`frontend/src/router/index.js`): new child route `path: 'media'`, `name: 'admin-media'`, component `MediaAnnouncementsView.vue`, `meta: { requiresRegistrarOrAdmin: true }` (new guard tier, alongside the existing `requiresAdmin`).
- **`beforeEach` guard**: add a `requiresRegistrarOrAdmin` check (parallel to the existing `requiresAdmin` block) — awaits `fetchCurrentUser()` if `currentUser` is unpopulated, redirects to `login` on failure, redirects to `admin-dashboard` if the resolved role is neither `admin` nor `registrar`.
- **`AdminLayout.vue`**: new sidebar link "Media & Announcements" → `/admin/media`, `v-if="['admin', 'registrar'].includes(queueStore.currentUser?.role)"`.
- **New shared component** `frontend/src/components/MediaAnnouncementPanel.vue`:
  - Fetches `activeMediaItems`/`activeAnnouncements` on mount and re-polls every 30 seconds (this content changes far less often than ticket state, so a slower poll than the 4-second display-board poll is appropriate).
  - Media playlist: renders the current item (`<img>` for `image` type, an embedded `<iframe>`/`<video>` for `video` type depending on URL shape), advancing to the next item after its own `display_duration_seconds`, looping back to the first after the last. Renders nothing if `activeMediaItems` is empty.
  - Announcement ticker: joins all `activeAnnouncements` texts (in `display_order`) into one continuous horizontal marquee (CSS animation, right-to-left, looping), rendered as a bottom bar. Renders nothing if `activeAnnouncements` is empty.
- **Layout integration**: both `DisplayBoardView.vue` and `DisplayOverviewView.vue` get `<MediaAnnouncementPanel />` added below their existing queue content (full width), with the ticker bar pinned to the very bottom — same layout approach on both screens, no side-by-side split.

### Error Handling

- Admin CRUD failures → inline red error box, same convention as `UserManagementView.vue`.
- Display-board panel fetch failures → panel/ticker simply don't render (fail silent, consistent with this being a non-critical decorative addition to a live public screen — the core "now serving" content must never be blocked or hidden by a media-panel error).

### Out of scope (deferred)

- File uploads / hosting media ourselves — URLs only (external images/videos, e.g. a direct image link or a YouTube embed URL).
- Scheduling windows (start/end dates/times) — only a simple on/off `is_active` flag.
- Any change to Queue Management, User Management, the Counter screen, or ticket/priority logic.

## Testing / Verification Plan

No automated test framework is configured for this project. Verification is manual, against the real running dev stack:
1. Re-run `seed.py` (or otherwise trigger `init_db()`) against the existing dev DB and confirm the two new tables exist without disturbing existing data.
2. As Admin and separately as Registrar, exercise the full CRUD flow on `/admin/media` for both media items and announcements; confirm a Staff-role login cannot see the sidebar link and is redirected away from `/admin/media` if navigated to directly.
3. Confirm `GET /api/media/active` and `GET /api/announcements/active` require no auth and only return `is_active=true` items in `display_order`.
4. On both `/display/:id` and `/display/overview`, confirm the media panel rotates through active items on their configured durations and the announcement ticker scrolls continuously; confirm both sections simply don't render when there are zero active items of that type; confirm a deliberately broken media URL doesn't break the rest of the page.
