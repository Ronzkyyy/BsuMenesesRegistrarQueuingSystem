# Now Serving Overview Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a combined "now serving" display screen showing every active queue at once, at a new `/display/overview` route, linked from the existing `/display` index page.

**Architecture:** A new public backend endpoint aggregates now-serving/waiting/next-up data for every active queue in one call. A new dark, full-screen Vue view polls that endpoint and renders a grid of per-queue cards, following the same visual/polling conventions as the existing single-queue `DisplayBoardView.vue`.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 (backend); Vue 3 (Composition API), Pinia, Vue Router, Tailwind CSS, date-fns (frontend).

## Global Constraints

- New endpoint is **public, no auth** — same convention as `/api/queues/active` and `/api/tickets/queue/{id}/display`.
- Only **active** queues (`QueueDB.status == ACTIVE`) are included, matching what `DisplayIndexView.vue` already shows.
- `serving_ticket_numbers` is a list (a queue can have more than one ticket in `serving` status concurrently in this system — there's no single-counter constraint).
- `next_ticket_number` is the lowest-`position` `WAITING` ticket's number, or `null` if none are waiting.
- The existing per-queue board (`/display/:id`) and its route are unchanged. `/display/overview` must be registered before `/display/:id` in the router's routes array (defensive ordering, mirroring the same static-before-dynamic precaution used elsewhere in this codebase, even though Vue Router 4's matcher generally ranks static segments above dynamic ones regardless of order).
- No automated test framework is configured for this project — verification is manual against the real running dev stack, per prior specs in this project.
- Seeded dev data: queues include "Enrollment" (active); students include external `student_id` `2021000001`.

---

### Task 1: Backend — now-serving-overview aggregate endpoint

**Files:**
- Modify: `bsu-registrar-queue/backend/app/services/ticket_service.py`
- Modify: `bsu-registrar-queue/backend/app/api/tickets.py`

**Interfaces:**
- Produces: `GET /api/tickets/now-serving-overview` (no auth), returning:
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
  and `TicketService.get_now_serving_overview(self) -> list[dict]`.

- [ ] **Step 1: Add `get_now_serving_overview` to `TicketService`**

In `bsu-registrar-queue/backend/app/services/ticket_service.py`, all needed imports (`TicketDB`, `TicketDBStatus`, `QueueDB`, `QueueDBStatus`, `func`) are already present at the top of the file — no new imports needed. Add this method anywhere in the `TicketService` class (e.g. immediately after `get_queue_display`, around where `get_student_ticket`/`get_student_tickets` live):

```python
    def get_now_serving_overview(self) -> List[dict]:
        """Aggregate now-serving/waiting summary for every active queue"""
        active_queues = self.db.query(QueueDB).filter(
            QueueDB.status == QueueDBStatus.ACTIVE
        ).all()

        result = []
        for queue in active_queues:
            serving_tickets = self.db.query(TicketDB).filter(
                TicketDB.queue_id == queue.id,
                TicketDB.status == TicketDBStatus.SERVING
            ).order_by(TicketDB.position).all()

            next_waiting = self.db.query(TicketDB).filter(
                TicketDB.queue_id == queue.id,
                TicketDB.status == TicketDBStatus.WAITING
            ).order_by(TicketDB.position).first()

            waiting_count = self.db.query(func.count(TicketDB.id)).filter(
                TicketDB.queue_id == queue.id,
                TicketDB.status == TicketDBStatus.WAITING
            ).scalar()

            result.append({
                "queue_id": queue.id,
                "queue_name": queue.name,
                "queue_type": queue.queue_type.value,
                "serving_ticket_numbers": [t.ticket_number for t in serving_tickets],
                "next_ticket_number": next_waiting.ticket_number if next_waiting else None,
                "waiting_count": waiting_count,
            })

        return result
```

- [ ] **Step 2: Add the `/now-serving-overview` endpoint**

In `bsu-registrar-queue/backend/app/api/tickets.py`, insert this endpoint immediately after `get_queue_display` (before `serve_next_ticket`). No route-ordering hazard here: there's no bare `GET /{something}` route in this file for a literal path segment to collide with (all `{ticket_id}` routes are POST-only, and this file's other GETs are either literal like `/my-ticket` or nested under `/queue/{queue_id}/...`).

```python
@router.get("/now-serving-overview")
def get_now_serving_overview(
    db: Session = Depends(get_db)
):
    """Get now-serving/waiting summary for every active queue (public display endpoint)"""
    service = TicketService(db)
    return service.get_now_serving_overview()
```

- [ ] **Step 3: Start the backend**

From `bsu-registrar-queue/`, run `.\dev.ps1` (or start just the backend if already set up: from `bsu-registrar-queue/backend`, `.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000`). Wait for `Uvicorn running on http://0.0.0.0:8000`.

