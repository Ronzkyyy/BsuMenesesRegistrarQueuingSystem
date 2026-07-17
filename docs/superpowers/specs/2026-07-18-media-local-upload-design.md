# Local Media Upload — Design Spec

**Date:** 2026-07-18
**Status:** Approved by user, ready for implementation planning

## Background

The Media & Announcements feature (`2026-07-17-media-announcements-design.md`) shipped with URL-only media items — an admin pastes a link to an image or an iframe-embeddable video (e.g. a YouTube `/embed/` link). That spec explicitly deferred file uploads: *"File uploads / hosting media ourselves — URLs only... Deferred."* The user now wants to add a file directly from their computer instead of always needing an externally-hosted URL.

## Current State (before this change)

- `MediaItemDB` (`backend/app/db_models.py`) has `media_type` (`image`/`video`), `url`, `display_duration_seconds`, `display_order`, `is_active` — no concept of where the URL came from.
- `MediaAnnouncementPanel.vue` renders `image` items as `<img>` and `video` items as `<iframe>` unconditionally — this assumes every video is an external embeddable link. A raw uploaded video *file* cannot play inside an `<iframe>`; it needs a native `<video>` element.
- `MediaAnnouncementsView.vue`'s create/edit modal has a single URL text input for both media types.
- The frontend dev proxy (`frontend/vite.config.js`) only forwards `/api/*` to the backend (`http://localhost:8000`) — nothing else is proxied. `backend/app/main.py` mounts the API router at `/api` and has no static file serving today.
- No file storage of any kind exists in this project (SQLite/Postgres DB only, no upload directories, nothing in `.gitignore` related to uploads).

## Scope

Let Admin/Registrar staff upload an image or video file from their own computer as an alternative to pasting a URL, for both create and edit. Uploaded files are stored on the backend's local disk and served back through the existing `/api` path so no new proxy configuration is needed in dev or production. Keep the existing "paste a URL" path working unchanged, side-by-side with the new upload path.

## Design

### Backend

- **Schema change** (`MediaItemDB`): add `source = Column(Enum(MediaDBSource), default=MediaDBSource.LINK, nullable=False)` where `MediaDBSource` is a new `str` enum with values `UPLOAD` / `LINK`. Existing rows (all created via URL so far) default to `LINK`, preserving current behavior exactly.
- **New endpoint** `POST /api/media/upload` (Admin/Registrar-gated, `multipart/form-data`, one `file` field):
  - Validates file extension against an allowlist: images `.jpg`, `.jpeg`, `.png`, `.gif`, `.webp`; videos `.mp4`, `.webm`, `.ogg`. Anything else → `400`.
  - Validates size: images ≤ 5 MB, videos ≤ 50 MB. Over the limit → `400`.
  - Media type (`image`/`video`) is derived from the validated extension — the client doesn't need to declare it separately.
  - Saves the file to `backend/uploads/media/<uuid4><original-extension>` (random filename avoids collisions and path-traversal from a hostile original filename).
  - Returns `{"url": "/api/uploads/media/<filename>", "media_type": "image"|"video"}`. This endpoint only stores the file and reports back where it landed — it does **not** create a `MediaItemDB` row itself. The client then calls the existing `POST /api/media` (or `PATCH /api/media/{id}`) with that `url`, the reported `media_type`, and `source: "upload"`, exactly as it would for a pasted URL. This keeps upload and CRUD as separate, composable steps rather than one large endpoint.
- **Static file serving**: mount `backend/uploads/` at `/api/uploads` in `main.py` via FastAPI's `StaticFiles` — placing it under `/api` (rather than a bare `/uploads`) is what makes it reachable through the frontend's existing `/api` dev-proxy rule and whatever reverse-proxy rule fronts `/api` in production, without adding a second proxy path anywhere.
- **Delete cleanup**: `MediaService.delete()` — if the item's `source == UPLOAD`, best-effort-delete the file at the stored path from disk (wrapped so a missing/already-gone file doesn't fail the DB delete).
- **Replace-on-edit cleanup**: `MediaService.update()` — if the item's `source == UPLOAD` and the `url` is being changed (i.e. the admin uploaded a replacement file during edit), best-effort-delete the *old* file from disk after the DB row is updated to the new URL, so replaced uploads don't accumulate orphaned files.
- **New directory**: `backend/uploads/` (and its `media/` subfolder, created on first upload via `os.makedirs(..., exist_ok=True)`) is added to `.gitignore` — uploaded content is runtime data, not source.

