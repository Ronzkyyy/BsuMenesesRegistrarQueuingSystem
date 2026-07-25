# One Active Ticket Per Student (Rate Limiting) — Design

## Problem

`TicketService.create_ticket` only blocks a duplicate ticket within the *same* queue (`student_id` + `queue_id`). A student can currently hold active (WAITING/SERVING) tickets in several different queues at once — e.g. take a ticket in Enrollment, then immediately take another in Document Request. This defeats the purpose of a queue system as a rate-limiting mechanism: one student, one transaction in flight, at a time.

## Decision

A student may hold **at most one active ticket at a time, across all queues** (not just per-queue). This is a concurrency limit, not a time-based cooldown — once a ticket is completed, cancelled, or marked no-show, the student may immediately take a new one in any queue.

## Changes

### Backend

**`app/services/ticket_service.py` — `create_ticket`**

Replace the same-queue duplicate check:

```python
existing = self.db.query(TicketDB).filter(
    TicketDB.student_id == ticket_data.student_id,
    TicketDB.queue_id == ticket_data.queue_id,
    TicketDB.status.in_([TicketDBStatus.WAITING, TicketDBStatus.SERVING])
).first()
if existing:
    return None
```

with a global (any-queue) check that raises a descriptive error instead of silently returning `None`:

```python
existing = self.db.query(TicketDB).filter(
    TicketDB.student_id == ticket_data.student_id,
    TicketDB.status.in_([TicketDBStatus.WAITING, TicketDBStatus.SERVING])
).first()
if existing:
    existing_queue = self.db.query(QueueDB).filter(QueueDB.id == existing.queue_id).first()
    queue_label = existing_queue.name if existing_queue else "another queue"
    ticket_code = (
        _format_ticket_code(existing_queue.ticket_letter, existing.ticket_number)
        if existing_queue else ""
    )
    raise ValueError(
        f"You already have an active ticket in {queue_label} ({ticket_code}). "
        f"Complete or cancel it before taking a new one."
    )
```

All other `None`-returning cases (student not found, queue not found/inactive, queue at capacity) are unchanged — they keep the existing generic 400.

Delete `get_student_tickets` (the plural, cross-queue lookup) — with only one active ticket ever possible, it's now redundant with `get_student_ticket`.

**`app/api/tickets.py`**

- `create_ticket` endpoint: wrap `service.create_ticket(ticket)` in `try/except ValueError as e: raise HTTPException(400, detail=str(e))`, matching the existing pattern in `queues.py`/`students.py`. The generic 400 for `None` stays as the `else` path.
- Delete the `GET /my-tickets` endpoint (`get_my_tickets`), which only existed to serve the now-removed "View All My Tickets" feature.

### Frontend

**`src/stores/queue.js`**
- Delete `myTickets` state and the `fetchMyTickets` action.

**`src/views/QueuesView.vue`**
- `checkExistingTicketForSelectedService`: change `queueStore.fetchMyTicket(studentId, selectedQueueId)` → `queueStore.fetchMyTicket(studentId)` (no `queueId`), and `queueStore.startPollingMyTicket(studentId, selectedQueueId)` → `queueStore.startPollingMyTicket(studentId)`, so a student with an active ticket in *any* queue is routed to the "My Queue Status" view during the wizard (step 2), before reaching the confirm step — instead of only discovering the conflict via the 400 at submission.
- Delete the "View All My Tickets" button, the "My Tickets modal" block, the `viewAllMyTickets` function, and the `showMyTicketsModal` ref. This feature is fully redundant once only one active ticket can ever exist — `myTicket` (singular), already shown on the same screen, covers it.
- The existing catch block in `confirmRegistration` (`error.value = err.response?.data?.detail`) already surfaces the new specific message verbatim — no change needed there.

## Data Flow (new)

1. Student picks a service/queue in step 1 → step 2.
2. `checkExistingTicketForSelectedService` fetches the student's active ticket, unscoped to queue.
   - If found (any queue, any status other than completed/cancelled/no_show): show "My Queue Status" view directly, polling that ticket.
   - If none (404): continue to registration form.
3. On submit, `POST /api/tickets` re-checks server-side (authoritative check, closes the race between step 2 and submit). If a conflicting active ticket exists, respond 400 with the specific message; frontend surfaces it via the existing error banner.

## Error Handling

- Business-rule violation (duplicate active ticket) → `ValueError` → HTTP 400 with a specific, actionable message naming the queue and ticket code.
- Structural failures (student/queue not found, queue inactive, queue full) → unchanged generic 400.

## Testing

No test framework is configured for this project (per CLAUDE.md). Manual verification plan:

1. Take a ticket as Student X in Queue A. Attempt to take a ticket as Student X in Queue B:
   - Wizard should short-circuit at step 2, showing "My Queue Status" for Queue A (not the registration form for Queue B).
   - If reached anyway (e.g. via direct API call), `POST /api/tickets` should return 400 with a message naming Queue A and the ticket code.
2. Complete or cancel the Queue A ticket. Student X should then be able to take a new ticket in Queue B without conflict.
3. Confirm the "View All My Tickets" button, modal, and `GET /api/tickets/my-tickets` route are gone with no dangling references (build/lint clean).

## Out of Scope

- Time-based cooldown (e.g. once per day) — only a concurrency limit is being added.
- Changes to staff-facing serve/complete/cancel/no-show endpoints.
- DB schema/migration changes — this is pure query/business-logic logic, no new columns.
