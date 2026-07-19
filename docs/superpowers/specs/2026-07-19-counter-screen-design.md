# Counter Screen — Design Spec

**Date:** 2026-07-19
**Status:** Approved by user, ready for implementation planning

## Background

The reference video's `counter interface.png` screen showed a dedicated staff "serving" screen: a counter picker, a large currently-serving ticket card with Call/Skip/Complete actions, and two waiting lanes split by priority (Senior Citizen / Regular). This was deferred from the very first admin-dashboard spec, since the reference's domain model doesn't map directly onto ours — it assumes a physical "Counter" entity and a single combined queue split into two priority lanes, whereas our system has multiple queue *types* (Enrollment, Document Request, Clearance, Scholarship, Others), each already ordered by a 3-tier priority (Normal/Priority/Urgent), and no "Counter" entity at all.

Per user decisions during brainstorming, this spec adapts the reference's *interaction pattern* (a focused screen with Call/Skip/Complete) onto our existing architecture, without introducing a new "Counter" entity or restructuring the priority/queue-type model.

## Current State (before this change)

- `frontend/src/views/QueueManagementView.vue` has an embedded "Queue Display" panel: a queue picker, a "Currently Serving" display, a waiting-ticket list, and Serve Next Ticket / Mark Complete buttons. This is admin-facing (lives under Queue Management) and stays completely unchanged by this spec — both it and the new screen can serve tickets.
- `POST /api/tickets/{ticket_id}/no-show` (backend/app/api/tickets.py) already exists, gated `require_role(UserRole.ADMIN, UserRole.REGISTRAR, UserRole.STAFF)`, calling `TicketService.mark_no_show` — but no frontend UI anywhere calls it today.
- `POST /api/tickets/{ticket_id}/serve` and `POST /api/tickets/{ticket_id}/complete` exist and are used by `QueueManagementView.vue`'s existing panel (via `serveNextTicket`/`completeTicket` store actions, which call `POST /api/tickets/queue/{id}/next` and `POST /api/tickets/{id}/complete` respectively).
- `TicketDB` (backend/app/db_models.py) has `id, ticket_number, student_id, queue_id, priority, purpose, status, position, estimated_wait_time_minutes, served_at, completed_at, created_at, updated_at` — no `called_at` field.
- `TicketPublic` (backend/app/models/ticket.py), returned by `GET /api/tickets/queue/{id}/display`, has `ticket_number, queue_name, position, status, estimated_wait_time_minutes, created_at` — no `called_at` field. This is what `DisplayBoardView.vue` (the single-queue display board) polls every 4 seconds.
- `frontend/src/components/AdminLayout.vue` sidebar currently has: Dashboard, Queue Management, Media & Announcements (Admin/Registrar only), User Management (Admin only).
- Priority badges (Priority = yellow/gold, Urgent = red, Normal = no badge) are already a established visual convention in `QueueManagementView.vue`'s waiting-ticket list and `QueueDetailView.vue`.
- No audio of any kind exists anywhere in this project; no audio asset files exist.

## Scope

Add a new, dedicated staff screen ("Counter") for actively serving tickets: pick a queue, see the currently-serving ticket with Call/Skip/Complete actions, and a single priority-ordered waiting list. Add a lightweight "Call" signal (a timestamp) that the single-queue public display board picks up on its next poll to briefly pulse and chime, drawing attention to the currently-serving number. No new database entities beyond one new column; no changes to priority calculation, queue types, or the existing Queue Management panel.

## Design

### Backend

- **New column**: `TicketDB.called_at = Column(DateTime(timezone=True), nullable=True)` (backend/app/db_models.py).
- **New endpoint** `POST /api/tickets/{ticket_id}/call` (backend/app/api/tickets.py), gated `require_role(UserRole.ADMIN, UserRole.REGISTRAR, UserRole.STAFF)` — same roles as `/serve`, `/complete`, `/no-show`. Sets `called_at = datetime.now(timezone.utc)` on the ticket via a new `TicketService.call_ticket(ticket_id)` method, commits, returns the updated `Ticket`. Does not touch `status`, `position`, or anything else — purely a "someone clicked Call" timestamp.
- **`TicketPublic`** (backend/app/models/ticket.py) gains `called_at: Optional[datetime] = None`. `TicketService.get_queue_display` (used by `GET /api/tickets/queue/{id}/display`) includes `called_at` in the `TicketPublic` it constructs for each ticket, so the display board can see it.
- **"Skip"** on the new Counter screen calls the existing `POST /api/tickets/{ticket_id}/no-show` endpoint directly — no backend change needed there.

### Frontend

