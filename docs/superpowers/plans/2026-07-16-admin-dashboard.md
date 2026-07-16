# Admin Dashboard Overview Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the single `AdminView.vue` with a sidebar-shell layout (`AdminLayout.vue`) wrapping three routed pages — Dashboard (new stats/charts), Queue Management (moved, unchanged behavior), and User Management (new) — backed by one new aggregate backend endpoint that also fixes a pre-existing stats bug.

**Architecture:** A new `GET /api/queues/dashboard-summary` endpoint computes today's ticket cohort and live counts in a few fixed queries. The frontend splits `/admin` into nested Vue Router routes under a shared `AdminLayout.vue` (sidebar + header), with `DashboardView.vue` rendering stat tiles and two Chart.js charts, `QueueManagementView.vue` carrying over today's queue/ticket-serving UI verbatim, and `UserManagementView.vue` exposing already-existing but previously UI-less staff-account endpoints. A router guard extension restricts `/admin/users` to Admin role.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, Pydantic v2 (backend); Vue 3 (Composition API, `<script setup>`), Pinia, Vue Router, Tailwind CSS, Chart.js + vue-chartjs (new), Axios (frontend).

## Global Constraints

- Sidebar has exactly 3 links: Dashboard, Queue Management, User Management (no Media/Audit Logs/Reports/separate Admin Management — those are deferred to future specs, omitted entirely rather than shown disabled).
- User Management link and route are Admin-only: hidden from the sidebar and guarded server- and client-side for non-Admin roles.
- `waiting_count` / `serving_count` in the dashboard summary are **live state** (not date-filtered). `completed_today_count` / `no_shows_today_count` and both chart datasets are derived from **the same "today" cohort** (tickets where `created_at` falls in the current UTC calendar day), so tiles and charts can never disagree.
- No automated test framework is configured for this project (backend or frontend) — verification is manual against the real running dev stack (`dev.ps1`), consistent with prior specs in this project. Do not introduce pytest/Vitest as part of this plan.
- Seeded dev accounts: `admin/admin123` (Admin), `registrar/registrar123` (Registrar), `staff/staff123` (Staff). Seeded queues include "Enrollment" (active). Seeded students include external `student_id` `2021000001` (Juan Dela Cruz).
- Chart colors: bar chart uses a single BSU-primary (`#be185d`) fill (one series, no categorical need). Pie/donut chart uses this fixed, validated 5-color mapping (never reassigned): `waiting` → `#2a78d6`, `serving` → `#eda100`, `completed` → `#008300`, `cancelled` → `#4a3aa7`, `no_show` → `#e34948`.
- `QueueManagementView.vue`'s content is a verbatim behavioral move from today's `AdminView.vue` — no behavior changes there in this plan.

---

### Task 1: Backend — dashboard-summary aggregate endpoint

**Files:**
- Modify: `bsu-registrar-queue/backend/app/services/queue_service.py`
- Modify: `bsu-registrar-queue/backend/app/api/queues.py`

**Interfaces:**
- Produces: `GET /api/queues/dashboard-summary` (role: Admin/Registrar/Staff, same as existing `/api/queues/{id}/stats`), returning:
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
  and `QueueService.get_dashboard_summary(self) -> dict`, callable by later tasks (none in this plan call it directly from Python, only via the endpoint).

- [ ] **Step 1: Add `timezone` to the datetime import**

In `bsu-registrar-queue/backend/app/services/queue_service.py`, change line 6 from:

```python
from datetime import datetime
```

to:

```python
from datetime import datetime, timezone
```

- [ ] **Step 2: Add `get_dashboard_summary` to `QueueService`**