### Frontend

- **`stores/queue.js`**: new action `uploadMediaFile(file)` — `POST /api/media/upload` with a `FormData` body (`multipart/form-data`, not JSON), returns `{ url, media_type }`.
- **`MediaAnnouncementsView.vue`**: the Media modal gains a source toggle — "Upload File" vs. "Paste URL" (radio buttons or a two-tab toggle), defaulting to whichever mode matches the item being edited (or "Paste URL" for a brand-new item, matching today's default behavior).
  - **Paste URL mode**: unchanged — the existing `url` text input, `media_type` select, `source` implicitly `"link"`.
  - **Upload File mode**: a native `<input type="file" accept="image/*,video/*">`. On save: first call `uploadMediaFile(file)` to get `{ url, media_type }`, then call the existing `createMediaItem`/`updateMediaItem` with `{ url, media_type, source: "upload", display_duration_seconds, display_order }`. If editing an existing upload without picking a new file, the existing `url`/`media_type`/`source` are resubmitted unchanged (no re-upload).
  - Client-side validation mirrors the backend's limits (extension allowlist, 5 MB/50 MB size caps) so obviously-invalid files are rejected before a network round-trip, with the backend as the authoritative check either way.
- **`MediaAnnouncementPanel.vue`** (display boards): rendering branches on both `media_type` and `source` now:
  - `media_type === 'image'` → `<img>` (unchanged, works identically for uploaded and linked images since both are just a URL).
  - `media_type === 'video' && source === 'upload'` → native `<video :src="url" autoplay muted loop playsinline>` (a real, locally-hosted file the browser can play directly).
  - `media_type === 'video' && source === 'link'` → `<iframe>` (unchanged, for externally-hosted embeds like YouTube).

### Error Handling

- Upload rejected for bad extension or over size limit → `400` with a specific detail message; the admin form surfaces this the same way it surfaces any other create/update error today (inline red error box in the modal).
- Upload succeeds but the subsequent create/update call fails → the uploaded file is already on disk but orphaned (no DB row references it). This is an accepted, low-stakes edge case for this project's scale — no automatic rollback/cleanup is built for it, consistent with YAGNI (an admin can just re-attempt the save; a stray unreferenced file on disk has no functional impact).

### Out of scope (deferred)

- Cloud/object storage (S3-like) — local disk only, matching this project's existing local-first scale.
- Any change to the "paste a URL" path's existing behavior or schema fields beyond adding `source`.
- Automatic cleanup of orphaned files from a failed create/update after a successful upload (see Error Handling above).
- Any change to Queue Management, User Management, Dashboard, or the Counter screen.

## Testing / Verification Plan

No automated test framework is configured for this project. Verification is manual, against the real running dev stack:
1. Confirm the new `source` column appears after re-running `seed.py` against the existing dev DB, and that pre-existing media rows read back with `source: "link"`.
2. Upload a valid image and a valid video via the new endpoint (as Admin and separately as Registrar); confirm both are saved to disk under `backend/uploads/media/` and the returned URL is reachable at `http://localhost:8000/api/uploads/media/<filename>` (and via the frontend dev server's proxied `/api/uploads/...` path).
3. Attempt an upload with a disallowed extension and one over the size limit; confirm both are rejected with `400` and a clear message.
4. Create a media item from an uploaded image and one from an uploaded video via the admin page; confirm both appear correctly in the admin table and, on a display board, the image renders in `<img>` and the video plays in a native `<video>` element (not an iframe).
5. Confirm the existing "Paste URL" flow (including an external video embed link) still works exactly as before.
6. Delete an uploaded media item; confirm its file is removed from `backend/uploads/media/`. Edit an uploaded item with a new file; confirm the old file is removed and the new one is served.
7. As Staff, confirm the upload endpoint is rejected with `403`, consistent with every other Media/Announcement mutation endpoint.
