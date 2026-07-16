# Login Page Redesign — Design Spec

**Date:** 2026-07-16
**Status:** Approved by user, ready for implementation planning

## Background

The user found a PHP "Queuing System" tutorial video (YouTube, "Queuing System using PHP" by RealJupi) whose login screen they want to replicate visually and functionally in our existing BSU Registrar Queue System, keeping our current tech stack (FastAPI + Vue 3 + Pinia + Tailwind + PostgreSQL). The video's login screen was captured as a screenshot (`log in interface.png`) showing:

- Centered white card on a light-gray background, with soft blurred lavender blob decorations
- A circular gradient icon above the title
- Title "Queuing System" (purple/indigo) + subtitle "Enter your credentials to continue"
- Username field, Password field (with show/hide eye toggle)
- A "Select Portal" dropdown with options: Admin, Counter, Display
- A "Back to Home" text link

Three other screenshots were also saved (`counter interface.png`, `display board.png`, `admin dashboard.png`) for later follow-up work — **out of scope for this spec**, which covers only the login screen.

## Current State (before this change)

- No dedicated `/login` route exists. The login form is embedded inline at the top of `frontend/src/views/AdminView.vue` (lines ~19–74), toggling with `queueStore.isAuthenticated`.
- Roles: `Admin > Registrar > Staff` (`UserRole` enum in `backend/app/db_models.py`).
- `POST /api/auth/login` (`backend/app/api/auth.py`) takes `OAuth2PasswordRequestForm` (username/password only) and returns a JWT with `sub`, `role`, `user_id`.
- The Display board (`/display`, `/display/:id`) is public, no authentication.
- `AdminView.vue` is a single unified dashboard for all authenticated roles — there is no separate Admin vs. Counter dashboard yet.
- Brand colors are defined in `frontend/tailwind.config.js`: `bsu.primary` (#be185d, maroon/pink), `bsu.gold` (#f59e0b). Real BSU + Meneses Campus logos exist at `frontend/src/assets/BSUlogo.png` and `frontend/src/assets/MENESESlogo.png`, already used in `AppHeader.vue`.

## Scope

Build a standalone `/login` page matching the video's layout and interaction pattern, recolored to BSU branding, wired into the existing auth flow. The Admin/Counter dashboard split (implied by the video's portal picker) is explicitly deferred — for this change, **both** "Admin" and "Counter" portal selections redirect to the existing unified `/admin` route after successful, validated login. The "Display" portal option from the video is dropped from the dropdown since our Display board stays public/no-auth; a "View Display Board" link will be added to the login page instead.

## Design

### Frontend

- **New `frontend/src/views/LoginView.vue`**, route `/login`:
  - Centered white rounded card, shadowed, on a light-gray background with two soft blurred blob shapes using `bsu-primary`/`bsu-gold` tints (replacing the video's lavender).
  - BSU logo + Meneses Campus logo (reused from `assets/`) displayed where the video had its generic gradient icon.
  - Title: "BSU Registrar Queue System", subtitle "Enter your credentials to continue".
  - Fields: Username (text input), Password (password input with show/hide eye-icon toggle using a local `ref`).
  - "Select Portal" dropdown with two options: **Admin**, **Counter** (no "Display").
  - Inline error box (reusing the existing red error-box style from `AdminView.vue`) for login failures.
  - "Back to Home" link (`router-link` to `/`) and a "View Display Board" link (`router-link` to `/display`).
  - Submits username/password/portal to the store's login action; on success, redirects to `/admin`; on failure, shows the inline error without navigating.

- **Router (`frontend/src/router/index.js`)**:
  - Add `{ path: '/login', name: 'login', component: () => import('../views/LoginView.vue') }`.
  - Add `meta: { requiresAuth: true }` to the `/admin` route.
  - Add a global `router.beforeEach` guard: if `to.meta.requiresAuth` and the Pinia store has no valid authenticated session, redirect to `/login`.

- **`AdminView.vue`**: remove the embedded login form block; the view now assumes an authenticated session (guard handles the unauthenticated case). No change to the dashboard content itself.

- **Pinia `stores/queue.js`**: reuse existing login/logout/auth state. Add a session-restore step on app bootstrap if not already present (read persisted token, call `/api/auth/me` to repopulate `currentUser`), so the router guard has something to check on a hard refresh.

### Backend

- **`POST /api/auth/login`** (`backend/app/api/auth.py`): accept an additional optional `portal: str | None = Form(None)` field alongside the existing `OAuth2PasswordRequestForm`.
  - Validation, applied *before* issuing a token:
    - `portal == "admin"` → requires `user.role == UserRole.ADMIN`, else `403` with detail `"This account does not have Admin portal access."`
    - `portal == "counter"` → allowed for any role (Admin, Registrar, Staff) — no restriction.
    - `portal` omitted → no portal validation (backward compatible).
  - Existing checks (401 bad credentials, 400 inactive account) remain unchanged and take precedence over the portal check.

### Error Handling

| Condition | Response | UI behavior |
|---|---|---|
| Bad username/password | `401` (existing) | Inline red error, same styling as current |
| Inactive account | `400` (existing) | Inline red error, same styling as current |
| Portal mismatch (e.g. non-admin selecting Admin) | `403` (new) | Inline red error, distinct message |
| Success | `200` + JWT (existing) | Redirect to `/admin` |

No token is issued on any failure path.

### Out of scope (deferred to follow-up specs)

- Splitting `/admin` into separate Admin and Counter dashboards (screenshots `admin dashboard.png` and `counter interface.png`).
- Any change to the Display board (`display board.png`).
- Automated tests (no test framework is currently configured per project `CLAUDE.md`; verification will be manual against the running dev stack).

## Testing / Verification Plan

No test framework is configured for this project. Verification will be manual, against the real running stack (per prior guidance to verify against the real backend+DB rather than mocks):
1. Start backend (`uvicorn`) + frontend (`npm run dev`) + PostgreSQL.
2. Navigate to `/admin` while logged out → confirm redirect to `/login`.
3. Log in as an Admin user with portal="Counter" and portal="Admin" → both succeed, land on `/admin`.
4. Log in as a Staff/Registrar user with portal="Admin" → expect 403 inline error.
5. Log in as a Staff/Registrar user with portal="Counter" → succeeds.
6. Bad credentials → existing inline error still works.
7. "Back to Home" and "View Display Board" links navigate correctly.