- [ ] **Step 4: Verify — shape and no-auth**

```bash
curl -s http://localhost:8000/api/tickets/now-serving-overview
```

Expected: `200`, a JSON array with one object per active queue, each containing exactly the keys `queue_id`, `queue_name`, `queue_type`, `serving_ticket_numbers`, `next_ticket_number`, `waiting_count`. No `Authorization` header was sent, confirming this is public.

- [ ] **Step 5: Verify — reflects a real ticket lifecycle**

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=admin123" | python -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

BEFORE=$(curl -s http://localhost:8000/api/tickets/now-serving-overview)
echo "BEFORE: $BEFORE"

QUEUE_ID=$(curl -s http://localhost:8000/api/queues/active | python -c "import sys, json; print(json.load(sys.stdin)[0]['id'])")
STUDENT_ID=$(curl -s "http://localhost:8000/api/students/search?student_id=2021000001" | python -c "import sys, json; print(json.load(sys.stdin)['id'])")

TICKET_RESP=$(curl -s -X POST http://localhost:8000/api/tickets \
  -H "Content-Type: application/json" \
  -d "{\"queue_id\": $QUEUE_ID, \"student_id\": $STUDENT_ID, \"purpose\": \"overview test\"}")
TICKET_ID=$(echo "$TICKET_RESP" | python -c "import sys, json; print(json.load(sys.stdin)['id'])")
TICKET_NUMBER=$(echo "$TICKET_RESP" | python -c "import sys, json; print(json.load(sys.stdin)['ticket_number'])")

curl -s -X POST http://localhost:8000/api/tickets/$TICKET_ID/serve -H "Authorization: Bearer $TOKEN" > /dev/null

AFTER=$(curl -s http://localhost:8000/api/tickets/now-serving-overview)
echo "AFTER: $AFTER"
```

Expected: in the entry for `$QUEUE_ID`, `AFTER`'s `serving_ticket_numbers` contains `$TICKET_NUMBER` where `BEFORE`'s did not (or `BEFORE` had no entry for that queue's serving list containing it).

- [ ] **Step 6: Commit**

```bash
git add bsu-registrar-queue/backend/app/services/ticket_service.py bsu-registrar-queue/backend/app/api/tickets.py
git commit -m "feat(display): add now-serving-overview aggregate endpoint"
```

---

### Task 2: Frontend — overview page, store wiring, and index link

**Files:**
- Modify: `bsu-registrar-queue/frontend/src/stores/queue.js`
- Create: `bsu-registrar-queue/frontend/src/views/DisplayOverviewView.vue`
- Modify: `bsu-registrar-queue/frontend/src/router/index.js`
- Modify: `bsu-registrar-queue/frontend/src/views/DisplayIndexView.vue`

**Interfaces:**
- Consumes: Task 1's `GET /api/tickets/now-serving-overview`.
- Produces: store state `nowServingOverview` (array), actions `fetchNowServingOverview()` and `startPollingNowServingOverview(interval = 4000)`; route `/display/overview` (name `display-overview`).

- [ ] **Step 1: Add `nowServingOverview` state**

In `bsu-registrar-queue/frontend/src/stores/queue.js`, change:

```js
    // Tickets
    myTicket: null,
    myTickets: [],
    queueTickets: [],
    queueDisplay: [],
    servingTicket: null,
```

to:

```js
    // Tickets
    myTicket: null,
    myTickets: [],
    queueTickets: [],
    queueDisplay: [],
    servingTicket: null,
    nowServingOverview: [],
```

- [ ] **Step 2: Add `fetchNowServingOverview` action**

In the same file, change:

```js
    async fetchQueueDisplay(queueId) {
      try {
        const response = await api.get(`/tickets/queue/${queueId}/display`)
        this.queueDisplay = response.data
        return response.data
      } catch (err) {
        this.error = err.response?.data?.detail || 'Failed to fetch queue display'
        throw err
      }
    },
```

to:

```js
    async fetchQueueDisplay(queueId) {
      try {
        const response = await api.get(`/tickets/queue/${queueId}/display`)
        this.queueDisplay = response.data
        return response.data
      } catch (err) {
        this.error = err.response?.data?.detail || 'Failed to fetch queue display'
        throw err
      }
    },

    async fetchNowServingOverview() {
      try {
        const response = await api.get('/tickets/now-serving-overview')
        this.nowServingOverview = response.data
        return response.data
      } catch (err) {
        this.error = err.response?.data?.detail || 'Failed to fetch now-serving overview'
        throw err
      }
    },
```

- [ ] **Step 3: Add `startPollingNowServingOverview` action**

In the same file, change:

```js
    startPollingQueueDisplay(queueId, interval = 5000) {
      this.stopPolling()
      this.pollingInterval = setInterval(() => {
        this.fetchQueueDisplay(queueId).catch(() => {})
      }, interval)
      this.fetchQueueDisplay(queueId).catch(() => {})
    },
```

to:

```js
    startPollingQueueDisplay(queueId, interval = 5000) {
      this.stopPolling()
      this.pollingInterval = setInterval(() => {
        this.fetchQueueDisplay(queueId).catch(() => {})
      }, interval)
      this.fetchQueueDisplay(queueId).catch(() => {})
    },

    startPollingNowServingOverview(interval = 4000) {
      this.stopPolling()
      this.pollingInterval = setInterval(() => {
        this.fetchNowServingOverview().catch(() => {})
      }, interval)
      this.fetchNowServingOverview().catch(() => {})
    },
```

- [ ] **Step 4: Create `DisplayOverviewView.vue`**

Create `bsu-registrar-queue/frontend/src/views/DisplayOverviewView.vue`:

```vue
<template>
  <div class="min-h-screen bg-gray-950 text-white flex flex-col">
    <!-- Top bar -->
    <header class="flex items-center justify-between px-8 py-5 border-b border-white/10">
      <div class="flex items-center space-x-4">
        <svg class="w-9 h-9 text-bsu-gold" fill="currentColor" viewBox="0 0 24 24">
          <path d="M12 3L1 9l11 6 9-4.91V17h2V9L12 3z"/>
        </svg>
        <div>
          <h1 class="text-lg font-bold leading-tight">BSU Meneses Campus</h1>
          <p class="text-sm text-white/50">All Queues Overview</p>
        </div>
      </div>
      <div class="flex items-center space-x-6">
        <div class="text-right">
          <p class="text-2xl font-bold tabular-nums">{{ clockTime }}</p>
          <p class="text-xs text-white/50">{{ clockDate }}</p>
        </div>
        <button
          @click="toggleFullscreen"
          class="p-2 rounded-md border border-white/20 text-white/70 hover:text-white hover:border-white/40 transition-colors"
          title="Toggle fullscreen"
        >
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
          </svg>
        </button>
      </div>
    </header>

    <main class="flex-1 px-8 py-10">
      <!-- Loading -->
      <div v-if="loading && overview.length === 0" class="flex flex-col items-center justify-center h-full text-white/60">
        <div class="animate-spin rounded-full h-16 w-16 border-4 border-bsu-primary-light border-t-transparent mb-4"></div>
        <p>Loading queue overview…</p>
      </div>

      <!-- Error -->
      <div v-else-if="error && overview.length === 0" class="flex flex-col items-center justify-center h-full text-center max-w-md mx-auto">
        <svg class="mx-auto h-14 w-14 text-red-400 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
        <p class="text-white/70">{{ error }}</p>
        <button
          @click="initialize"
          class="mt-6 px-5 py-2.5 rounded-md bg-bsu-primary hover:bg-pink-800 text-white font-medium"
        >
          Retry
        </button>
      </div>

      <!-- Empty -->
      <div v-else-if="overview.length === 0" class="flex items-center justify-center h-full">
        <p class="text-white/30 text-xl">No active services right now</p>
      </div>

      <!-- Grid -->
      <div v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
        <div
          v-for="q in overview"
          :key="q.queue_id"
          class="bg-white/5 border border-white/10 rounded-2xl p-6 text-center"
        >
          <h2 class="text-sm font-semibold tracking-[0.2em] text-white/40 uppercase mb-4">{{ q.queue_name }}</h2>

          <div class="mb-4">
            <p class="text-xs uppercase tracking-wide text-white/30 mb-2">Now Serving</p>
            <div v-if="q.serving_ticket_numbers.length > 0" class="flex flex-wrap justify-center gap-2">
              <span
                v-for="num in q.serving_ticket_numbers"
                :key="num"
                class="inline-block bg-bsu-primary rounded-xl px-5 py-3 text-3xl font-extrabold tabular-nums"
              >
                {{ num }}
              </span>
            </div>
            <span v-else class="inline-block bg-white/5 border border-white/10 rounded-xl px-5 py-3 text-3xl font-extrabold text-white/20">
              --
            </span>
          </div>

          <div class="flex items-center justify-center space-x-6 text-sm">
            <div>
              <p class="text-white/30">Waiting</p>
              <p class="text-lg font-bold tabular-nums">{{ q.waiting_count }}</p>
            </div>
            <div>
              <p class="text-white/30">Next</p>
              <p class="text-lg font-bold tabular-nums">{{ q.next_ticket_number ?? '--' }}</p>
            </div>
          </div>
        </div>
      </div>
    </main>

    <footer class="text-center py-4 text-xs text-white/30 border-t border-white/10">
      Bulacan State University - Meneses Campus &middot; Registrar Queue Management System
      <span class="inline-block w-1.5 h-1.5 rounded-full bg-green-500 ml-2 align-middle animate-pulse"></span>
    </footer>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted, ref, computed } from 'vue'
import { format } from 'date-fns'
import { useQueueStore } from '@/stores/queue'

const queueStore = useQueueStore()

const loading = ref(true)
const error = ref(null)

const now = ref(new Date())
const clockTime = computed(() => format(now.value, 'h:mm:ss a'))
const clockDate = computed(() => format(now.value, 'EEEE, MMMM d, yyyy'))

const overview = computed(() => queueStore.nowServingOverview)

let clockTimer = null

const initialize = async () => {
  loading.value = true
  error.value = null
  try {
    await queueStore.fetchNowServingOverview()
    queueStore.startPollingNowServingOverview()
  } catch (err) {
    error.value = 'Unable to reach the server. Retrying automatically…'
  } finally {
    loading.value = false
  }
}

const toggleFullscreen = () => {
  if (!document.fullscreenElement) {
    document.documentElement.requestFullscreen?.()
  } else {
    document.exitFullscreen?.()
  }
}

onMounted(() => {
  initialize()
  clockTimer = setInterval(() => {
    now.value = new Date()
  }, 1000)
})

onUnmounted(() => {
  queueStore.stopPolling()
  if (clockTimer) clearInterval(clockTimer)
})
</script>
```

- [ ] **Step 5: Add the `/display/overview` route**

In `bsu-registrar-queue/frontend/src/router/index.js`, change:

```js
    {
      path: '/display',
      name: 'display-index',
      component: () => import('../views/DisplayIndexView.vue')
    },
    {
      path: '/display/:id',
      name: 'display-board',
      component: () => import('../views/DisplayBoardView.vue')
    }
```

to:

```js
    {
      path: '/display',
      name: 'display-index',
      component: () => import('../views/DisplayIndexView.vue')
    },
    {
      path: '/display/overview',
      name: 'display-overview',
      component: () => import('../views/DisplayOverviewView.vue')
    },
    {
      path: '/display/:id',
      name: 'display-board',
      component: () => import('../views/DisplayBoardView.vue')
    }
```

- [ ] **Step 6: Add the link on `DisplayIndexView.vue`**

In `bsu-registrar-queue/frontend/src/views/DisplayIndexView.vue`, change:

```html
      <div class="mb-8">
        <h2 class="text-3xl font-bold text-gray-900">Queue Display Boards</h2>
        <p class="mt-2 text-gray-600">
          Pick a service to open its public "Now Serving" board — meant to be shown full-screen on a waiting-area TV or monitor.
        </p>
      </div>

      <!-- Loading State -->
```

to:

```html
      <div class="mb-8">
        <h2 class="text-3xl font-bold text-gray-900">Queue Display Boards</h2>
        <p class="mt-2 text-gray-600">
          Pick a service to open its public "Now Serving" board — meant to be shown full-screen on a waiting-area TV or monitor.
        </p>
      </div>

      <router-link
        to="/display/overview"
        target="_blank"
        class="flex items-center justify-between bg-bsu-primary rounded-xl shadow-sm p-5 mb-6 text-white hover:bg-pink-800 transition-colors"
      >
        <div>
          <h3 class="text-lg font-bold">All Queues Overview</h3>
          <p class="text-sm text-pink-100">See every active queue's "Now Serving" ticket on one screen</p>
        </div>
        <span class="inline-flex items-center px-4 py-2 text-sm font-medium rounded-md bg-white text-bsu-primary">
          Open Board
          <svg class="ml-2 w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
          </svg>
        </span>
      </router-link>

      <!-- Loading State -->
```

- [ ] **Step 7: Start the full dev stack**

From `bsu-registrar-queue/`, run `.\dev.ps1` (or restart the frontend/backend windows if already running, to pick up the router/store changes).

- [ ] **Step 8: Verify — index page link and per-queue boards unchanged**

Navigate to `http://localhost:5173/display`. Expected: a new highlighted "All Queues Overview" card appears above the existing per-queue list; clicking an existing per-queue link still opens `/display/:id` unchanged.

- [ ] **Step 9: Verify — overview page renders and updates live**

Click "All Queues Overview" (opens `/display/overview` in a new tab). Expected: dark full-screen layout, one card per active queue, each showing name, now-serving number(s) (or `--`), waiting count, and next-up ticket. In the admin/counter UI (or via the Task 1 curl flow), serve or complete a ticket in one of the shown queues; within ~4 seconds the corresponding card updates without a manual reload.

- [ ] **Step 10: Commit**

```bash
git add bsu-registrar-queue/frontend/src/stores/queue.js \
        bsu-registrar-queue/frontend/src/views/DisplayOverviewView.vue \
        bsu-registrar-queue/frontend/src/router/index.js \
        bsu-registrar-queue/frontend/src/views/DisplayIndexView.vue
git commit -m "feat(display): add now-serving overview page for all active queues"
```
