# Now Serving Overview — Design Spec

**Date:** 2026-07-17
**Status:** Approved by user, ready for implementation planning

## Background

The user wants a single screen showing the "now serving" ticket for every active queue at once, for display on a shared waiting-area monitor — rather than needing to pick one queue at a time from the existing `/display` index and its per-queue `/display/:id` boards.

## Current State (before this change)

- `frontend/src/views/DisplayIndexView.vue`: lists active queues, each linking to `/display/:id`.
- `frontend/src/views/DisplayBoardView.vue`: dark, full-screen TV-style board for **one** queue — "Now Serving" ticket(s), a "Waiting" list/preview, clock, fullscreen toggle. Polls `GET /api/tickets/queue/{id}/display` every 4 seconds via `queueStore.startPollingQueueDisplay`.
- `backend/app/services/ticket_service.py:389` `get_queue_display(queue_id)` returns one queue's waiting+serving tickets as `TicketPublic` (ticket_number, queue_name, position, status, estimated_wait_time_minutes, created_at) — scoped to a single queue, no aggregate-across-queues endpoint exists.
- No route ordering hazard: all existing `GET` routes in `tickets.py` are either literal (`/my-ticket`, `/my-tickets`) or under the `/queue/{queue_id}...` prefix — a new top-level literal route doesn't collide with any of them.

## Scope

Add a new combined overview screen at `/display/overview`, linked from the top of the existing `/display` index page. The existing per-queue boards (`/display/:id`) and their links are unchanged. No changes to student/admin/counter flows.

## Design

### Backend

- **New endpoint** `GET /api/tickets/now-serving-overview` (public, no auth — same convention as `/queues/active` and `/tickets/queue/{id}/display`), added to `backend/app/api/tickets.py`.
- **New service method** `TicketService.get_now_serving_overview(self) -> list[dict]` in `backend/app/services/ticket_service.py`, iterating active queues once and returning, per queue:
  ```json
  [
    {
      "queue_id": 1,
      "queue_name": "Enrollment",
      "queue_type": "enrollment",
      "serving_ticket_numbers": [5, 6],
      "next_ticket_number": 7,
      "waiting_count": 3
    }
  ]
  ```
  - `serving_ticket_numbers`: all tickets in that queue with `status == SERVING`, as a list (our model allows more than one concurrently-serving ticket per queue, since there's no single-counter constraint).
  - `next_ticket_number`: the `ticket_number` of the lowest-`position` `WAITING` ticket in that queue, or `null` if none are waiting.
  - `waiting_count`: count of `WAITING` tickets in that queue.
  - Only **active** queues (`QueueDB.status == ACTIVE`) are included, matching what `DisplayIndexView.vue` already shows.

### Frontend

- **New route** `/display/overview` → new `frontend/src/views/DisplayOverviewView.vue`, styled consistently with `DisplayBoardView.vue` (dark full-screen theme, live clock, fullscreen toggle) but rendering a **grid of cards, one per active queue** instead of one queue's detail:
  - Queue name
  - Currently-serving ticket number(s) (or a placeholder `--` if none)
  - Waiting count
  - Next-up ticket number (or blank if none waiting)
- Polls the new endpoint on the same 4-second interval convention as the existing per-queue board.
- **`frontend/src/views/DisplayIndexView.vue`**: add one new link at the top of the list, to `/display/overview`, labeled distinctly from the per-queue board links (e.g. "All Queues Overview"). Existing per-queue links are unchanged, unmoved.
- **`frontend/src/stores/queue.js`**: add `fetchNowServingOverview()` action and a `nowServingOverview` state field, following the existing `loading`/`error` action pattern. A `startPollingNowServingOverview` / reuse of the existing generic `pollingInterval` + `stopPolling()` mechanism, matching the pattern already used by `startPollingQueueDisplay`.

### Error Handling

- Fetch failure on the overview page → same inline error + retry pattern as `DisplayBoardView.vue`'s existing error state.
- Empty state (no active queues) → same "no active services" messaging convention used elsewhere (`DisplayIndexView.vue`'s empty state).

### Out of scope (deferred to future specs)

- Media/video panel and scrolling announcement ticker (separate sub-project, to be brainstormed next).
- Any change to the existing per-queue `DisplayBoardView.vue` or its route.
- Any change to the Counter-screen redesign (still deferred from the earlier admin-dashboard spec).

## Testing / Verification Plan

No automated test framework is configured for this project. Verification is manual, against the real running dev stack:
1. Start the dev stack.
2. `curl http://localhost:8000/api/tickets/now-serving-overview` (no auth needed) and confirm the response shape, cross-checked against real ticket data (serve a ticket, confirm it appears in `serving_ticket_numbers`; check `waiting_count`/`next_ticket_number` against the actual waiting list for that queue).
3. Navigate to `/display` → confirm a new "All Queues Overview" link appears above the existing per-queue links, and those per-queue links still work unchanged.
4. Navigate to `/display/overview` → confirm a card per active queue, correct now-serving/waiting/next values, live updates within ~4 seconds of a ticket being served/completed elsewhere.
