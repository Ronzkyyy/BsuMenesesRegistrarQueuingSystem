# Surface Student Services on Counter and Admin Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the specific student service (e.g. Adding & Dropping vs. Enrollment vs. Petition Class — currently indistinguishable since they share one queue) visible to staff on the Counter screen and broken out on the Admin Dashboard.

**Architecture:** The specific service a student picked only survives as the free-text `ticket.purpose` field. Today it's never rendered to staff: the Counter's waiting list is sourced from the public `TicketPublic`-based display endpoint (which excludes `purpose` by design, since it also feeds the unauthenticated public display board), and the Admin Dashboard's "Tickets Today by Queue" chart aggregates strictly by `queue_id`/`queue_name`. This plan (1) switches the Counter's waiting list to the already-available staff-authenticated `GET /tickets/queue/{id}?status=waiting` endpoint (full `Ticket`, includes `purpose`) and renders `purpose` as a label on every ticket, and (2) changes the dashboard's backend aggregation to group by `COALESCE(purpose, queue_name)` instead of by queue, renaming the response field and updating the chart to match.

**Tech Stack:** Python FastAPI + SQLAlchemy (backend), Vue 3 + Pinia + vue-chartjs (frontend). No test framework is configured in this repo (per `CLAUDE.md`), so verification is manual against the real running stack, not mocked.

## Global Constraints

- No DB schema or migration changes — group by the existing free-text `purpose` column as-is.
- No changes to the public display board (`DisplayBoardView.vue`) or its backend endpoint (`GET /tickets/queue/{id}/display`, `TicketPublic` schema) — `purpose` must NOT be added to `TicketPublic` or exposed on that public, unauthenticated board.
- No changes to the student-facing registration wizard (`QueuesView.vue`'s services list) or to how `purpose` is set/validated at ticket creation.
- The dashboard's response field is renamed `tickets_today_by_queue` → `tickets_today_by_service` — this is a deliberate breaking change to that one field; only `DashboardView.vue` consumes it, so no other caller needs updating.

---

### Task 1: Backend — group dashboard's "tickets today" aggregation by service instead of queue

**Files:**
- Modify: `bsu-registrar-queue/backend/app/services/queue_service.py:203-211,221`

**Interfaces:**
- Consumes: `TicketDB.purpose` (existing nullable `Text` column, `db_models.py:114`), `QueueDB.name`.
- Produces: `get_dashboard_summary()`'s returned dict now has a `tickets_today_by_service` key (list of `{"service_name": str, "count": int}`) instead of `tickets_today_by_queue` (list of `{"queue_id": int, "queue_name": str, "count": int}`). Task 2 (frontend) consumes this new key and shape.

- [ ] **Step 1: Replace the queue-grouped aggregation with a service-grouped one**

In `bsu-registrar-queue/backend/app/services/queue_service.py`, replace lines 203-211:

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

with:

```python
        # Group by the student's specific purpose (e.g. "Petition Class"),
        # falling back to the queue name for the rare ticket with no purpose
        # set - purpose is the only place the specific service (as opposed
        # to the shared underlying queue) survives past ticket creation.
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

- [ ] **Step 2: Update the returned dict's key**

In the same file, replace line 221:

```python
            "tickets_today_by_queue": tickets_today_by_queue,
```

with:

```python
            "tickets_today_by_service": tickets_today_by_service,
```

- [ ] **Step 3: Start the real backend stack and verify manually**

```bash
cd bsu-registrar-queue/backend
source .venv/Scripts/activate
uvicorn app.main:app --reload
```

You'll need a staff auth token. Log in via the existing `/api/auth/login` endpoint with an existing admin/registrar/staff account (check `bsu-registrar-queue/backend/app/core/init_db.py` for a seeded account, or use one you know exists in the real dev DB):

```bash
curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "<username>", "password": "<password>"}' | python -m json.tool
```

Copy the `access_token` from the response. Take at least two tickets today for services that share a queue (e.g. "Adding & Dropping" and "Petition Class", both `enrollment` — use the frontend wizard, or `POST /api/tickets` directly with `purpose` set to each string and a valid `queue_id`/`student_id`).

Then call the dashboard summary endpoint:

```bash
curl -s http://localhost:8000/api/queues/dashboard-summary \
  -H "Authorization: Bearer <access_token>" | python -m json.tool
