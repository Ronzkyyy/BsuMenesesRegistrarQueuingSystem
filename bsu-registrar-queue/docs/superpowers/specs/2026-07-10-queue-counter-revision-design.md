# Queue Counter Revision — Design Spec

Date: 2026-07-10

## 1. Goal

Revise the BSU Registrar Queue System to cover this set of features:

1. Public TV/monitor display board showing the current serving number and succeeding numbers in line.
2. A registrar staff counter interface for managing transactions efficiently.
3. Marking a transaction complete automatically triggers the next queue number.
4. Skip and recall functions for students with incomplete requirements or who need to return later.
5. Real-time handling of walk-in transactions at the registrar's office.
6. A separate queue for Persons with Disabilities (PWDs) and senior citizens.

Features 1 (now-serving + waiting list) and, partially, 2 (a serve/complete control) already exist (`DisplayBoardView.vue`, `AdminView.vue`'s "Queue Display" section). This spec covers what's missing or needs revision: a dedicated counter interface, auto-advance, skip/recall, walk-in ticket issuance at the counter, a PWD/senior priority lane, and display-board updates (audio cues, recalled-ticket badge).

## 2. Data model changes

**`TicketDB` (and `Ticket` / `TicketPublic` schemas):**
- New column `skip_count: int` (default `0`). Incremented each time a ticket is skipped.
- New computed/exposed field `was_skipped: bool` = `skip_count > 0`, added to `Ticket` and `TicketPublic` so both staff and public views can badge a ticket that was previously skipped and is now being served again (a "recall", whether reached via the explicit Recall action or by naturally coming back up in the waiting order).

No new `TicketDBStatus` value is introduced. A skipped ticket is simply a `WAITING` ticket with `skip_count > 0` — it resurfaces through normal serving once its (adjusted) position comes up, or staff can jump to it directly via Recall.

**`QueueDB` (and `Queue` / `QueueCreate` schemas):**
- New column `is_priority_lane: bool` (default `False`). Marks a queue as a dedicated PWD/senior-citizen express lane. No new `QueueDBType` value — a priority lane is created the same way as any other queue (same `queue_type`, e.g. `document_request`), just with this flag set. Admin creates it explicitly via the existing "Create Queue" flow, same as any regular queue for that service.

**Migration:** one new Alembic revision adding `tickets.skip_count` and `queues.is_priority_lane`, both with server defaults so existing rows are unaffected.

## 3. Backend service logic

**Correctness fix (prerequisite):** `TicketService.serve_next_ticket()` currently orders candidates by `priority DESC, created_at ASC`, ignoring the `position` field. Every place that assigns `position` (ticket creation, serve, cancel) already keeps it priority-consistent, so this is switched to order by `position ASC` (tie-broken by `created_at ASC`). This is required for skip's "reinsert N slots back" to actually change serve order rather than being purely cosmetic.

**`skip_ticket(ticket_id)`** (new):
- Ticket must be `SERVING`, else 400.
- Reinsert it into the `WAITING` list `SKIP_REINSERT_OFFSET = 3` positions back (a fixed constant, not per-queue configurable): it ends up behind the next 3 waiting tickets (or at the end if fewer than 3 are waiting). Positions of the affected tickets shift to make room; `estimated_wait_time_minutes` is recalculated for all shifted tickets.
- `skip_count += 1`, status → `WAITING`.
- Auto-advance: immediately calls `serve_next_ticket()` for the same queue afterward.
- Returns the skipped ticket (now `WAITING`).

**`recall_ticket(ticket_id)`** (new):
- Ticket must be `WAITING`, else 400.
- If another ticket is currently `SERVING` in the same queue, that ticket is bumped back to the front of `WAITING` (position 1, `served_at` cleared) rather than losing its place — it will be served next.
- The recalled ticket becomes `SERVING` (`served_at` set to now).
- Returns the recalled ticket (now `SERVING`).

**`mark_completed(ticket_id)`** (revised):
- Unchanged completion logic, but now also calls `serve_next_ticket()` for the ticket's queue at the end (auto-advance). No-ops silently if nothing is waiting.

## 4. API surface

- `POST /api/tickets/{id}/skip` — staff-only (`Admin`/`Registrar`/`Staff`). Returns `Ticket`.
- `POST /api/tickets/{id}/recall` — staff-only. Returns `Ticket`.
- Existing `POST /api/tickets/{id}/complete` — unchanged request/response shape; auto-advance is an internal side effect.
- Existing `POST /api/queues` / queue schemas gain `is_priority_lane`.
- **Walk-in issuance needs no new endpoints** — it's a Counter-view UI flow built from the existing public endpoints (`GET /api/students/search`, `POST /api/students`, `POST /api/tickets`), which the frontend already knows how to drive (see `QueueDetailView.vue`).

## 5. Frontend

**New `CounterView.vue`** (route `/counter`) — the dedicated staff screen for working a queue:
- Uses a new shared `StaffLoginForm.vue` component (extracted from `AdminView.vue`, which currently inlines this markup/logic) if not authenticated.
- Queue selector.
- "Currently Serving" panel: ticket number, priority/lane badge, student name and purpose (staff-only detail — unlike the public board), with **Complete**, **Skip**, and **No-show** actions.
- **Serve Next** action for the idle state (nothing currently serving, e.g. start of a session).
- "Previously Skipped" panel: waiting tickets in the selected queue with `was_skipped`, each with a **Recall** button.
- "Register Walk-in" panel: student-ID search → register-if-not-found → take ticket, reusing the same store actions `QueueDetailView.vue` already uses (`searchStudent`, `registerStudent`, `takeTicket`).
- Polls the queue's ticket state on an interval (consistent with existing polling patterns elsewhere in the app).
- Header link to/from `AdminView.vue`.

**`AdminView.vue` (trimmed):**
- Remove the existing inline "Serve Next Ticket" / "Mark Complete" buttons in the Queue Display section — this logic now lives solely in `CounterView` (avoids two divergent implementations of ticket serving, one of which wouldn't know about skip/recall/auto-advance).
- Keep queue CRUD, stats, login (via the extracted `StaffLoginForm`), and the existing "Display Board" link.
- Add an "Open Counter" link per queue, and an "Priority Lane" checkbox to the Create Queue modal.

**`DisplayBoardView.vue`:**
- Badge a serving ticket "Recalled" when `was_skipped` is true.
- One-time "Enable Sound" button overlay (needed due to browser autoplay-audio restrictions — unlocks audio on a user gesture).
- On serving-ticket change: play a short two-tone chime via the Web Audio API (`OscillatorNode`, no binary asset files) and, if `speechSynthesis` is available, speak "Now serving number X" (or "Recalling number X" when `was_skipped`). Both gracefully no-op if unsupported/blocked.
- Show a "Priority Lane" badge in the header when the queue is a PWD/senior lane.

**`DisplayIndexView.vue` / `QueuesView.vue`:**
- Priority-lane queues get a distinguishing badge/icon in the listing. No structural changes otherwise.

## 6. Explicitly out of scope

- No per-queue configurable skip offset — fixed at 3.
- No multi-counter/multi-window modeling per queue (one "currently serving" slot per queue, as today).
- No automatic routing/detection of PWD/senior status on students — a priority lane is just another queue the student (or staff, for walk-ins) picks explicitly, same as choosing any other service.
- No new `is_pwd` / `is_senior_citizen` fields on the student profile — not needed since routing is queue-selection-based, not student-attribute-based.
- No change to the existing `no_show` flow (timeout-based, terminal) — skip/recall is a distinct, non-terminal mechanism for "not ready yet, will come back."

## 7. Verification notes

Per project convention ([[feedback-verify-with-real-stack]] equivalent guidance), these changes should be exercised against the real local stack (`dev.ps1`, SQLite), not just type-checked — skip/recall position math and auto-advance are exactly the kind of data-flow logic that looks right by inspection but needs to be driven end-to-end (create several tickets with different priorities, skip one, confirm it reappears 3 slots back and gets served in the right order; confirm recall bumps the current ticket back to the front instead of losing it).