In the same file, insert this new method immediately after `get_queue_stats` (i.e. right before the `def _to_queue` method, after the closing `}` of `get_queue_stats`'s return statement):

```python
    def get_dashboard_summary(self) -> dict:
        """Aggregate stats for the admin dashboard overview"""
        from ..db_models import TicketDB, TicketDBStatus, UserDB
        from sqlalchemy import func

        users_count = self.db.query(func.count(UserDB.id)).scalar()
        queues_count = self.db.query(func.count(QueueDB.id)).scalar()
        active_queues_count = self.db.query(func.count(QueueDB.id)).filter(
            QueueDB.status == QueueDBStatus.ACTIVE
        ).scalar()

        waiting_count = self.db.query(func.count(TicketDB.id)).filter(
            TicketDB.status == TicketDBStatus.WAITING
        ).scalar()
        serving_count = self.db.query(func.count(TicketDB.id)).filter(
            TicketDB.status == TicketDBStatus.SERVING
        ).scalar()

        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

        status_rows = self.db.query(
            TicketDB.status, func.count(TicketDB.id)
        ).filter(
            TicketDB.created_at >= today_start
        ).group_by(TicketDB.status).all()
        tickets_today_by_status = {status.value: 0 for status in TicketDBStatus}
        for status, count in status_rows:
            tickets_today_by_status[status.value] = count

        queue_rows = self.db.query(
            TicketDB.queue_id, QueueDB.name, func.count(TicketDB.id)
        ).join(QueueDB, TicketDB.queue_id == QueueDB.id).filter(
            TicketDB.created_at >= today_start
        ).group_by(TicketDB.queue_id, QueueDB.name).all()
        tickets_today_by_queue = [
            {"queue_id": queue_id, "queue_name": queue_name, "count": count}
            for queue_id, queue_name, count in queue_rows
        ]

        return {
            "users_count": users_count,
            "queues_count": queues_count,
            "active_queues_count": active_queues_count,
            "waiting_count": waiting_count,
            "serving_count": serving_count,
            "completed_today_count": tickets_today_by_status["completed"],
            "no_shows_today_count": tickets_today_by_status["no_show"],
            "tickets_today_by_queue": tickets_today_by_queue,
            "tickets_today_by_status": tickets_today_by_status,
        }
```

- [ ] **Step 3: Add the `/dashboard-summary` endpoint**

In `bsu-registrar-queue/backend/app/api/queues.py`, insert this new endpoint **immediately after** the `list_active_queues` function (after its closing `return service.get_active_queues()`, i.e. right before `@router.get("/{queue_id}", response_model=Queue)`). This ordering matters: FastAPI/Starlette matches routes in registration order, and `/{queue_id}` has no type constraint in the path pattern itself, so a literal segment like `dashboard-summary` would otherwise be swallowed by `/{queue_id}` first (causing a 422, since `"dashboard-summary"` doesn't coerce to the `queue_id: int` parameter) — exactly the same reason `/active` is already placed before `/{queue_id}` in this file.

```python
@router.get("/dashboard-summary")
def get_dashboard_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.REGISTRAR, UserRole.STAFF))
):
    """Get aggregate stats for the admin dashboard overview"""
    service = QueueService(db)
    return service.get_dashboard_summary()
```

- [ ] **Step 4: Start the backend**

From `bsu-registrar-queue/`, run `.\dev.ps1` (or start just the backend if the stack is already set up: from `bsu-registrar-queue/backend`, `.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000`). Wait until it prints `Uvicorn running on http://0.0.0.0:8000` (or `127.0.0.1:8000`).

- [ ] **Step 5: Verify — endpoint shape and role-gating**

Get an Admin token and confirm the endpoint requires auth and returns the expected keys:

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=admin123" | python -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

curl -s -o /dev/null -w "no-auth: %{http_code}\n" http://localhost:8000/api/queues/dashboard-summary

curl -s http://localhost:8000/api/queues/dashboard-summary -H "Authorization: Bearer $TOKEN"
```

Expected: `no-auth: 401`, and the authenticated call returns a JSON object containing exactly the keys `users_count`, `queues_count`, `active_queues_count`, `waiting_count`, `serving_count`, `completed_today_count`, `no_shows_today_count`, `tickets_today_by_queue`, `tickets_today_by_status` (values will reflect whatever is currently in the dev DB — that's fine for this check).

- [ ] **Step 6: Verify — "today" aggregation actually reflects a real ticket's lifecycle**

Create one ticket, serve it, complete it, and confirm the summary's `completed_today_count` and `tickets_today_by_status.completed` both increased by exactly 1, and that the queue used appears (or increments) in `tickets_today_by_queue`:

```bash
BEFORE=$(curl -s http://localhost:8000/api/queues/dashboard-summary -H "Authorization: Bearer $TOKEN")
echo "BEFORE: $BEFORE"

QUEUE_ID=$(curl -s http://localhost:8000/api/queues/active | python -c "import sys, json; print(json.load(sys.stdin)[0]['id'])")
STUDENT_ID=$(curl -s "http://localhost:8000/api/students/search?student_id=2021000001" | python -c "import sys, json; print(json.load(sys.stdin)['id'])")

TICKET_ID=$(curl -s -X POST http://localhost:8000/api/tickets \
  -H "Content-Type: application/json" \
  -d "{\"queue_id\": $QUEUE_ID, \"student_id\": $STUDENT_ID, \"purpose\": \"dashboard summary test\"}" \
  | python -c "import sys, json; print(json.load(sys.stdin)['id'])")

curl -s -X POST http://localhost:8000/api/tickets/$TICKET_ID/serve -H "Authorization: Bearer $TOKEN" > /dev/null
curl -s -X POST http://localhost:8000/api/tickets/$TICKET_ID/complete -H "Authorization: Bearer $TOKEN" > /dev/null

AFTER=$(curl -s http://localhost:8000/api/queues/dashboard-summary -H "Authorization: Bearer $TOKEN")
echo "AFTER: $AFTER"
```

Expected: in `AFTER` vs `BEFORE`, `completed_today_count` is exactly 1 higher, `tickets_today_by_status.completed` is exactly 1 higher, and `tickets_today_by_queue` contains an entry for `$QUEUE_ID` whose `count` is exactly 1 higher than in `BEFORE` (or a new entry with `count: 1` if that queue had no tickets today before this step).

- [ ] **Step 7: Commit**

```bash
git add bsu-registrar-queue/backend/app/services/queue_service.py bsu-registrar-queue/backend/app/api/queues.py
git commit -m "feat(dashboard): add aggregate dashboard-summary endpoint"
```

---

### Task 2: Frontend — store data layer and charting dependency

**Files:**
- Modify: `bsu-registrar-queue/frontend/package.json`
- Modify: `bsu-registrar-queue/frontend/src/stores/queue.js`

**Interfaces:**
- Consumes: Task 1's `GET /api/queues/dashboard-summary`; existing `GET /api/auth/users`, `POST /api/auth/register`, `PATCH /api/auth/users/{id}/activate`, `PATCH /api/auth/users/{id}/deactivate`.
- Produces: new store state `dashboardSummary` (object or `null`) and `users` (array); new store actions `fetchDashboardSummary()`, `fetchUsers()`, `createUser(userData)`, `activateUser(userId)`, `deactivateUser(userId)` — all following the same `loading`/`error` pattern as every other action in this store. Later tasks (Task 3) call these directly by name.

- [ ] **Step 1: Add `chart.js` and `vue-chartjs` dependencies**

In `bsu-registrar-queue/frontend/package.json`, change the `dependencies` block from:

```json
  "dependencies": {
    "vue": "^3.4.0",
    "vue-router": "^4.2.0",
    "pinia": "^2.1.0",
    "axios": "^1.6.0",
    "date-fns": "^3.0.0",
    "tailwindcss": "^3.4.0"
  },
```

to:

```json
  "dependencies": {
    "vue": "^3.4.0",
    "vue-router": "^4.2.0",
    "pinia": "^2.1.0",
    "axios": "^1.6.0",
    "date-fns": "^3.0.0",
    "tailwindcss": "^3.4.0",
    "chart.js": "^4.4.0",
    "vue-chartjs": "^5.3.0"
  },
```

Then, from `bsu-registrar-queue/frontend`, run:

```bash
npm install
```

Expected: installs successfully, `chart.js` and `vue-chartjs` now present under `node_modules/`.

- [ ] **Step 2: Add new state fields**

In `bsu-registrar-queue/frontend/src/stores/queue.js`, change the `state()` block from:

```js
    // Auth
    token: localStorage.getItem(TOKEN_KEY) || null,
    currentUser: null,

    // UI State
    loading: false,
    error: null,
    pollingInterval: null,
  }),
```

to:

```js
    // Auth
    token: localStorage.getItem(TOKEN_KEY) || null,
    currentUser: null,

    // Dashboard
    dashboardSummary: null,

    // Users
    users: [],

    // UI State
    loading: false,
    error: null,
    pollingInterval: null,
  }),
```

- [ ] **Step 3: Add `fetchDashboardSummary` and the User Management actions**

In the same file, change:

```js
    logout() {
      this.token = null
      this.currentUser = null
      localStorage.removeItem(TOKEN_KEY)
      this.stopPolling()
    },

    // ============ QUEUE ACTIONS ============
```

to:

```js
    logout() {
      this.token = null
      this.currentUser = null
      localStorage.removeItem(TOKEN_KEY)
      this.stopPolling()
    },

    // ============ DASHBOARD ACTIONS ============

    async fetchDashboardSummary() {
      this.loading = true
      this.error = null
      try {
        const response = await api.get('/queues/dashboard-summary')
        this.dashboardSummary = response.data
        return response.data
      } catch (err) {
        this.error = err.response?.data?.detail || 'Failed to fetch dashboard summary'
        throw err
      } finally {
        this.loading = false
      }
    },

    // ============ USER MANAGEMENT ACTIONS ============

    async fetchUsers() {
      this.loading = true
      this.error = null
      try {
        const response = await api.get('/auth/users')
        this.users = response.data
        return response.data
      } catch (err) {
        this.error = err.response?.data?.detail || 'Failed to fetch users'
        throw err
      } finally {
        this.loading = false
      }
    },

    async createUser(userData) {
      this.loading = true
      this.error = null
      try {
        const response = await api.post('/auth/register', userData)
        this.users.push(response.data)
        return response.data
      } catch (err) {
        this.error = err.response?.data?.detail || 'Failed to create user'
        throw err
      } finally {
        this.loading = false
      }
    },

    async activateUser(userId) {
      this.loading = true
      this.error = null
      try {
        await api.patch(`/auth/users/${userId}/activate`)
        const idx = this.users.findIndex(u => u.id === userId)
        if (idx !== -1) this.users[idx].is_active = true
      } catch (err) {
        this.error = err.response?.data?.detail || 'Failed to activate user'
        throw err
      } finally {
        this.loading = false
      }
    },

    async deactivateUser(userId) {
      this.loading = true
      this.error = null
      try {
        await api.patch(`/auth/users/${userId}/deactivate`)
        const idx = this.users.findIndex(u => u.id === userId)
        if (idx !== -1) this.users[idx].is_active = false
      } catch (err) {
        this.error = err.response?.data?.detail || 'Failed to deactivate user'
        throw err
      } finally {
        this.loading = false
      }
    },

    // ============ QUEUE ACTIONS ============
```

- [ ] **Step 4: Verify — build succeeds**

From `bsu-registrar-queue/frontend`, run:

```bash
npm run build
```

Expected: builds successfully with no errors (this task adds no new `.vue` files, so this is a syntax/import sanity check on `queue.js` and the new dependency).

- [ ] **Step 5: Commit**

```bash
git add bsu-registrar-queue/frontend/package.json bsu-registrar-queue/frontend/package-lock.json bsu-registrar-queue/frontend/src/stores/queue.js
git commit -m "feat(frontend): add dashboard/user-management store actions and charting dependency"
```

---

### Task 3: Frontend — sidebar layout, Dashboard, Queue Management, and User Management pages

**Files:**
- Create: `bsu-registrar-queue/frontend/src/components/AdminLayout.vue`
- Create: `bsu-registrar-queue/frontend/src/views/DashboardView.vue`
- Create: `bsu-registrar-queue/frontend/src/views/QueueManagementView.vue`
- Create: `bsu-registrar-queue/frontend/src/views/UserManagementView.vue`
- Modify: `bsu-registrar-queue/frontend/src/router/index.js`
- Delete: `bsu-registrar-queue/frontend/src/views/AdminView.vue`

**Interfaces:**
- Consumes: Task 2's store state/actions (`dashboardSummary`, `users`, `fetchDashboardSummary`, `fetchUsers`, `createUser`, `activateUser`, `deactivateUser`) and Task 1's endpoint (indirectly, via those store actions). Also consumes existing store state/actions unchanged: `currentUser`, `isAuthenticated`, `logout`, `fetchCurrentUser`, `fetchQueues`, `pauseQueue`, `resumeQueue`, `closeQueue`, `deleteQueue`, `createQueue`, `serveNextTicket`, `completeTicket`, `fetchQueueDisplay`, `queueDisplay`, `queues`.
- Produces: routes `admin-dashboard` (`/admin`), `admin-queues` (`/admin/queues`), `admin-users` (`/admin/users`, admin-only).

- [ ] **Step 1: Create `AdminLayout.vue`**

Create `bsu-registrar-queue/frontend/src/components/AdminLayout.vue`:

```vue
<template>
  <div class="min-h-screen bg-gray-50 flex flex-col">
    <AppHeader subtitle="Registrar Staff Dashboard">
      <template #actions>
        <span class="hidden md:block text-sm text-pink-100">
          Logged in as: {{ queueStore.currentUser?.full_name || queueStore.currentUser?.username || 'Staff' }}
        </span>
        <button
          @click="logout"
          class="px-3 py-1.5 text-sm font-medium rounded-md bg-red-600 hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500"
        >
          Logout
        </button>
      </template>
    </AppHeader>

    <div class="flex-1 flex max-w-7xl mx-auto w-full">
      <aside class="w-56 flex-shrink-0 border-r border-gray-200 bg-white py-6 px-3 hidden sm:block">
        <nav class="space-y-1">
          <router-link
            to="/admin"
            class="block px-3 py-2 rounded-md text-sm font-medium"
            :class="route.path === '/admin' ? 'bg-bsu-primary/10 text-bsu-primary' : 'text-gray-700 hover:bg-gray-100'"
          >
            Dashboard
          </router-link>
          <router-link
            to="/admin/queues"
            class="block px-3 py-2 rounded-md text-sm font-medium"
            :class="route.path === '/admin/queues' ? 'bg-bsu-primary/10 text-bsu-primary' : 'text-gray-700 hover:bg-gray-100'"
          >
            Queue Management
          </router-link>
          <router-link
            v-if="queueStore.currentUser?.role === 'admin'"
            to="/admin/users"
            class="block px-3 py-2 rounded-md text-sm font-medium"
            :class="route.path === '/admin/users' ? 'bg-bsu-primary/10 text-bsu-primary' : 'text-gray-700 hover:bg-gray-100'"
          >
            User Management
          </router-link>
        </nav>
      </aside>

      <main class="flex-1 px-4 sm:px-6 lg:px-8 py-8 min-w-0">
        <router-view />
      </main>
    </div>

    <AppFooter />
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useQueueStore } from '@/stores/queue'
import AppHeader from '@/components/AppHeader.vue'
import AppFooter from '@/components/AppFooter.vue'