```

Expected: the response has a `tickets_today_by_service` key (not `tickets_today_by_queue`), with separate entries like `{"service_name": "Adding & Dropping", "count": 1}` and `{"service_name": "Petition Class", "count": 1}` rather than one combined `{"queue_name": "Enrollment", "count": 2}`.

- [ ] **Step 4: Commit**

```bash
git add bsu-registrar-queue/backend/app/services/queue_service.py
git commit -m "feat(dashboard): group tickets-today aggregation by service instead of queue"
```

---

### Task 2: Frontend — Admin Dashboard consumes the new service breakdown

**Files:**
- Modify: `bsu-registrar-queue/frontend/src/views/DashboardView.vue:48-53,88,94-105`

**Interfaces:**
- Consumes: `summary.tickets_today_by_service: {service_name: string, count: number}[]` (produced by Task 1's backend change; `summary` comes from `queueStore.dashboardSummary`, unchanged plumbing).
- Produces: no new interfaces; this is the sole consumer of the renamed field.

- [ ] **Step 1: Update the heading**

In `bsu-registrar-queue/frontend/src/views/DashboardView.vue`, replace line 48:

```html
        <h3 class="text-lg font-medium text-gray-900 mb-4">Tickets Today by Queue</h3>
```

with:

```html
        <h3 class="text-lg font-medium text-gray-900 mb-4">Tickets Today by Service</h3>
```

- [ ] **Step 2: Rename and repoint the `hasQueueData` computed**

Replace line 88:

```javascript
const hasQueueData = computed(() => (summary.value?.tickets_today_by_queue?.length ?? 0) > 0)
```

with:

```javascript
const hasServiceData = computed(() => (summary.value?.tickets_today_by_service?.length ?? 0) > 0)
```

- [ ] **Step 3: Update the template's `v-if` to match the renamed computed**

In the same file, replace the `v-if="hasQueueData"` in the "Tickets Today by Service" card (the same block as Step 1, around line 49):

```html
        <div v-if="hasQueueData" class="h-64">
```

with:

```html
        <div v-if="hasServiceData" class="h-64">
