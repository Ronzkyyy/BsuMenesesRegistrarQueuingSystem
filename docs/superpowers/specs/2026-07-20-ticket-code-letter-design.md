# Ticket Code Letter Prefix — Design Spec

**Date:** 2026-07-20
**Status:** Approved by user, ready for implementation planning

## Background

The reference PHP queuing system that originally inspired this project's UI used letter-prefixed ticket numbers (e.g. "E-007") rather than plain integers. This was raised earlier in the project and deliberately deferred ("we can add it on the next projects") while a display bug was investigated first. The user has now asked to revisit it: give each queue's tickets a letter prefix based on the queue's "transaction" (service) identity, so a ticket reads as e.g. `E-007` instead of a bare `7`.

During brainstorming, a real edge case surfaced: if the letter were derived from the fixed `queue_type` enum (Enrollment→E, Document Request→D, Clearance→C, Scholarship→S, Others→O), two queues sharing the same `queue_type` (nothing stops an admin from creating two "Enrollment" queues today) would each run independent ticket counters and could both mint `E-001`, `E-002`, etc. simultaneously. The user's resolution: make the letter a property of the individual queue, not the queue type, so distinct queues can be given distinct letters even if they share a type.

## Current State (before this change)

- `QueueDB` (`backend/app/db_models.py:25-38`) has no per-queue "letter" or "code" field. `current_ticket_number` (line 36) is a plain integer counter, incremented per-queue by `TicketService._get_next_ticket_number` (`backend/app/services/ticket_service.py:151-158`).
- `Ticket` and `TicketPublic` (`backend/app/models/ticket.py`) expose `ticket_number: int` with no formatting; nothing else combines it with any queue identity for display.
- `TicketService.get_now_serving_overview` (`backend/app/services/ticket_service.py:429-457`) independently builds plain dicts (not through `Ticket`/`TicketPublic`) containing `serving_ticket_numbers` and `next_ticket_number`, both raw ints pulled directly from `t.ticket_number`.
- Six frontend files render `ticket_number` directly today: `DisplayBoardView.vue`, `DisplayOverviewView.vue`, `CounterView.vue`, `QueueManagementView.vue`, `QueueDetailView.vue`, and `QueuesView.vue`.
- There is **no "Edit Queue" feature anywhere in the app** — the Queue Management screen (`frontend/src/views/QueueManagementView.vue`) only has a Create Queue modal (lines 197-289) plus separate pause/resume/close status actions (`backend/app/api/queues.py:74-131`). Every queue field (name, type, description, capacity, slot duration, priority toggle) is set once at creation and is not editable afterward. This spec follows that existing precedent rather than introducing queue editing as a side effect.
- No uniqueness constraint exists today on `queue_type`, `name`, or anything else that would prevent two queues from colliding in any way — plain `ticket_number` values already collide across different queues today (e.g., "Ticket #1" can exist simultaneously in both the Enrollment and Clearance queues), distinguished only by which queue's screen you're viewing.
- The 5 currently-seeded queues (`backend/app/core/init_db.py:32-71`): Enrollment (type `ENROLLMENT`), Document Request (type `DOCUMENT_REQUEST`), Clearance (type `CLEARANCE`), Scholarship (type `SCHOLARSHIP`), General Inquiry (type `OTHERS` — note the name doesn't start with the same letter as its type).
- No automated test framework is configured for this project; verification is manual against the real running dev stack, per every prior feature in this project's history.
- No Alembic migration wiring exists; `Base.metadata.create_all()` only creates missing tables, so schema-adding changes require dropping/recreating affected tables in the dev DB (same caveat as every prior schema change in this project).

## Scope

Add a required, admin-set `ticket_letter` field to each queue (set once, at creation time, like every other queue field today). Compute a new, purely additive `ticket_code` string (e.g. `E-007`) from a queue's `ticket_letter` plus its existing `ticket_number` counter, and expose it on every ticket-facing response. Replace the plain ticket number with this code everywhere it's currently shown to students or staff. No changes to `ticket_number`'s type, meaning, or role in sorting/lookups — it remains the internal per-queue counter it already is. No "Edit Queue" feature is introduced.

## Design

### Backend

- **New column**: `QueueDB.ticket_letter = Column(String(1), nullable=False)` (`backend/app/db_models.py`).
- **`QueueBase`** (`backend/app/models/queue.py`) gains `ticket_letter: str` — a single uppercase A-Z character. Pydantic validation normalizes/enforces this (uppercase, length 1, alphabetic) so `QueueCreate` inherits it as a required field.
- **Uniqueness check** in `QueueService.create_queue` (`backend/app/services/queue_service.py`): before inserting, query for any existing queue (regardless of status — active, paused, or closed) whose `ticket_letter` matches (case-insensitive). If found, raise a clear validation error (the API layer turns this into an HTTP 400 with a message like `"Ticket letter 'E' is already used by another queue"`), following this project's existing error-surfacing conventions.
- **`ticket_code` computed field**: added to both `Ticket` and `TicketPublic` (`backend/app/models/ticket.py`) as `ticket_code: str`. Computed in `TicketService` wherever a `Ticket`/`TicketPublic` is built — `_to_ticket` (uses the `queue` object already fetched there) and `get_queue_display` (same) — as `f"{queue.ticket_letter}-{ticket.ticket_number:03d}"`. This is the same additive-field pattern already used for `priority`/`called_at` in the Counter screen feature: `ticket_number` itself is untouched, `ticket_code` is a new, purely derived display string.
- **`get_now_serving_overview`** (`backend/app/services/ticket_service.py:429-457`) gets the equivalent treatment: `serving_ticket_numbers` becomes `serving_ticket_codes` (list of formatted strings) and `next_ticket_number` becomes `next_ticket_code` (formatted string or `None`), both built the same way using the queue already in scope in that method's loop.
- **Format**: `<LETTER>-<3-digit zero-padded number>`, e.g. `E-007`. If a queue's counter exceeds 999 in its lifetime, the number simply grows (`E-1000`) rather than truncating or wrapping.

### Frontend

- **Create Queue form** (`frontend/src/views/QueueManagementView.vue`, modal at lines 197-289): a new "Ticket Letter" text input (`maxlength="1"`, uppercased on input) added after the "Queue Type" field. `newQueueForm` (line 314) gains `ticket_letter: ''`. When the admin picks a Queue Type, the field is pre-filled with a sensible per-type default (E/D/C/S/O) via a small local lookup table — but remains freely editable, and is not re-overwritten if the admin has already typed something. `createQueue()` (line 391) sends `ticket_letter` as part of the payload; a collision response from the backend surfaces in the existing `createQueueError` box (line 270-272), the same way other create-queue failures do today.
- **Display consumers**: all six files that currently render `ticket.ticket_number` (or, for `DisplayOverviewView.vue`, `q.serving_ticket_numbers`/`q.next_ticket_number`) switch to rendering `ticket.ticket_code` (or `q.serving_ticket_codes`/`q.next_ticket_code`) instead. `ticket_number` itself is left in place wherever it's used as a Vue `:key` or otherwise not shown to a human — those usages are unaffected since `ticket_number` doesn't change.
- No other frontend behavior changes — no new routes, no new store actions beyond whatever the existing `createQueue` action already threads through (it already forwards the full form payload, so `ticket_letter` passes through unchanged).

### Error Handling

- A duplicate `ticket_letter` at creation time is a validation error, surfaced the same way existing create-queue validation failures are today (inline red error box in the modal, request not submitted to the database).
- Pydantic-level validation (non-alphabetic input, wrong length) is rejected the same way other malformed create-queue fields already are today (existing FastAPI/Pydantic 422 handling — no new pattern needed).

### Migration / Seed Data

Same caveat as every previous schema change in this project: no Alembic wiring exists, so the new `ticket_letter` column requires dropping/recreating the `queues` table (and, transitively, `tickets`, since it foreign-keys to `queues`) in the dev database, with the same data-loss implication already accepted for prior features. `backend/app/core/init_db.py`'s 5 seeded queues (lines 32-71) each need a `ticket_letter` value added: Enrollment→E, Document Request→D, Clearance→C, Scholarship→S, General Inquiry→O (matching its `OTHERS` type, not its name).

### Out of scope (deferred)

- Any "Edit Queue" feature (changing a queue's letter, name, type, or any other field after creation) — none exists today for any field, and this spec doesn't introduce one.
- Automatic conflict-avoidance (auto-picking a different letter if the default collides) — the admin resolves collisions manually by typing a different letter, per the user's chosen approach.
- Any change to `ticket_number`'s type, storage, or role in internal sorting/lookup logic — it remains exactly as it is today; `ticket_code` is purely additive.
- Any change to how tickets are ordered within a queue (`position` remains the sole ordering field, untouched by this change).
- Multi-letter or custom-length codes — the letter is always exactly one character.

## Testing / Verification Plan

No automated test framework is configured for this project. Verification is manual, against the real running dev stack:

1. Confirm the new `ticket_letter` column exists and the 5 seeded queues carry their expected letters after recreating the dev DB (same caveat as prior schema-adding features).
2. Create a new queue via the admin UI, confirm the Ticket Letter field pre-fills based on the selected Queue Type and can be freely edited before submitting.
3. Attempt to create a second queue using a letter already in use (e.g. `E`, already taken by the seeded Enrollment queue) and confirm the creation is rejected with a clear inline error, not silently accepted.
4. Take a ticket as a student for a queue, confirm the ticket confirmation view (`QueueDetailView.vue`/`QueuesView.vue`) shows the formatted code (e.g. `E-004`), not a bare number.
5. Serve/call/complete that ticket from both the Counter screen and the Queue Management panel, confirming both consistently show the same `ticket_code`.
6. Open the single-queue display board (`/display/:id`) and the all-queues overview (`/display/overview`) and confirm both show formatted codes (`serving_ticket_codes`/`next_ticket_code` on the overview, `ticket_code` on the single-queue board) rather than plain numbers.