const queueStore = useQueueStore()
const router = useRouter()
const route = useRoute()

const logout = () => {
  queueStore.logout()
  router.push('/login')
}

onMounted(async () => {
  try {
    await queueStore.fetchCurrentUser()
  } catch (err) {
    queueStore.logout()
    router.push('/login')
  }
})
</script>
```

- [ ] **Step 2: Create `DashboardView.vue`**

Create `bsu-registrar-queue/frontend/src/views/DashboardView.vue`:

```vue
<template>
  <div>
    <div class="mb-8">
      <h2 class="text-3xl font-bold text-gray-900">Dashboard</h2>
      <p class="mt-2 text-gray-600">Overview of queues, tickets, and staff</p>
    </div>

    <div v-if="summaryError" class="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
      <p class="text-sm text-red-700">{{ summaryError }}</p>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-4 gap-6 mb-6">
      <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
        <p class="text-sm text-gray-500">Users</p>
        <p class="text-2xl font-bold text-gray-900">{{ summary?.users_count ?? 0 }}</p>
      </div>
      <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
        <p class="text-sm text-gray-500">Queues</p>
        <p class="text-2xl font-bold text-gray-900">{{ summary?.queues_count ?? 0 }}</p>
      </div>
      <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
        <p class="text-sm text-gray-500">Active Queues</p>
        <p class="text-2xl font-bold text-gray-900">{{ summary?.active_queues_count ?? 0 }}</p>
      </div>
      <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
        <p class="text-sm text-gray-500">Waiting</p>
        <p class="text-2xl font-bold text-gray-900">{{ summary?.waiting_count ?? 0 }}</p>
      </div>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
      <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
        <p class="text-sm text-gray-500">Serving</p>
        <p class="text-2xl font-bold text-gray-900">{{ summary?.serving_count ?? 0 }}</p>
      </div>
      <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
        <p class="text-sm text-gray-500">Completed Today</p>
        <p class="text-2xl font-bold text-gray-900">{{ summary?.completed_today_count ?? 0 }}</p>
      </div>
      <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
        <p class="text-sm text-gray-500">No-Shows</p>
        <p class="text-2xl font-bold text-gray-900">{{ summary?.no_shows_today_count ?? 0 }}</p>
      </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
        <h3 class="text-lg font-medium text-gray-900 mb-4">Tickets Today by Queue</h3>
        <div v-if="hasQueueData" class="h-64">
          <Bar :data="barData" :options="barOptions" />
        </div>
        <p v-else class="text-center text-gray-500 py-8">No tickets today</p>
      </div>

      <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
        <h3 class="text-lg font-medium text-gray-900 mb-4">Today's Tickets by Status</h3>
        <div v-if="hasStatusData" class="h-64">
          <Doughnut :data="doughnutData" :options="doughnutOptions" />
        </div>
        <p v-else class="text-center text-gray-500 py-8">No tickets today</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { Bar, Doughnut } from 'vue-chartjs'
