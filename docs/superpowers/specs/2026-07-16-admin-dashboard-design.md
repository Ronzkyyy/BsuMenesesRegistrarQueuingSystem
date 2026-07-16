# Admin Dashboard Overview — Design Spec

**Date:** 2026-07-16
**Status:** Approved by user, ready for implementation planning

## Background

Continuing from the video-inspired redesign (see `2026-07-16-login-page-redesign-design.md`), the user wants to replicate the reference video's admin-side screens, adapted to our stack. Two more screenshots were captured:

- `counter interface.png` — a per-counter serving screen (Select Counter dropdown, currently-serving card with Call/Skip/Complete, two priority lanes: "Senior Citizen Queue" / "Regular Queue").
- `admin dashboard.png` — a sidebar-shell dashboard (Dashboard, Queue Management, Media, Admin Management, Audit & Logs, User Management, Reports) with a stat-tile row (Users/Services/Counters/Waiting/Serving/Skipped/Completed) and two charts (bar + pie).

These bundle multiple independent subsystems and, in the counter screen's case, a domain model (2-lane priority, a physical "Counter" entity) that doesn't match ours (3-tier Normal/Priority/Urgent, no Counter entity, service-type queues). Per user decision, this spec covers **only** the admin dashboard overview sub-project. The counter screen redesign is a separate, later spec. Media, Audit & Logs, Reports, and a separate "Admin Management" section (distinct from User Management) are deferred indefinitely — omitted from the sidebar entirely rather than shown as disabled placeholders, since they have no backend behind them.

## Current State (before this change)

- `frontend/src/views/AdminView.vue` is a single ~700-line file combining: a stats row (Active Queues/Waiting Tickets/Completed Today/No-Shows), a Queue Management section (list, pause/resume/close/delete, create-queue modal), and a Queue Display section (queue picker, currently-serving display, waiting-ticket list, Serve Next/Mark Complete buttons). It's rendered at `/admin` (behind the login/auth guard added in the prior spec).
- Its stats are computed client-side in `fetchStats()` (`AdminView.vue:531-558`) by looping over every queue and calling `GET /api/queues/{id}/stats` per queue (N+1), then reading `queueStore.queueStats.completed_today` and `.no_shows` — **these keys don't exist**. The actual backend response (`QueueService.get_queue_stats`, `backend/app/services/queue_service.py:84-133`) returns `completed` and `no_show`, both all-time totals with no date filtering. This is a pre-existing bug: those two tiles have silently always shown their default (`0`).
- No `Users` count, no charts, and no user-management UI exist anywhere in the frontend today, even though the backend already fully supports listing/creating/activating/deactivating staff accounts (`backend/app/api/auth.py`, admin-only via `require_role(UserRole.ADMIN)`).
- `TicketDB` (`backend/app/db_models.py:105-124`) has `created_at`, `served_at`, `completed_at`, `updated_at` timestamp columns and a `status` enum of `waiting/serving/completed/cancelled/no_show` — there is no "skipped" status and no "Counter" entity anywhere in the schema.
- No charting library is installed (`frontend/package.json` has only vue, vue-router, pinia, axios, date-fns, tailwindcss).
- Router (`frontend/src/router/index.js`) currently has a single `/admin` route (`meta: { requiresAuth: true }`) rendering `AdminView.vue` directly, with a global `beforeEach` guard checking `queueStore.isAuthenticated`.

## Scope

Replace `AdminView.vue` with a sidebar-shell layout (`AdminLayout.vue`) wrapping three routed pages under `/admin`:
1. **Dashboard** (new) — stat tiles + bar chart + pie chart, backed by one new aggregate backend endpoint.
2. **Queue Management** (moved, unchanged behavior) — today's queue list/CRUD, create-queue modal, and queue-display/serve-next/complete panel.
3. **User Management** (new) — staff account list/create/activate/deactivate, admin-only, using already-existing backend endpoints.

Sidebar only lists these three sections. User Management is hidden from the sidebar (and route-guarded) for non-Admin roles.

## Design

### Backend

- **New endpoint:** `GET /api/queues/dashboard-summary`, role-gated the same as the existing per-queue stats endpoint (`require_role(UserRole.ADMIN, UserRole.REGISTRAR, UserRole.STAFF)`), added to `backend/app/api/queues.py`.
- **New service method:** `QueueService.get_dashboard_summary(db)` in `backend/app/services/queue_service.py`, doing a small, fixed number of aggregate queries (not one query per queue):
  - `users_count` — `COUNT(*)` on `UserDB`.
  - `queues_count`, `active_queues_count` — `COUNT(*)` on `QueueDB`, and with `status == ACTIVE`.
  - `waiting_count`, `serving_count` — **live state**, `COUNT(*)` on `TicketDB` filtered by `status` only (not date-filtered — a ticket waiting since yesterday still counts as waiting right now).
  - **Today's cohort** — all tickets where `created_at` falls within the current UTC calendar day (`created_at >= start_of_today_utc`). One query, grouped by `status`, produces `tickets_today_by_status` (a dict: `waiting`/`serving`/`completed`/`cancelled`/`no_show` → count). `completed_today_count` and `no_shows_today_count` are read off this same dict (`tickets_today_by_status["completed"]`, `["no_show"]`) — so the tile numbers and the pie chart can never disagree.
  - `tickets_today_by_queue` — today's cohort grouped by `queue_id`, joined to queue name: a list of `{queue_id, queue_name, count}`.