- **`frontend/src/stores/queue.js`**: new action `callTicket(ticketId)` (`POST /tickets/{id}/call`), following the existing action pattern. `markNoShow` already exists as a store action (confirmed in the codebase) and will be reused as-is for "Skip".
- **New `frontend/src/views/CounterView.vue`**, at route `/admin/counter`:
  - A queue picker (dropdown of active queues), matching the existing pattern in `QueueManagementView.vue`.
  - **Currently Serving card**: ticket number (large), queue name, a priority badge (Priority/Urgent only, matching the existing visual convention — no badge for Normal), and three buttons: **Call** (calls `callTicket`, no local status change, just a brief "Called" confirmation flash on the button itself), **Skip** (calls `markNoShow` on the serving ticket, then clears the local "currently serving" state so staff can Serve Next again), **Complete** (calls the existing `completeTicket` action, same as today's Queue Management panel).
  - **Waiting list**: a single list ordered by position (already correctly priority-ordered by the backend), each row showing ticket number, a Priority/Urgent badge where applicable, and estimated wait — same data/shape already used by `QueueManagementView.vue`'s waiting list and `fetchQueueDisplay`/`queueDisplay`.
  - A "Serve Next Ticket" action (reusing the existing `serveNextTicket` store action) to pull the next ticket into the Currently Serving card when nothing is currently being served.
- **`frontend/src/router/index.js`**: new child route under `/admin`: `path: 'counter'`, `name: 'admin-counter'`, component `CounterView.vue` — **no `requiresAdmin`/`requiresRegistrarOrAdmin` meta** (unrestricted, same access level as Dashboard/Queue Management: any authenticated Admin/Registrar/Staff).
- **`frontend/src/components/AdminLayout.vue`**: new sidebar link "Counter" between Queue Management and Media & Announcements, visible to all authenticated roles (no `v-if` role gate, matching Dashboard/Queue Management's existing unconditional links).
- **`frontend/src/views/DisplayBoardView.vue`** (single-queue board only — the all-queues overview page is explicitly out of scope for the Call effect): on each poll (`fetchQueueDisplay`, already running every 4 seconds), compare the serving ticket's `called_at` against the previously-seen value for that same ticket. If it changed (a new, later timestamp), trigger:
  - A brief CSS pulse/flash animation on the "Now Serving" number (a few seconds, then settles back to the existing steady `animate-pulse-slow`).
  - A short audio chime, synthesized on the fly via the Web Audio API (`AudioContext` + `OscillatorNode`, a couple hundred milliseconds, no new binary asset file needed) — sidesteps the autoplay-policy concern for pre-recorded audio, since generating a `AudioContext` sound in response to accumulated user interaction on the page (e.g., the fullscreen toggle button, or simply that most kiosk displays have had at least one earlier interaction) is treated the same as playing a media file for autoplay-policy purposes; if the very first poll after page load happens to include a `called_at` before any user interaction, the browser may block that one chime (silently, no error) — acceptable for a "nice to have" audio cue, not treated as a bug.

### Error Handling

- `Call`/`Skip`/`Complete`/`Serve Next` failures on the Counter screen surface the same way existing similar actions do elsewhere: an inline red error box, same Tailwind convention as `QueueManagementView.vue`.
- A missing/blocked audio chime (browser autoplay policy) fails silently — the visual pulse still happens regardless, so the core "you're being called" signal is never entirely lost.

### Out of scope (deferred)

- Any new "Counter" (physical station) entity, counter assignment, or per-counter login.
- Splitting waiting tickets into separate visual lanes by priority (single ordered list with badges instead).
- The Call pulse/chime appearing on the all-queues overview page (`/display/overview`).
- Removing or changing the existing Queue Management "Queue Display" serving panel.
- Any change to priority calculation, queue types, or ticket numbering format.

## Testing / Verification Plan

No automated test framework is configured for this project. Verification is manual, against the real running dev stack:
1. Confirm the new `called_at` column exists after re-running `seed.py` (or recreating the dev DB, same caveat as prior schema-adding features on this project).
2. As each of Admin, Registrar, and Staff, open `/admin/counter`, pick a queue, Serve Next, then exercise Call, Skip, and Complete; confirm each does what's described and that Skip correctly moves the skipped ticket to No-Show status (visible via the existing admin ticket views) rather than Completed.
3. With the Counter screen and the single-queue display board (`/display/:id`) for the same queue open side by side, click Call and confirm the display board pulses and chimes within one poll cycle (~4 seconds). Confirm the all-queues overview page (`/display/overview`) does NOT pulse/chime for the same event.
4. Confirm the existing Queue Management "Queue Display" panel still works completely unchanged, and that serving a ticket from either screen is reflected correctly on the other (both read from the same backend state).