import {
  Chart as ChartJS,
  Title,
  Tooltip,
  Legend,
  BarElement,
  ArcElement,
  CategoryScale,
  LinearScale,
} from 'chart.js'
import { useQueueStore } from '@/stores/queue'

ChartJS.register(Title, Tooltip, Legend, BarElement, ArcElement, CategoryScale, LinearScale)

const queueStore = useQueueStore()
const summaryError = ref('')

const summary = computed(() => queueStore.dashboardSummary)

const hasQueueData = computed(() => (summary.value?.tickets_today_by_queue?.length ?? 0) > 0)
const hasStatusData = computed(() => {
  const byStatus = summary.value?.tickets_today_by_status
  return !!byStatus && Object.values(byStatus).some((count) => count > 0)
})

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

const barOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { display: false } },
  scales: {
    y: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: '#e5e7eb' } },
    x: { grid: { display: false } },
  },
}

const STATUS_LABELS = {
  waiting: 'Waiting',
  serving: 'Serving',
  completed: 'Completed',
  cancelled: 'Cancelled',
  no_show: 'No-Show',
}

const STATUS_COLORS = {
  waiting: '#2a78d6',
  serving: '#eda100',
  completed: '#008300',
  cancelled: '#4a3aa7',
  no_show: '#e34948',
}

const doughnutData = computed(() => {
  const byStatus = summary.value?.tickets_today_by_status ?? {}
  const keys = Object.keys(STATUS_LABELS).filter((key) => key in byStatus)
  return {
    labels: keys.map((key) => STATUS_LABELS[key]),
    datasets: [
      {
        data: keys.map((key) => byStatus[key]),
        backgroundColor: keys.map((key) => STATUS_COLORS[key]),
        borderWidth: 0,
      },
    ],
  }
})

const doughnutOptions = {
  responsive: true,
  maintainAspectRatio: false,
  cutout: '60%',
  plugins: { legend: { position: 'bottom' } },
}