- Response shape:
  ```json
  {
    "users_count": 6,
    "queues_count": 5,
    "active_queues_count": 3,
    "waiting_count": 12,
    "serving_count": 2,
    "completed_today_count": 4,
    "no_shows_today_count": 1,
    "tickets_today_by_queue": [{"queue_id": 1, "queue_name": "Enrollment", "count": 5}],
    "tickets_today_by_status": {"waiting": 3, "serving": 2, "completed": 4, "cancelled": 0, "no_show": 1}
  }
  ```

### Frontend

- **`frontend/src/components/AdminLayout.vue`** (new): sidebar with three nav links — Dashboard (`/admin`), Queue Management (`/admin/queues`), User Management (`/admin/users`, `v-if="queueStore.currentUser?.role === 'admin'"`) — plus a top bar (reusing `AppHeader`-style branding) and a `<router-view>` outlet. Logout button and "Logged in as" text move here from the old `AdminView.vue`.
- **Router (`frontend/src/router/index.js`)**: `/admin` becomes a parent route with `component: AdminLayout`, `meta: { requiresAuth: true }`, and children:
  - `''` (default) → `DashboardView.vue`
  - `'queues'` → `QueueManagementView.vue`
  - `'users'` → `UserManagementView.vue`, with additional `meta: { requiresAdmin: true }`
  - The `beforeEach` guard gains a second check: if `to.meta.requiresAdmin`, first ensure `queueStore.currentUser` is populated — if it's `null` (e.g. a fresh page load/hard refresh where the async `fetchCurrentUser()` hasn't resolved yet), `await queueStore.fetchCurrentUser()` before checking the role (wrapped so a failure here — expired token — falls through to the existing `requiresAuth` redirect-to-`/login` behavior, not a crash). Then if `queueStore.currentUser?.role !== 'admin'`, redirect to `/admin` (the dashboard) instead of `/login`.
- **`frontend/src/views/DashboardView.vue`** (new): fetches `dashboardSummary` on mount, renders 7 stat tiles (Users, Queues, Active Queues, Waiting, Serving, Completed Today, No-Shows) in the existing gradient-card style, plus:
  - A bar chart ("Tickets Today by Queue") and a pie/donut chart ("Today's Tickets by Status"), both via **Chart.js + vue-chartjs** (new dependency). Colors follow BSU branding, chosen using the project's dataviz skill at implementation time for accessible, consistent categorical color mapping.
- **`frontend/src/views/QueueManagementView.vue`** (new file): the Queue Management section and the Queue Display/serve-next/complete panel, moved verbatim from today's `AdminView.vue` (same markup, same script logic) — no behavior change. Its later replacement by a dedicated Counter screen is a separate, future spec.
- **`frontend/src/views/UserManagementView.vue`** (new): table of staff accounts (username, full name, role, active/inactive), a "Create User" form/modal (username, full name, role select, password), and Activate/Deactivate buttons per row — calling the existing `/api/auth/{register,users,users/{id}/activate,users/{id}/deactivate}` endpoints.
- **`frontend/src/stores/queue.js`**: add `fetchDashboardSummary()`, `fetchUsers()`, `createUser(userData)`, `activateUser(userId)`, `deactivateUser(userId)`.
- **Delete `frontend/src/views/AdminView.vue`** entirely — fully replaced by the layout + 3 views.
- **New dependency**: `chart.js` and `vue-chartjs` added to `frontend/package.json`.

### Error Handling

- Dashboard summary fetch failure → inline error banner on `DashboardView.vue` (same red-box style used elsewhere), stats/charts simply don't render.
- User Management actions (create/activate/deactivate) → inline error box reusing existing patterns from other admin actions in the codebase (e.g. `createQueueError` in today's `AdminView.vue`).
- A non-Admin manually navigating to `/admin/users` → silently redirected to `/admin` (dashboard) by the router guard; the sidebar never shows the link to them in the first place.

### Out of scope (deferred to future specs)

- Counter screen redesign (`counter interface.png`) — including any decision about the 2-lane priority model vs. our 3-tier model, and whether to introduce a "Counter" entity.
- Media, Audit & Logs, Reports, and a separate "Admin Management" section.
- Any change to ticket priority levels, queue types, or the student-facing flows.

## Testing / Verification Plan

No automated test framework is configured for this project (backend or frontend) — consistent with the prior spec's convention. Verification is manual, against the real running stack:
1. Start the dev stack (`dev.ps1`).
2. Hit `GET /api/queues/dashboard-summary` directly (curl, as Admin) and confirm the response shape and that `completed_today_count`/`no_shows_today_count` match manually-verified ticket data (e.g. via seed data or freshly created/completed test tickets).
3. Log in as Admin → land on `/admin` → confirm sidebar shows all 3 links, Dashboard tiles and both charts render with real numbers.
4. Navigate to `/admin/queues` → confirm all existing Queue Management functionality (pause/resume/close/delete, create queue, serve next/complete) still works unchanged.
5. Navigate to `/admin/users` → confirm staff list renders, create/activate/deactivate work end-to-end against the real backend.
6. Log in as Staff or Registrar → confirm the User Management sidebar link is absent, and confirm manually navigating to `/admin/users` redirects back to `/admin`.