```

- [ ] **Step 4: Repoint `barData` at the new field/shape**

Replace lines 94-105:

```javascript
const barData = computed(() => ({
  labels: (summary.value?.tickets_today_by_queue ?? []).map((q) => q.queue_name),
  datasets: [
    {
      label: 'Tickets Today',
      data: (summary.value?.tickets_today_by_queue ?? []).map((q) => q.count),
      backgroundColor: '#be185d',
      borderRadius: 4,
      maxBarThickness: 48,
    },
  ],
}))
```

with:

```javascript
const barData = computed(() => ({
  labels: (summary.value?.tickets_today_by_service ?? []).map((s) => s.service_name),
  datasets: [
    {
      label: 'Tickets Today',
      data: (summary.value?.tickets_today_by_service ?? []).map((s) => s.count),
      backgroundColor: '#be185d',
      borderRadius: 4,
      maxBarThickness: 48,
    },
  ],
}))
```

- [ ] **Step 5: Start the frontend dev server and verify manually in the browser**

```bash
cd bsu-registrar-queue/frontend
npm run dev
```

Make sure the backend from Task 1 is still running on port 8000.

In the browser (http://localhost:5173), log in as staff and open the Dashboard. With the two test tickets from Task 1's Step 3 still present (or take fresh ones for two different services sharing a queue), confirm:
1. The chart is titled "Tickets Today by Service".
2. It shows separate bars for each distinct purpose (e.g. "Adding & Dropping" and "Petition Class" as two bars, not one "Enrollment" bar).

- [ ] **Step 6: Commit**

```bash
git add bsu-registrar-queue/frontend/src/views/DashboardView.vue
git commit -m "feat(dashboard): show tickets-today chart broken down by service"
```

---

### Task 3: Frontend — Counter shows each ticket's specific service

**Files:**
- Modify: `bsu-registrar-queue/frontend/src/views/CounterView.vue:32-44,92-109,140-187`

**Interfaces:**
- Consumes: `queueStore.fetchQueueTickets(queueId, status)` (existing store action, `stores/queue.js:552-566`, unchanged) — returns full `Ticket[]` including `purpose`, via the staff-authenticated `GET /tickets/queue/{id}?status=...` endpoint.
- Produces: no new interfaces; this task only changes `CounterView.vue`'s internal data source and template. This task is independent of Tasks 1-2 (different screen, no shared code) and can be verified separately.

- [ ] **Step 1: Rename the `queueDisplay` ref and repoint the `waitingTickets` computed**

In `bsu-registrar-queue/frontend/src/views/CounterView.vue`, replace lines 140-144:

```javascript
const queueDisplay = ref([])
const servingTicket = ref(null)
const waitingTickets = computed(() =>
  queueDisplay.value.filter(t => t.status === 'waiting').slice().sort((a, b) => a.position - b.position)
)
```

with:

```javascript
const waitingTicketsRaw = ref([])
const servingTicket = ref(null)
const waitingTickets = computed(() =>
  waitingTicketsRaw.value.filter(t => t.status === 'waiting').slice().sort((a, b) => a.position - b.position)
)
```

(Renamed because this no longer comes from the public "display" endpoint — see Step 2.)

- [ ] **Step 2: Switch the waiting-list fetch from the public display endpoint to the staff-authenticated ticket list**

In the same file, replace lines 156-171 (the first half of `updateQueueDisplay`, up to but not including the existing "serving" fetch block):

```javascript
const updateQueueDisplay = async () => {
  if (!selectedQueueId.value) return
  const targetQueueId = selectedQueueId.value

  try {
    await queueStore.fetchQueueDisplay(targetQueueId)
    if (selectedQueueId.value === targetQueueId) {
      queueDisplay.value = queueStore.queueDisplay
    }
  } catch (err) {
    if (selectedQueueId.value === targetQueueId) {
      queueDisplay.value = []
    }
  }

  try {
    await queueStore.fetchQueueTickets(targetQueueId, 'serving')
```

with:

```javascript
const updateQueueDisplay = async () => {
  if (!selectedQueueId.value) return
  const targetQueueId = selectedQueueId.value

  try {
    await queueStore.fetchQueueTickets(targetQueueId, 'waiting')
    if (selectedQueueId.value === targetQueueId) {
      waitingTicketsRaw.value = queueStore.queueTickets
    }
  } catch (err) {
    if (selectedQueueId.value === targetQueueId) {
      waitingTicketsRaw.value = []
    }
  }

  try {
    await queueStore.fetchQueueTickets(targetQueueId, 'serving')
```

Leave the rest of `updateQueueDisplay` (the "serving" fetch block and its catch, lines 171-186 in the original) unchanged — only the first `try`/`catch` block changes.

- [ ] **Step 3: Show the purpose on the "Currently Serving" card**

In the same file, replace lines 32-35:

```html
            <div v-if="servingTicket">
              <span class="inline-block px-8 py-4 bg-bsu-primary text-white text-5xl font-extrabold rounded-full mb-3">
                {{ servingTicket.ticket_code }}
              </span>
```

with:

```html
            <div v-if="servingTicket">
              <span class="inline-block px-8 py-4 bg-bsu-primary text-white text-5xl font-extrabold rounded-full mb-3">
                {{ servingTicket.ticket_code }}
              </span>
              <p v-if="servingTicket.purpose" class="text-sm text-gray-600 mb-2">{{ servingTicket.purpose }}</p>
```

- [ ] **Step 4: Show the purpose on each waiting-list row**

In the same file, replace lines 98-107:

```html
                <div class="flex items-center space-x-3">
                  <span class="font-medium text-gray-900">{{ ticket.ticket_code }}</span>
                  <span
                    v-if="ticket.priority !== 'normal'"
                    class="text-xs px-2 py-0.5 rounded-full"
                    :class="ticket.priority === 'urgent' ? 'bg-red-100 text-red-800' : 'bg-yellow-100 text-yellow-800'"
                  >
                    {{ ticket.priority }}
                  </span>
                </div>
```

with:

```html
                <div class="flex items-center space-x-3">
                  <span class="font-medium text-gray-900">{{ ticket.ticket_code }}</span>
                  <span v-if="ticket.purpose" class="text-sm text-gray-500">{{ ticket.purpose }}</span>
                  <span
                    v-if="ticket.priority !== 'normal'"
                    class="text-xs px-2 py-0.5 rounded-full"
                    :class="ticket.priority === 'urgent' ? 'bg-red-100 text-red-800' : 'bg-yellow-100 text-yellow-800'"
                  >
                    {{ ticket.priority }}
                  </span>
                </div>
```

- [ ] **Step 5: Start the real stack and verify manually in the browser**

```bash
cd bsu-registrar-queue/backend
source .venv/Scripts/activate
uvicorn app.main:app --reload
```

```bash
cd bsu-registrar-queue/frontend
npm run dev
```

In the browser:
1. As a student, take two tickets for services that share a queue (e.g. "Adding & Dropping" and "Petition Class") — use two different student IDs, since Tasks 1-2 of the earlier "one ticket per student" work restrict each student to one active ticket at a time.
2. Log in to the Counter as staff and select that queue.
3. Confirm the waiting list shows each ticket's purpose label (e.g. "Adding & Dropping" next to one ticket code, "Petition Class" next to the other).
4. Click "Serve Next Ticket" and confirm the "Currently Serving" card also shows that ticket's purpose underneath the ticket code.
5. Confirm the public display board (`/display` route or however it's accessed) is unaffected — still shows no purpose text, only ticket code/position/status (spot-check, since this task doesn't touch that view/endpoint).

- [ ] **Step 6: Commit**

```bash
git add bsu-registrar-queue/frontend/src/views/CounterView.vue
git commit -m "feat(counter): show each ticket's specific service to staff"
```