onMounted(async () => {
  try {
    await queueStore.fetchDashboardSummary()
  } catch (err) {
    summaryError.value = err.response?.data?.detail || 'Failed to load dashboard summary'
  }
})
</script>
```

- [ ] **Step 3: Create `QueueManagementView.vue`**

Create `bsu-registrar-queue/frontend/src/views/QueueManagementView.vue`:

```vue
<template>
  <div>
    <div class="mb-8">
      <h2 class="text-3xl font-bold text-gray-900">Queue Management</h2>
      <p class="mt-2 text-gray-600">Manage queues and serve tickets</p>
    </div>

    <div v-if="dashboardError" class="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
      <p class="text-sm text-red-700">{{ dashboardError }}</p>
    </div>

    <div class="bg-white rounded-xl shadow-sm border border-gray-100 mb-6">
      <div class="bg-bsu-primary/5 border-b border-bsu-primary/10 px-6 py-4">
        <h3 class="text-xl font-bold text-gray-900">Queue Management</h3>
      </div>
      <div class="p-6">
        <div v-if="queues.length > 0" class="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div
            v-for="queue in queues"
            :key="queue.id"
            class="border border-gray-200 rounded-lg p-4"
          >
            <div class="flex items-center justify-between mb-3">
              <div class="flex items-center space-x-3">
                <component :is="getQueueIcon(queue.queue_type)" class="w-8 h-8 text-bsu-primary" />
                <div>
                  <h4 class="font-medium text-gray-900">{{ queue.name }}</h4>
                  <p class="text-sm text-gray-500">{{ formatQueueType(queue.queue_type) }}</p>
                </div>
              </div>
              <StatusBadge :status="queue.status" />
            </div>

            <div class="text-sm text-gray-500 mb-3">
              <p>Capacity: {{ queue.max_capacity }} | Slot: {{ queue.slot_duration_minutes }} min</p>
            </div>

            <div class="flex space-x-2">
              <button
                v-if="queue.status === 'active'"
                @click="pauseQueue(queue.id)"
                :disabled="loading"
                class="flex-1 px-3 py-1.5 text-sm font-medium rounded-md bg-yellow-100 text-yellow-800 hover:bg-yellow-200 focus:outline-none focus:ring-2 focus:ring-yellow-500 disabled:opacity-50"
              >
                Pause
              </button>
              <button
                v-else-if="queue.status === 'paused'"
                @click="resumeQueue(queue.id)"
                :disabled="loading"
                class="flex-1 px-3 py-1.5 text-sm font-medium rounded-md bg-green-100 text-green-800 hover:bg-green-200 focus:outline-none focus:ring-2 focus:ring-green-500 disabled:opacity-50"
              >
                Resume
              </button>
              <button
                v-if="queue.status !== 'closed'"
                @click="closeQueue(queue.id)"
                :disabled="loading"
                class="flex-1 px-3 py-1.5 text-sm font-medium rounded-md bg-red-100 text-red-800 hover:bg-red-200 focus:outline-none focus:ring-2 focus:ring-red-500 disabled:opacity-50"
              >
                Close
              </button>
              <router-link
                :to="`/display/${queue.id}`"
                target="_blank"
                class="flex-1 inline-flex justify-center items-center px-3 py-1.5 text-sm font-medium rounded-md bg-gray-100 text-gray-700 hover:bg-gray-200"
              >
                Display Board
              </router-link>
              <button
                @click="deleteQueue(queue.id)"
                :disabled="loading"
                class="flex-1 px-3 py-1.5 text-sm font-medium rounded-md bg-red-600 text-white hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-600 disabled:opacity-50"
              >
                Delete
              </button>
            </div>
          </div>
        </div>

        <div v-else class="text-center py-8">
          <svg class="mx-auto h-12 w-12 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-5.586a1 1 0 01-.707-.293L9 5z" />
          </svg>
          <p class="mt-2 text-gray-500">No queues found. Create a new queue to get started.</p>
        </div>

        <div class="mt-6">
          <button
            @click="showCreateQueueModal = true"
            class="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-bsu-primary hover:bg-pink-800 focus:outline-none focus:ring-2 focus:ring-bsu-primary"
          >
            <svg class="mr-2 -ml-1 w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
            </svg>
            Create New Queue
          </button>
        </div>
      </div>
    </div>

    <div class="bg-white rounded-xl shadow-sm border border-gray-100 mb-6">
      <div class="bg-bsu-primary/5 border-b border-bsu-primary/10 px-6 py-4 flex items-center justify-between">
        <h3 class="text-xl font-bold text-gray-900">Queue Display</h3>
        <router-link to="/display" target="_blank" class="text-sm font-medium text-bsu-primary hover:underline">
          View All Boards ↗
        </router-link>
      </div>
      <div class="p-6">
        <div class="flex items-center justify-between mb-4">
          <h4 class="text-lg font-medium text-gray-900">{{ selectedQueue?.name || 'No queue selected' }}</h4>
          <select
            v-model="selectedQueueId"
            class="px-3 py-1.5 border border-gray-300 rounded-md focus:outline-none focus:ring-bsu-primary"
          >
            <option :value="null">Select Queue</option>
            <option :value="q.id" v-for="q in queues" :key="q.id">
              {{ q.name }}
            </option>
          </select>
        </div>

        <div v-if="selectedQueue" class="space-y-4">
          <div class="bg-gray-50 rounded-lg p-6">
            <div class="text-center mb-6">
              <h5 class="text-sm text-gray-500 uppercase tracking-wide">CURRENTLY SERVING</h5>
              <div class="mt-2">
                <span
                  v-if="servingTicket"
                  class="inline-block px-6 py-3 bg-bsu-primary text-white text-3xl font-bold rounded-full"
                >
                  {{ servingTicket.ticket_number }}
                </span>
                <span
                  v-else
                  class="inline-block px-6 py-3 bg-gray-200 text-gray-600 text-3xl font-bold rounded-full"
                >
                  --
                </span>
              </div>
            </div>

            <div class="border-t border-gray-200 pt-4">
              <h5 class="text-sm text-gray-500 uppercase tracking-wide mb-3">Waiting Queue</h5>
              <div class="space-y-2">
                <div
                  v-for="ticket in queueDisplay"
                  :key="ticket.id"
                  class="flex items-center justify-between px-3 py-2 rounded-md"
                  :class="ticket.priority === 'urgent' ? 'bg-red-50 border-l-4 border-red-400' : ticket.priority === 'priority' ? 'bg-yellow-50 border-l-4 border-yellow-400' : 'bg-white border border-gray-200'"
                >
                  <div class="flex items-center space-x-3">
                    <span class="font-medium text-gray-900">#{{ ticket.ticket_number }}</span>
                    <span v-if="ticket.priority !== 'normal'" class="text-xs px-2 py-0.5 rounded-full"
                      :class="ticket.priority === 'urgent' ? 'bg-red-100 text-red-800' : 'bg-yellow-100 text-yellow-800'"
                    >
                      {{ ticket.priority }}
                    </span>
                  </div>
                  <svg class="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 5l7 7-7 7" />
                  </svg>
                </div>

                <div v-if="queueDisplay.length === 0" class="text-center py-4 text-gray-500">
                  No tickets waiting
                </div>
              </div>
            </div>
          </div>

          <div class="flex space-x-3 pt-4">
            <button
              @click="serveNextTicket"
              :disabled="loading || queueDisplay.length === 0"
              class="flex-1 px-4 py-2 text-sm font-medium rounded-md text-white bg-bsu-primary hover:bg-pink-800 focus:outline-none focus:ring-2 focus:ring-bsu-primary disabled:opacity-50"
            >
              <span v-if="!loading">Serve Next Ticket</span>
              <span v-else>Processing...</span>
            </button>
            <button
              @click="completeCurrentTicket"
              :disabled="loading || !servingTicket"
              class="flex-1 px-4 py-2 text-sm font-medium rounded-md text-white bg-green-600 hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500 disabled:opacity-50"
            >
              <span v-if="!loading">Mark Complete</span>
              <span v-else>Processing...</span>
            </button>
          </div>
        </div>
        <div v-else class="text-center py-8">
          <p class="text-gray-500">Select a queue to view the display board</p>
        </div>
      </div>
    </div>

    <div v-if="showCreateQueueModal" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div class="bg-white rounded-xl shadow-xl max-w-md w-full mx-4">
        <div class="px-6 py-4 border-b border-gray-200">
          <h3 class="text-lg font-bold text-gray-900">Create New Queue</h3>
        </div>
        <div class="px-6 py-4 space-y-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Queue Name</label>
            <input
              v-model="newQueueForm.name"
              type="text"
              class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-bsu-primary"
              placeholder="e.g., Document Request"
            />
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Queue Type</label>
            <select
              v-model="newQueueForm.queue_type"
              class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-bsu-primary"
            >
              <option :value="type.value" v-for="type in queueTypeOptions" :key="type.value">
                {{ type.label }}
              </option>
            </select>
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Description</label>
            <textarea
              v-model="newQueueForm.description"
              rows="2"
              class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-bsu-primary"
              placeholder="Brief description of the service"
            ></textarea>
          </div>

          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">Max Capacity</label>
              <input
                v-model.number="newQueueForm.max_capacity"
                type="number"
                min="1"
                max="200"
                class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-bsu-primary"
              />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">Slot Duration (min)</label>
              <input
                v-model.number="newQueueForm.slot_duration_minutes"
                type="number"
                min="5"
                max="120"
                class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-bsu-primary"
              />
            </div>
          </div>

          <div class="flex items-center">
            <input
              id="allow_priority"
              type="checkbox"
              v-model="newQueueForm.allow_priority"
              class="h-4 w-4 text-bsu-primary border-gray-300 rounded"
            />
            <label for="allow_priority" class="ml-2 text-sm text-gray-700">
              Allow Priority Access
            </label>
          </div>

          <div v-if="createQueueError" class="p-3 bg-red-50 border border-red-200 rounded-lg">
            <p class="text-sm text-red-700">{{ createQueueError }}</p>
          </div>
        </div>

        <div class="px-6 py-4 border-t border-gray-200 flex justify-end space-x-3">
          <button
            @click="showCreateQueueModal = false"
            class="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200 focus:outline-none focus:ring-2 focus:ring-bsu-primary"
          >
            Cancel
          </button>
          <button
            @click="createQueue"
            :disabled="loading"
            class="px-4 py-2 text-sm font-medium text-white bg-bsu-primary rounded-md hover:bg-pink-800 focus:outline-none focus:ring-2 focus:ring-bsu-primary disabled:opacity-50"
          >
            Create
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useQueueStore } from '@/stores/queue'
import StatusBadge from '@/components/StatusBadge.vue'
import { getQueueIcon, formatQueueType } from '@/components/icons/QueueIcons'

