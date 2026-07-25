# Surface Student Services on Counter and Admin Dashboard — Design

## Problem

The student registration wizard offers 8 distinct services (Clearance, Request Documents, Adding & Dropping, Enrollment, General Inquiry, Scholarship, Petition Class, Others — `QueuesView.vue:415-422`), but the backend only has 5 queue types (`enrollment`, `document_request`, `clearance`, `scholarship`, `others`). Three services (Adding & Dropping, Enrollment, Petition Class) all map to the same `enrollment` queue; two (General Inquiry, Others) both map to `others`. The only place the specific service survives past ticket creation is the free-text `ticket.purpose` field.

That field never reaches staff:
- **Counter** (`CounterView.vue`) never renders `ticket.purpose` anywhere. Its waiting list is sourced from the public `GET /tickets/queue/{id}/display` endpoint, whose `TicketPublic` schema doesn't include `purpose` at all.
- **Admin Dashboard**: `get_dashboard_summary` (`queue_service.py:203-211`) aggregates "Tickets Today by Queue" strictly by `queue_id`/`queue_name` — no breakdown by service anywhere.

Result: staff serving the "Enrollment" queue can't tell whether a ticket is for Adding & Dropping, plain Enrollment, or a Petition Class without asking the student, and the admin dashboard can't show volume by service, only by the 5 underlying queues.

## Decision

Surface `ticket.purpose` on both screens:
1. **Counter**: show it as a label on every ticket (serving + waiting).
2. **Dashboard**: replace the "Tickets Today by Queue" chart with "Tickets Today by Service", grouping by `purpose` (falling back to queue name when null).

No DB schema or migration changes — this uses the existing free-text `purpose` field as-is. Grouping raw purpose text is simplest and sufficient: 7 of 8 services always set a fixed purpose string; only "Others" is genuinely free text, and it's the least-used service, so occasional noisy one-off dashboard buckets are an acceptable tradeoff against the larger schema change a proper service-key column would require.

## Changes

### Counter (`bsu-registrar-queue/frontend/src/views/CounterView.vue`) — frontend only

**Data source for the waiting list:** Currently `updateQueueDisplay()` populates `queueDisplay` via `queueStore.fetchQueueDisplay(targetQueueId)` → `GET /tickets/queue/{id}/display` → `TicketPublic[]` (no `purpose` field — deliberately, since that endpoint also feeds the public display board, and exposing free-text "Others" purposes there isn't desirable). Switch the waiting list to source from `queueStore.fetchQueueTickets(targetQueueId, 'waiting')` instead — the same staff-authenticated endpoint (`GET /tickets/queue/{id}?status=waiting`) already used to find the serving ticket, which returns the full `Ticket` model (`purpose` included). This removes the Counter's dependency on the public display endpoint entirely.

**Rendering:** Add `ticket.purpose` as a small label under/next to the ticket code:
- In the "Currently Serving" card (`CounterView.vue:32-44`), under the big ticket code.
- In each waiting-list row (`CounterView.vue:92-109`), under/next to the ticket code.

Fall back to nothing shown (or the queue name) if `purpose` is empty — should be rare since the wizard requires a purpose for every service that doesn't have a fixed `defaultPurpose`.

No backend changes needed for the Counter — `Ticket` (used by `GET /tickets/queue/{id}`) already includes `purpose`.

### Admin Dashboard

**Backend (`bsu-registrar-queue/backend/app/services/queue_service.py::get_dashboard_summary`)**

Replace the current aggregation:

```python
queue_rows = self.db.query(
    TicketDB.queue_id, QueueDB.name, func.count(TicketDB.id)
).join(QueueDB, TicketDB.queue_id == QueueDB.id).filter(
    TicketDB.created_at >= today_start
).group_by(TicketDB.queue_id, QueueDB.name).all()
tickets_today_by_queue = [
    {"queue_id": queue_id, "queue_name": queue_name, "count": count}
    for queue_id, queue_name, count in queue_rows
]
```

with a purpose-based grouping, falling back to the queue name when `purpose` is null:

```python
service_label = func.coalesce(TicketDB.purpose, QueueDB.name)
service_rows = self.db.query(
    service_label, func.count(TicketDB.id)
).join(QueueDB, TicketDB.queue_id == QueueDB.id).filter(
    TicketDB.created_at >= today_start
).group_by(service_label).all()
tickets_today_by_service = [
    {"service_name": service_name, "count": count}
    for service_name, count in service_rows
]
```

Rename the response key `tickets_today_by_queue` → `tickets_today_by_service` (only the dashboard consumes this field, so no other API consumer is affected).

**Frontend (`bsu-registrar-queue/frontend/src/views/DashboardView.vue`)**

- `hasQueueData` / `barData` computeds: read from `summary.value?.tickets_today_by_service` instead of `tickets_today_by_queue`, and use `q.service_name` instead of `q.queue_name` for bar labels.
- Chart heading: "Tickets Today by Queue" → "Tickets Today by Service".

## Data Flow (new)

1. Student picks a service in the wizard → `purpose` set (fixed string for 7 services, free text for "Others") → stored on the ticket at creation (unchanged).
2. **Counter:** staff selects a queue → waiting list + serving ticket both now come from the same staff-authenticated `GET /tickets/queue/{id}` endpoint (`status=waiting` / `status=serving`), both including `purpose` → rendered as a label per ticket.
3. **Dashboard:** `get_dashboard_summary` groups today's tickets by `COALESCE(purpose, queue_name)` → bar chart shows per-service volume instead of per-queue volume.

## Testing

No automated test framework is configured for this project (per `CLAUDE.md`). Manual verification plan, against the real running stack:

1. Take tickets for at least two different services that map to the same queue (e.g. "Adding & Dropping" and "Petition Class", both `enrollment`).
2. On the Counter screen for that queue: confirm the waiting list shows a distinct purpose label per ticket, and serving one of them shows its purpose on the "Currently Serving" card.
3. On the Admin Dashboard: confirm "Tickets Today by Service" shows separate bars for "Adding & Dropping" and "Petition Class" rather than one combined "Enrollment" bar.
4. Confirm the public display board (`DisplayBoardView.vue`) is unaffected — still shows no purpose/service info, only ticket code/position/status.

## Out of Scope

- DB schema/migration changes (e.g. a dedicated service-key column) — grouping by existing free-text `purpose` is the chosen tradeoff.
- Changes to the public display board or the student-facing registration wizard.
- Any change to how `purpose` is set or validated at ticket creation.