const queueStore = useQueueStore()

const loading = ref(false)
const dashboardError = ref('')
const createQueueError = ref('')
const showCreateQueueModal = ref(false)

const queues = ref([])
const selectedQueueId = ref(null)
const selectedQueue = computed(() => queues.value.find(q => q.id === selectedQueueId.value))
const queueDisplay = ref([])
const servingTicket = ref(null)

const newQueueForm = ref({
  name: '',
  queue_type: 'enrollment',
  description: '',
  max_capacity: 50,
  slot_duration_minutes: 30,
  allow_priority: true,
})

const queueTypeOptions = [
  { value: 'enrollment', label: 'Enrollment' },
  { value: 'document_request', label: 'Document Request' },
  { value: 'clearance', label: 'Clearance' },
  { value: 'scholarship', label: 'Scholarship' },
  { value: 'others', label: 'Others' },
]

const loadQueues = async () => {
  dashboardError.value = ''
  try {
    await queueStore.fetchQueues()
    queues.value = queueStore.queues
  } catch (err) {
    dashboardError.value = err.response?.data?.detail || 'Failed to load queues'
  }
}

const pauseQueue = async (queueId) => {
  loading.value = true
  try {
    await queueStore.pauseQueue(queueId)
    await loadQueues()
  } catch (err) {
    dashboardError.value = err.response?.data?.detail || 'Failed to pause queue'
  } finally {
    loading.value = false
  }
}

const resumeQueue = async (queueId) => {
  loading.value = true
  try {
    await queueStore.resumeQueue(queueId)
    await loadQueues()
  } catch (err) {
    dashboardError.value = err.response?.data?.detail || 'Failed to resume queue'
  } finally {
    loading.value = false
  }
}

const closeQueue = async (queueId) => {
  loading.value = true
  try {
    await queueStore.closeQueue(queueId)
    await loadQueues()
  } catch (err) {
    dashboardError.value = err.response?.data?.detail || 'Failed to close queue'
  } finally {
    loading.value = false
  }
}

const deleteQueue = async (queueId) => {
  if (!confirm('Are you sure you want to delete this queue? This cannot be undone.')) return
  loading.value = true
  try {
    await queueStore.deleteQueue(queueId)
    queues.value = queues.value.filter((q) => q.id !== queueId)
    await loadQueues()
  } catch (err) {
    dashboardError.value = err.response?.data?.detail || 'Failed to delete queue'
  } finally {
    loading.value = false
  }
}

const createQueue = async () => {
  if (!newQueueForm.value.name) return

  loading.value = true
  createQueueError.value = ''
  try {
    await queueStore.createQueue(newQueueForm.value)
    showCreateQueueModal.value = false
    newQueueForm.value = {
      name: '',
      queue_type: 'enrollment',
      description: '',
      max_capacity: 50,
      slot_duration_minutes: 30,
      allow_priority: true,
    }
    await loadQueues()
  } catch (err) {
    createQueueError.value = err.response?.data?.detail || 'Failed to create queue'
  } finally {
    loading.value = false
  }
}

const serveNextTicket = async () => {
  if (!selectedQueueId.value) return

  loading.value = true
  try {
    const result = await queueStore.serveNextTicket(selectedQueueId.value)
    servingTicket.value = result
    await updateQueueDisplay()
  } catch (err) {
    dashboardError.value = err.response?.data?.detail || 'No waiting tickets'
  } finally {
    loading.value = false
  }
}

const completeCurrentTicket = async () => {
  if (!servingTicket.value) return

  loading.value = true
  try {
    await queueStore.completeTicket(servingTicket.value.id)
    servingTicket.value = null
    await updateQueueDisplay()
  } catch (err) {
    dashboardError.value = err.response?.data?.detail || 'Failed to complete ticket'
  } finally {
    loading.value = false
  }
}

const updateQueueDisplay = async () => {
  if (!selectedQueueId.value) return
  try {
    await queueStore.fetchQueueDisplay(selectedQueueId.value)
    queueDisplay.value = queueStore.queueDisplay.map(t => ({
      ...t,
      priority: t.priority || 'normal',
    }))
  } catch (err) {
    queueDisplay.value = []
  }
}

let displayRefreshTimer = null

onMounted(async () => {
  await loadQueues()
  displayRefreshTimer = setInterval(() => {
    if (selectedQueueId.value) {
      updateQueueDisplay()
    }
  }, 5000)
})

onUnmounted(() => {
  if (displayRefreshTimer) clearInterval(displayRefreshTimer)
})
</script>
```

- [ ] **Step 4: Create `UserManagementView.vue`**

Create `bsu-registrar-queue/frontend/src/views/UserManagementView.vue`:

```vue
<template>
  <div>
    <div class="mb-8 flex items-center justify-between">
      <div>
        <h2 class="text-3xl font-bold text-gray-900">User Management</h2>
        <p class="mt-2 text-gray-600">Manage registrar staff accounts</p>
      </div>
      <button
        @click="openCreateModal"
        class="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-bsu-primary hover:bg-pink-800 focus:outline-none focus:ring-2 focus:ring-bsu-primary"
      >
        <svg class="mr-2 -ml-1 w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
        </svg>
        Create User
      </button>
    </div>

    <div v-if="listError" class="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
      <p class="text-sm text-red-700">{{ listError }}</p>
    </div>

    <div class="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
      <table class="min-w-full divide-y divide-gray-200">
        <thead class="bg-gray-50">
          <tr>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Username</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Full Name</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Role</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
            <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-200">
          <tr v-for="user in queueStore.users" :key="user.id">
            <td class="px-6 py-4 text-sm font-medium text-gray-900">{{ user.username }}</td>
            <td class="px-6 py-4 text-sm text-gray-500">{{ user.full_name }}</td>
            <td class="px-6 py-4 text-sm text-gray-500 capitalize">{{ user.role }}</td>
            <td class="px-6 py-4">
              <StatusBadge :status="user.is_active ? 'active' : 'inactive'" />
            </td>
            <td class="px-6 py-4 text-right">
              <button
                v-if="user.is_active"
                @click="deactivate(user.id)"
                :disabled="actionLoading"
                class="px-3 py-1.5 text-sm font-medium rounded-md bg-red-100 text-red-800 hover:bg-red-200 disabled:opacity-50"
              >
                Deactivate
              </button>
              <button
                v-else
                @click="activate(user.id)"
                :disabled="actionLoading"
                class="px-3 py-1.5 text-sm font-medium rounded-md bg-green-100 text-green-800 hover:bg-green-200 disabled:opacity-50"
              >
                Activate
              </button>
            </td>
          </tr>

          <tr v-if="queueStore.users.length === 0">
            <td colspan="5" class="px-6 py-8 text-center text-gray-500">No staff accounts found.</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="showCreateModal" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div class="bg-white rounded-xl shadow-xl max-w-md w-full mx-4">
        <div class="px-6 py-4 border-b border-gray-200">
          <h3 class="text-lg font-bold text-gray-900">Create User</h3>
        </div>
        <div class="px-6 py-4 space-y-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Username</label>
            <input
              v-model="newUserForm.username"
              type="text"
              class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-bsu-primary"
              placeholder="e.g., jsantos"
            />
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Full Name</label>
            <input
              v-model="newUserForm.full_name"
              type="text"
              class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-bsu-primary"
              placeholder="e.g., Juan Santos"
            />
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Role</label>
            <select
              v-model="newUserForm.role"
              class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-bsu-primary"
            >
              <option value="admin">Admin</option>
              <option value="registrar">Registrar</option>
              <option value="staff">Staff</option>
            </select>
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Password</label>
            <input
              v-model="newUserForm.password"
              type="password"
              class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-bsu-primary"
              placeholder="At least 8 characters"
            />
          </div>

          <div v-if="createError" class="p-3 bg-red-50 border border-red-200 rounded-lg">
            <p class="text-sm text-red-700">{{ createError }}</p>
          </div>
        </div>

        <div class="px-6 py-4 border-t border-gray-200 flex justify-end space-x-3">
          <button
            @click="showCreateModal = false"
            class="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200 focus:outline-none focus:ring-2 focus:ring-bsu-primary"
          >
            Cancel
          </button>
          <button
            @click="createUser"
            :disabled="actionLoading"
            class="px-4 py-2 text-sm font-medium text-white bg-bsu-primary rounded-md hover:bg-pink-800 focus:outline-none focus:ring-2 focus:ring-bsu-primary disabled:opacity-50"
          >
            Create
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useQueueStore } from '@/stores/queue'
import StatusBadge from '@/components/StatusBadge.vue'

const queueStore = useQueueStore()

const listError = ref('')
const createError = ref('')
const actionLoading = ref(false)
const showCreateModal = ref(false)

const newUserForm = ref({
  username: '',
  full_name: '',
  role: 'staff',
  password: '',
})

const openCreateModal = () => {
  createError.value = ''
  newUserForm.value = { username: '', full_name: '', role: 'staff', password: '' }
  showCreateModal.value = true
}

const createUser = async () => {
  if (!newUserForm.value.username || !newUserForm.value.full_name || !newUserForm.value.password) return

  actionLoading.value = true
  createError.value = ''
  try {
    await queueStore.createUser(newUserForm.value)
    showCreateModal.value = false
  } catch (err) {
    createError.value = err.response?.data?.detail || 'Failed to create user'
  } finally {
    actionLoading.value = false
  }
}

const activate = async (userId) => {
  actionLoading.value = true
  listError.value = ''
  try {
    await queueStore.activateUser(userId)
  } catch (err) {
    listError.value = err.response?.data?.detail || 'Failed to activate user'
  } finally {
    actionLoading.value = false
  }
}

const deactivate = async (userId) => {
  actionLoading.value = true
  listError.value = ''
  try {
    await queueStore.deactivateUser(userId)
  } catch (err) {
    listError.value = err.response?.data?.detail || 'Failed to deactivate user'
  } finally {
    actionLoading.value = false
  }
}

onMounted(async () => {
  try {
    await queueStore.fetchUsers()
  } catch (err) {
    listError.value = err.response?.data?.detail || 'Failed to load users'
  }
})
</script>
```

- [ ] **Step 5: Restructure the router into nested `/admin` routes with the admin-only guard**

Replace the full contents of `bsu-registrar-queue/frontend/src/router/index.js`:

```js
import { createRouter, createWebHistory } from 'vue-router'
import { useQueueStore } from '../stores/queue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'home',
      component: () => import('../views/HomeView.vue')
    },
    {
      path: '/login',
      name: 'login',
      component: () => import('../views/LoginView.vue')
    },
    {
      path: '/queues',
      name: 'queues',
      component: () => import('../views/QueuesView.vue')
    },
    {
      path: '/queues/:id',
      name: 'queue-detail',
      component: () => import('../views/QueueDetailView.vue')
    },
    {
      path: '/admin',
      component: () => import('../components/AdminLayout.vue'),
      meta: { requiresAuth: true },
      children: [
        {
          path: '',
          name: 'admin-dashboard',
          component: () => import('../views/DashboardView.vue')
        },
        {
          path: 'queues',
          name: 'admin-queues',
          component: () => import('../views/QueueManagementView.vue')
        },
        {
          path: 'users',
          name: 'admin-users',
          component: () => import('../views/UserManagementView.vue'),
          meta: { requiresAdmin: true }
        }
      ]
    },
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
  ]
})

router.beforeEach(async (to) => {
  const queueStore = useQueueStore()

  if (to.meta.requiresAuth && !queueStore.isAuthenticated) {
    return { name: 'login' }
  }

  if (to.meta.requiresAdmin) {
    if (!queueStore.currentUser) {
      try {
        await queueStore.fetchCurrentUser()
      } catch (err) {
        return { name: 'login' }
      }
    }
    if (queueStore.currentUser?.role !== 'admin') {
      return { name: 'admin-dashboard' }
    }
  }
})

export default router
```

- [ ] **Step 6: Delete the old `AdminView.vue`**

```bash
git rm bsu-registrar-queue/frontend/src/views/AdminView.vue
```

- [ ] **Step 7: Start the full dev stack**

From `bsu-registrar-queue/`, run `.\dev.ps1` (or restart the frontend/backend windows if already running, to pick up the router/store changes). Wait for both "Backend: http://localhost:8000" and "Frontend: http://localhost:5173" to print.

- [ ] **Step 8: Verify — Admin sees all 3 sidebar sections, Dashboard renders real data**

Log in at `http://localhost:5173/login` as `admin` / `admin123`, portal Admin. Expected: lands on `/admin`, sidebar shows Dashboard / Queue Management / User Management, all 3 clickable. Dashboard page shows 7 stat tiles with real numbers (not all zero, given seed data and any tickets created during Task 1's verification) and both charts render (bar chart with at least one bar if any ticket was created today, donut chart with at least one slice).

- [ ] **Step 9: Verify — Queue Management still works unchanged**

Click "Queue Management" in the sidebar (lands on `/admin/queues`). Expected: queue list renders with Pause/Resume/Close/Delete/Display Board buttons behaving as before; "Create New Queue" modal opens and creates a queue; selecting a queue in "Queue Display" shows currently-serving ticket and waiting list; "Serve Next Ticket" / "Mark Complete" work.

- [ ] **Step 10: Verify — User Management works end-to-end**

Click "User Management" (`/admin/users`). Expected: table lists the 3 seeded staff accounts (admin/registrar/staff). Click "Create User", fill in a new username/full name/role/password, submit — new row appears. Click "Deactivate" on that new user — status badge changes to "inactive" and the button becomes "Activate"; click "Activate" — reverts.

- [ ] **Step 11: Verify — non-Admin cannot reach User Management**

Log out, log back in as `staff` / `staff123` (portal Counter). Expected: sidebar shows only Dashboard and Queue Management (no User Management link). Manually navigate the browser to `http://localhost:5173/admin/users`. Expected: redirected back to `/admin` (the Dashboard), not shown the user table.

- [ ] **Step 12: Commit**

```bash
git add bsu-registrar-queue/frontend/src/components/AdminLayout.vue \
        bsu-registrar-queue/frontend/src/views/DashboardView.vue \
        bsu-registrar-queue/frontend/src/views/QueueManagementView.vue \
        bsu-registrar-queue/frontend/src/views/UserManagementView.vue \
        bsu-registrar-queue/frontend/src/router/index.js \
        bsu-registrar-queue/frontend/src/views/AdminView.vue
git commit -m "feat(frontend): split admin dashboard into sidebar layout with Dashboard/Queue Management/User Management pages"
```
