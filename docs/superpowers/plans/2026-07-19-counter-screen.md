# Counter Screen Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A dedicated staff "Counter" screen for actively serving tickets (pick a queue, see the currently-serving ticket with Call/Skip/Complete actions and a priority-ordered waiting list), plus a lightweight "Call" signal that makes the single-queue public display board briefly pulse and chime.

**Architecture:** A new `called_at` timestamp column on tickets, exposed through both the staff-facing `Ticket` schema and the public `TicketPublic` schema (which also gains a `priority` field it was missing). A new `POST /api/tickets/{id}/call` endpoint records the timestamp without changing ticket status. The frontend gets a new dedicated `CounterView.vue` page reusing the existing serve/complete/no-show actions, and the existing single-queue display board detects `called_at` changes on its regular poll to trigger a CSS pulse plus a synthesized audio chime (Web Audio API, no new audio asset).

**Tech Stack:** FastAPI, SQLAlchemy 2.0, Pydantic v2 (backend); Vue 3 (Composition API), Pinia, Vue Router, Tailwind CSS (frontend).

## Global Constraints

- No new "Counter" entity/table — "Counter" is purely a new staff screen; queue selection works exactly like the existing Queue Management panel.
- Waiting tickets render as a single ordered list with Priority/Urgent badges (no badge for Normal) — no separate visual lanes.
- "Call" (`POST /tickets/{id}/call`) never changes ticket `status`, `position`, or anything else — it only records `called_at`. Gated the same as serve/complete/no-show: `require_role(UserRole.ADMIN, UserRole.REGISTRAR, UserRole.STAFF)` — **all three roles**, not just Admin/Registrar.
- "Skip" reuses the existing, already-built `POST /tickets/{id}/no-show` endpoint verbatim — no backend change needed for Skip itself.
- The Call pulse/chime effect only applies to the single-queue display board (`/display/:id`) — the all-queues overview page is explicitly unaffected.
- A blocked/failed audio chime (browser autoplay policy) must fail silently — the visual pulse must still happen regardless.
- **`TicketPublic` currently has no `priority` field at all**, which means the existing `QueueManagementView.vue` waiting list has always silently shown every ticket as "normal" priority regardless of its real priority (its own code defensively falls back with `priority: t.priority || 'normal'`, and `t.priority` was always `undefined`). Adding `priority` to `TicketPublic` in this plan is a genuine prerequisite for the Counter screen's waiting-list badges to work at all, and it also transparently fixes this pre-existing bug in `QueueManagementView.vue` for free — no changes to that file are needed for the fix to take effect, since it reads from the same underlying data.
- No automated test framework is configured for this project — verification is manual against the real running dev stack, per prior specs in this project.
- Seeded dev accounts: `admin/admin123` (Admin), `registrar/registrar123` (Registrar), `staff/staff123` (Staff). Seeded students with non-Normal priority: external `student_id` `2022000045` (Maria Santos, scholar → Priority), `2021000001` (Juan Dela Cruz, graduating → Urgent).

---

### Task 1: Backend — `called_at`, `priority` on `TicketPublic`, and the Call endpoint

**Files:**
- Modify: `bsu-registrar-queue/backend/app/db_models.py`
- Modify: `bsu-registrar-queue/backend/app/models/ticket.py`
- Modify: `bsu-registrar-queue/backend/app/services/ticket_service.py`
- Modify: `bsu-registrar-queue/backend/app/api/tickets.py`

**Interfaces:**
- Produces: `POST /api/tickets/{ticket_id}/call` (Admin/Registrar/Staff-gated) → returns the full `Ticket` (unchanged shape plus a `called_at` field). `TicketPublic` (used by `GET /api/tickets/queue/{id}/display`) gains `priority` and `called_at` fields. `TicketService.call_ticket(ticket_id) -> Optional[Ticket]`.

- [ ] **Step 1: Add the `called_at` column**

In `bsu-registrar-queue/backend/app/db_models.py`, change:

```python
    served_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    student = relationship("StudentDB", back_populates="tickets")
    queue = relationship("QueueDB", back_populates="tickets")
```

to:

```python
    served_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    called_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    student = relationship("StudentDB", back_populates="tickets")
    queue = relationship("QueueDB", back_populates="tickets")
```

- [ ] **Step 2: Add `called_at` to `Ticket`, and `priority`/`called_at` to `TicketPublic`**

In `bsu-registrar-queue/backend/app/models/ticket.py`, change:

```python
class Ticket(TicketBase):
    id: int
    ticket_number: int
    status: TicketStatus = TicketStatus.WAITING
    position: int
    estimated_wait_time_minutes: Optional[int] = None
    served_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    queue_name: Optional[str] = None

    class Config:
        from_attributes = True


class TicketInDB(Ticket):
    id: int


class TicketPublic(BaseModel):
    """Ticket data safe to expose to students (hides sensitive info)"""
    ticket_number: int
    queue_name: str
    position: int
    status: TicketStatus
    estimated_wait_time_minutes: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True
```

to:

```python
class Ticket(TicketBase):
    id: int
    ticket_number: int
    status: TicketStatus = TicketStatus.WAITING
    position: int
    estimated_wait_time_minutes: Optional[int] = None
    served_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    called_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    queue_name: Optional[str] = None

    class Config:
        from_attributes = True


class TicketInDB(Ticket):
    id: int


class TicketPublic(BaseModel):
    """Ticket data safe to expose to students (hides sensitive info)"""
    ticket_number: int
    queue_name: str
    position: int
    status: TicketStatus
    priority: PriorityLevel
    estimated_wait_time_minutes: Optional[int]
    called_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True
```

- [ ] **Step 3: Add `TicketService.call_ticket`, and include `priority`/`called_at` in `get_queue_display` and `_to_ticket`**

In `bsu-registrar-queue/backend/app/services/ticket_service.py`, change:

```python
    def mark_no_show(self, ticket_id: int) -> Optional[Ticket]:
```

to (inserting the new method immediately before `mark_no_show`):

```python
    def call_ticket(self, ticket_id: int) -> Optional[Ticket]:
        """Record that staff called this ticket again (does not change status)"""
        ticket = self.db.query(TicketDB).filter(TicketDB.id == ticket_id).first()
        if not ticket:
            return None

        ticket.called_at = datetime.now()
        ticket.updated_at = datetime.now()
        self.db.commit()
        self.db.refresh(ticket)

        student = self.db.query(StudentDB).filter(StudentDB.id == ticket.student_id).first()
        queue = self.db.query(QueueDB).filter(QueueDB.id == ticket.queue_id).first()

        return self._to_ticket(ticket, student, queue)

    def mark_no_show(self, ticket_id: int) -> Optional[Ticket]:
```

Then change `get_queue_display`, from:

```python
    def get_queue_display(self, queue_id: int) -> List[TicketPublic]:
        """Get tickets for public display (limited info)"""
        tickets = self.db.query(TicketDB).filter(
            TicketDB.queue_id == queue_id,
            TicketDB.status.in_([TicketDBStatus.WAITING, TicketDBStatus.SERVING])
        ).order_by(TicketDB.position).all()

        queue = self.db.query(QueueDB).filter(QueueDB.id == queue_id).first()

        result = []
        for ticket in tickets:
            # For display, show only ticket number, not student info
            result.append(TicketPublic(
                ticket_number=ticket.ticket_number,
                queue_name=queue.name if queue else "Unknown",
                position=ticket.position,
                status=TicketStatus(ticket.status.value),
                estimated_wait_time_minutes=ticket.estimated_wait_time_minutes,
                created_at=ticket.created_at,
            ))
        return result
```

to:

```python
    def get_queue_display(self, queue_id: int) -> List[TicketPublic]:
        """Get tickets for public display (limited info)"""
        tickets = self.db.query(TicketDB).filter(
            TicketDB.queue_id == queue_id,
            TicketDB.status.in_([TicketDBStatus.WAITING, TicketDBStatus.SERVING])
        ).order_by(TicketDB.position).all()

        queue = self.db.query(QueueDB).filter(QueueDB.id == queue_id).first()

        result = []
        for ticket in tickets:
            # For display, show only ticket number, not student info
            result.append(TicketPublic(
                ticket_number=ticket.ticket_number,
                queue_name=queue.name if queue else "Unknown",
                position=ticket.position,
                status=TicketStatus(ticket.status.value),
                priority=PydanticPriorityLevel(ticket.priority.value),
                estimated_wait_time_minutes=ticket.estimated_wait_time_minutes,
                called_at=ticket.called_at,
                created_at=ticket.created_at,
            ))
        return result
```

Then change `_to_ticket`, from:

```python
    def _to_ticket(self, db_ticket: TicketDB, student: StudentDB = None, queue: QueueDB = None) -> Ticket:
        """Convert DB model to Pydantic model"""
        return Ticket(
            id=db_ticket.id,
            ticket_number=db_ticket.ticket_number,
            student_id=db_ticket.student_id,
            queue_id=db_ticket.queue_id,
            priority=PydanticPriorityLevel(db_ticket.priority.value),
            purpose=db_ticket.purpose,
            status=TicketStatus(db_ticket.status.value),
            position=db_ticket.position,
            estimated_wait_time_minutes=db_ticket.estimated_wait_time_minutes,
            served_at=db_ticket.served_at,
            completed_at=db_ticket.completed_at,
            created_at=db_ticket.created_at,
            updated_at=db_ticket.updated_at,
            queue_name=queue.name if queue else None,
        )
```

to:

```python
    def _to_ticket(self, db_ticket: TicketDB, student: StudentDB = None, queue: QueueDB = None) -> Ticket:
        """Convert DB model to Pydantic model"""
        return Ticket(
            id=db_ticket.id,
            ticket_number=db_ticket.ticket_number,
            student_id=db_ticket.student_id,
            queue_id=db_ticket.queue_id,
            priority=PydanticPriorityLevel(db_ticket.priority.value),
            purpose=db_ticket.purpose,
            status=TicketStatus(db_ticket.status.value),
            position=db_ticket.position,
            estimated_wait_time_minutes=db_ticket.estimated_wait_time_minutes,
            served_at=db_ticket.served_at,
            completed_at=db_ticket.completed_at,
            called_at=db_ticket.called_at,
            created_at=db_ticket.created_at,
            updated_at=db_ticket.updated_at,
            queue_name=queue.name if queue else None,
        )
```

- [ ] **Step 4: Add the `/call` endpoint**

In `bsu-registrar-queue/backend/app/api/tickets.py`, change:

```python
@router.post("/{ticket_id}/no-show", response_model=Ticket)
def mark_no_show(
```

to (inserting the new endpoint immediately before `mark_no_show`):

```python
@router.post("/{ticket_id}/call", response_model=Ticket)
def call_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.REGISTRAR, UserRole.STAFF))
):
    """Record that staff called this ticket again (does not change status)"""
    service = TicketService(db)
    ticket = service.call_ticket(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


@router.post("/{ticket_id}/no-show", response_model=Ticket)
def mark_no_show(
```

- [ ] **Step 5: Re-create tables and start the backend**

From `bsu-registrar-queue/backend`, run `.venv/Scripts/python.exe seed.py` to pick up the new `called_at` column on the existing `tickets` table in the dev DB (same caveat as prior schema-adding features on this project: `Base.metadata.create_all` only creates missing tables, so if `tickets` already exists without this column, recreate the table/DB rather than expecting an automatic migration). Then start the backend: `.venv/Scripts/python.exe -m uvicorn app.main:app --port 8000` (or `.\dev.ps1` from `bsu-registrar-queue/` if the whole stack isn't already running).

- [ ] **Step 6: Verify — Call endpoint works for all three roles, doesn't change status, and shows up in both `Ticket` and `TicketPublic`**

```bash
cd bsu-registrar-queue/backend
.venv/Scripts/python.exe -c "
import httpx

base = 'http://localhost:8000/api'

def login(username, password):
    r = httpx.post(f'{base}/auth/login', data={'username': username, 'password': password})
    return r.json()['access_token']

admin_token = login('admin', 'admin123')
headers = {'Authorization': f'Bearer {admin_token}'}

queue_id = httpx.get(f'{base}/queues/active').json()[0]['id']
student_id = httpx.get(f'{base}/students/search', params={'student_id': '2022000045'}).json()['id']

ticket = httpx.post(f'{base}/tickets', json={'queue_id': queue_id, 'student_id': student_id, 'purpose': 'counter test'}).json()
print('created ticket priority:', ticket['priority'])
ticket_id = ticket['id']

served = httpx.post(f'{base}/tickets/{ticket_id}/serve', headers=headers).json()
print('served status:', served['status'], 'called_at:', served.get('called_at'))

for role_user, role_pass in [('admin', 'admin123'), ('registrar', 'registrar123'), ('staff', 'staff123')]:
    token = login(role_user, role_pass)
    r = httpx.post(f'{base}/tickets/{ticket_id}/call', headers={'Authorization': f'Bearer {token}'})
    print(f'{role_user} call:', r.status_code, r.json().get('called_at'), r.json().get('status'))

display = httpx.get(f'{base}/tickets/queue/{queue_id}/display').json()
mine = [t for t in display if t['ticket_number'] == ticket['ticket_number']][0]
print('display entry:', {'priority': mine['priority'], 'called_at': mine['called_at'], 'status': mine['status']})

httpx.post(f'{base}/tickets/{ticket_id}/complete', headers=headers)
"
```

Expected: `created ticket priority: priority` (2022000045 is a scholar); `served status: serving`; all three role calls return `200` with a fresh `called_at` timestamp each time and `status` still `serving` (unchanged by any of the three calls); the display entry shows `priority: priority`, a non-null `called_at`, `status: serving`.

- [ ] **Step 7: Verify — Skip (no-show) still works exactly as before, using the existing endpoint**

```bash
cd bsu-registrar-queue/backend
.venv/Scripts/python.exe -c "
import httpx

base = 'http://localhost:8000/api'
resp = httpx.post(f'{base}/auth/login', data={'username': 'admin', 'password': 'admin123'})
token = resp.json()['access_token']
headers = {'Authorization': f'Bearer {token}'}

queue_id = httpx.get(f'{base}/queues/active').json()[0]['id']
student_id = httpx.get(f'{base}/students/search', params={'student_id': '2024000567'}).json()['id']

ticket = httpx.post(f'{base}/tickets', json={'queue_id': queue_id, 'student_id': student_id, 'purpose': 'skip test'}).json()
served = httpx.post(f'{base}/tickets/{ticket[\"id\"]}/serve', headers=headers).json()
print('served:', served['status'])

skipped = httpx.post(f'{base}/tickets/{ticket[\"id\"]}/no-show', headers=headers).json()
print('after skip:', skipped['status'])
"
```

Expected: `served: serving`, `after skip: no_show`.

- [ ] **Step 8: Commit**

```bash
git add bsu-registrar-queue/backend/app/db_models.py \
        bsu-registrar-queue/backend/app/models/ticket.py \
        bsu-registrar-queue/backend/app/services/ticket_service.py \
        bsu-registrar-queue/backend/app/api/tickets.py
git commit -m "feat(counter): add called_at tracking, priority on TicketPublic, and the Call endpoint"
```

---

### Task 2: Frontend — Counter screen

**Files:**
- Modify: `bsu-registrar-queue/frontend/src/stores/queue.js`
- Create: `bsu-registrar-queue/frontend/src/views/CounterView.vue`
- Modify: `bsu-registrar-queue/frontend/src/router/index.js`
- Modify: `bsu-registrar-queue/frontend/src/components/AdminLayout.vue`

**Interfaces:**
- Consumes: Task 1's `POST /api/tickets/{id}/call`, the now-`priority`-and-`called_at`-bearing `TicketPublic` shape (via existing `fetchQueueDisplay`), and the existing `fetchActiveQueues`, `serveNextTicket`, `completeTicket`, `markNoShow` store actions.
- Produces: `queueStore.callTicket(ticketId)`; route `/admin/counter` (name `admin-counter`), unrestricted (any authenticated role).

- [ ] **Step 1: Add the `callTicket` store action**

In `bsu-registrar-queue/frontend/src/stores/queue.js`, change:

```js
    async markNoShow(ticketId) {
      this.loading = true
      this.error = null
      try {
        const response = await api.post(`/tickets/${ticketId}/no-show`)
        const idx = this.queueTickets.findIndex(t => t.id === ticketId)
        if (idx !== -1) this.queueTickets[idx] = response.data
        return response.data
      } catch (err) {
        this.error = err.response?.data?.detail || 'Failed to mark no-show'
        throw err
      } finally {
        this.loading = false
      }
    },

    // ============ STUDENT ACTIONS ============
```

to:

```js
    async markNoShow(ticketId) {
      this.loading = true
      this.error = null
      try {
        const response = await api.post(`/tickets/${ticketId}/no-show`)
        const idx = this.queueTickets.findIndex(t => t.id === ticketId)
        if (idx !== -1) this.queueTickets[idx] = response.data
        return response.data
      } catch (err) {
        this.error = err.response?.data?.detail || 'Failed to mark no-show'
        throw err
      } finally {
        this.loading = false
      }
    },

    async callTicket(ticketId) {
      this.loading = true
      this.error = null
      try {
        const response = await api.post(`/tickets/${ticketId}/call`)
        return response.data
      } catch (err) {
        this.error = err.response?.data?.detail || 'Failed to call ticket'
        throw err
      } finally {
        this.loading = false
      }
    },

    // ============ STUDENT ACTIONS ============
```

- [ ] **Step 2: Create `CounterView.vue`**

Create `bsu-registrar-queue/frontend/src/views/CounterView.vue`:

```vue
<template>
  <div>
    <div class="mb-8">
      <h2 class="text-3xl font-bold text-gray-900">Counter</h2>
      <p class="mt-2 text-gray-600">Serve tickets for a queue</p>
    </div>

    <div v-if="counterError" class="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
      <p class="text-sm text-red-700">{{ counterError }}</p>
    </div>

    <div class="bg-white rounded-xl shadow-sm border border-gray-100">
      <div class="bg-bsu-primary/5 border-b border-bsu-primary/10 px-6 py-4 flex items-center justify-between">
        <h3 class="text-xl font-bold text-gray-900">{{ selectedQueue?.name || 'Select a queue' }}</h3>
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

      <div class="p-6">
        <div v-if="selectedQueue" class="space-y-6">
          <!-- Currently Serving -->
          <div class="bg-gray-50 rounded-lg p-8 text-center">
            <h4 class="text-sm text-gray-500 uppercase tracking-wide mb-4">Currently Serving</h4>

            <div v-if="servingTicket">
              <span class="inline-block px-8 py-4 bg-bsu-primary text-white text-5xl font-extrabold rounded-full mb-3">
                {{ servingTicket.ticket_number }}
              </span>
              <div class="mb-6">
                <span
                  v-if="servingTicket.priority && servingTicket.priority !== 'normal'"
                  class="text-xs px-2 py-0.5 rounded-full"
                  :class="servingTicket.priority === 'urgent' ? 'bg-red-100 text-red-800' : 'bg-yellow-100 text-yellow-800'"
                >
                  {{ servingTicket.priority }}
                </span>
              </div>

              <div class="flex justify-center gap-3">
                <button
                  @click="callCurrentTicket"
                  :disabled="loading"
                  class="px-5 py-2.5 text-sm font-medium rounded-md bg-bsu-gold text-gray-900 hover:bg-yellow-500 focus:outline-none focus:ring-2 focus:ring-bsu-gold disabled:opacity-50"
                >
                  {{ justCalled ? 'Called ✓' : 'Call' }}
                </button>
                <button
                  @click="skipCurrentTicket"
                  :disabled="loading"
                  class="px-5 py-2.5 text-sm font-medium rounded-md bg-red-600 text-white hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 disabled:opacity-50"
                >
                  Skip
                </button>
                <button
                  @click="completeCurrentTicket"
                  :disabled="loading"
                  class="px-5 py-2.5 text-sm font-medium rounded-md bg-green-600 text-white hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500 disabled:opacity-50"
                >
                  Complete
                </button>
              </div>
            </div>

            <div v-else>
              <span class="inline-block px-8 py-4 bg-gray-200 text-gray-500 text-5xl font-extrabold rounded-full mb-6">
                --
              </span>
              <div>
                <button
                  @click="serveNext"
                  :disabled="loading || waitingTickets.length === 0"
                  class="px-6 py-3 text-sm font-medium rounded-md text-white bg-bsu-primary hover:bg-pink-800 focus:outline-none focus:ring-2 focus:ring-bsu-primary disabled:opacity-50"
                >
                  <span v-if="!loading">Serve Next Ticket</span>
                  <span v-else>Processing...</span>
                </button>
              </div>
            </div>
          </div>

          <!-- Waiting list -->
          <div>
            <h4 class="text-sm text-gray-500 uppercase tracking-wide mb-3">Waiting ({{ waitingTickets.length }})</h4>
            <div class="space-y-2">
              <div
                v-for="ticket in waitingTickets"
                :key="ticket.ticket_number"
                class="flex items-center justify-between px-3 py-2 rounded-md"
                :class="ticket.priority === 'urgent' ? 'bg-red-50 border-l-4 border-red-400' : ticket.priority === 'priority' ? 'bg-yellow-50 border-l-4 border-yellow-400' : 'bg-white border border-gray-200'"
              >
                <div class="flex items-center space-x-3">
                  <span class="font-medium text-gray-900">#{{ ticket.ticket_number }}</span>
                  <span
                    v-if="ticket.priority !== 'normal'"
                    class="text-xs px-2 py-0.5 rounded-full"
                    :class="ticket.priority === 'urgent' ? 'bg-red-100 text-red-800' : 'bg-yellow-100 text-yellow-800'"
                  >
                    {{ ticket.priority }}
                  </span>
                </div>
                <span class="text-sm text-gray-500">~{{ ticket.estimated_wait_time_minutes ?? 0 }} min</span>
              </div>

              <div v-if="waitingTickets.length === 0" class="text-center py-4 text-gray-500">
                No tickets waiting
              </div>
            </div>
          </div>
        </div>

        <div v-else class="text-center py-12">
          <p class="text-gray-500">Select a queue to start serving tickets</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useQueueStore } from '@/stores/queue'

const queueStore = useQueueStore()

const loading = ref(false)
const counterError = ref('')
const justCalled = ref(false)

const queues = ref([])
const selectedQueueId = ref(null)
const selectedQueue = computed(() => queues.value.find(q => q.id === selectedQueueId.value))

const queueDisplay = ref([])
const servingTicket = ref(null)
const waitingTickets = computed(() =>
  queueDisplay.value.filter(t => t.status === 'waiting').slice().sort((a, b) => a.position - b.position)
)

const loadQueues = async () => {
  counterError.value = ''
  try {
    await queueStore.fetchActiveQueues()
    queues.value = queueStore.activeQueues
  } catch (err) {
    counterError.value = err.response?.data?.detail || 'Failed to load queues'
  }
}

const updateQueueDisplay = async () => {
  if (!selectedQueueId.value) return
  try {
    await queueStore.fetchQueueDisplay(selectedQueueId.value)
    queueDisplay.value = queueStore.queueDisplay
  } catch (err) {
    queueDisplay.value = []
  }
}

const serveNext = async () => {
  if (!selectedQueueId.value) return
  loading.value = true
  counterError.value = ''
  try {
    const result = await queueStore.serveNextTicket(selectedQueueId.value)
    servingTicket.value = result
    await updateQueueDisplay()
  } catch (err) {
    counterError.value = err.response?.data?.detail || 'No waiting tickets'
  } finally {
    loading.value = false
  }
}

const callCurrentTicket = async () => {
  if (!servingTicket.value) return
  loading.value = true
  counterError.value = ''
  try {
    await queueStore.callTicket(servingTicket.value.id)
    justCalled.value = true
    setTimeout(() => { justCalled.value = false }, 2000)
  } catch (err) {
    counterError.value = err.response?.data?.detail || 'Failed to call ticket'
  } finally {
    loading.value = false
  }
}

const skipCurrentTicket = async () => {
  if (!servingTicket.value) return
  loading.value = true
  counterError.value = ''
  try {
    await queueStore.markNoShow(servingTicket.value.id)
    servingTicket.value = null
    await updateQueueDisplay()
  } catch (err) {
    counterError.value = err.response?.data?.detail || 'Failed to skip ticket'
  } finally {
    loading.value = false
  }
}

const completeCurrentTicket = async () => {
  if (!servingTicket.value) return
  loading.value = true
  counterError.value = ''
  try {
    await queueStore.completeTicket(servingTicket.value.id)
    servingTicket.value = null
    await updateQueueDisplay()
  } catch (err) {
    counterError.value = err.response?.data?.detail || 'Failed to complete ticket'
  } finally {
    loading.value = false
  }
}

watch(selectedQueueId, () => {
  servingTicket.value = null
  queueDisplay.value = []
  updateQueueDisplay()
})

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

- [ ] **Step 3: Add the `/admin/counter` route**

In `bsu-registrar-queue/frontend/src/router/index.js`, change:

```js
        {
          path: 'queues',
          name: 'admin-queues',
          component: () => import('../views/QueueManagementView.vue')
        },
        {
          path: 'media',
```

to:

```js
        {
          path: 'queues',
          name: 'admin-queues',
          component: () => import('../views/QueueManagementView.vue')
        },
        {
          path: 'counter',
          name: 'admin-counter',
          component: () => import('../views/CounterView.vue')
        },
        {
          path: 'media',
```

(No `meta` restriction — unrestricted, same access level as Dashboard/Queue Management: any authenticated Admin/Registrar/Staff, inherited from the parent `/admin` route's `requiresAuth`.)

- [ ] **Step 4: Add the sidebar link**

In `bsu-registrar-queue/frontend/src/components/AdminLayout.vue`, change:

```html
          <router-link
            to="/admin/queues"
            class="block px-3 py-2 rounded-md text-sm font-medium"
            :class="route.path === '/admin/queues' ? 'bg-bsu-primary/10 text-bsu-primary' : 'text-gray-700 hover:bg-gray-100'"
          >
            Queue Management
          </router-link>
          <router-link
            v-if="['admin', 'registrar'].includes(queueStore.currentUser?.role)"
            to="/admin/media"
```

to:

```html
          <router-link
            to="/admin/queues"
            class="block px-3 py-2 rounded-md text-sm font-medium"
            :class="route.path === '/admin/queues' ? 'bg-bsu-primary/10 text-bsu-primary' : 'text-gray-700 hover:bg-gray-100'"
          >
            Queue Management
          </router-link>
          <router-link
            to="/admin/counter"
            class="block px-3 py-2 rounded-md text-sm font-medium"
            :class="route.path === '/admin/counter' ? 'bg-bsu-primary/10 text-bsu-primary' : 'text-gray-700 hover:bg-gray-100'"
          >
            Counter
          </router-link>
          <router-link
            v-if="['admin', 'registrar'].includes(queueStore.currentUser?.role)"
            to="/admin/media"
```

- [ ] **Step 5: Start the full dev stack**

From `bsu-registrar-queue/`, run `.\dev.ps1` (or restart the frontend/backend windows if already running).

- [ ] **Step 6: Verify — sidebar link, queue selection, serve/call/skip/complete cycle, priority badges**

Log in as `staff`/`staff123` (portal Counter). Expected: sidebar shows "Counter" (unrestricted, unlike Media/Users). Click it (`/admin/counter`), pick a queue with at least one waiting ticket (use the existing Queue Management page or the student-facing `/queues/:id` flow to create one first if needed, ideally for a scholar/varsity/graduating student so a priority badge is visible). Click "Serve Next Ticket" — confirm the ticket appears in Currently Serving with its priority badge if applicable. Click "Call" — button should briefly read "Called ✓" then revert. Click "Skip" — confirm Currently Serving clears back to `--` and the ticket no longer appears in the waiting list (it's now No-Show, not waiting). Serve another, click "Complete" — confirm the same clear-back-to-`--` behavior.

- [ ] **Step 7: Verify — switching queues refreshes immediately**

With two different active queues each having at least one ticket, switch the queue picker from one to the other. Confirm the Currently Serving card and waiting list update immediately (not after a multi-second delay).

- [ ] **Step 8: Commit**

```bash
git add bsu-registrar-queue/frontend/src/stores/queue.js \
        bsu-registrar-queue/frontend/src/views/CounterView.vue \
        bsu-registrar-queue/frontend/src/router/index.js \
        bsu-registrar-queue/frontend/src/components/AdminLayout.vue
git commit -m "feat(counter): add dedicated Counter screen for serving tickets"
```

---

### Task 3: Frontend — display board Call pulse and chime

**Files:**
- Modify: `bsu-registrar-queue/frontend/src/views/DisplayBoardView.vue`

**Interfaces:**
- Consumes: `called_at` and `priority` now present on every item in `queueStore.queueDisplay` (Task 1 + Task 2). This task doesn't use `priority` (the display board doesn't show priority badges), only `called_at`.

- [ ] **Step 1: Detect `called_at` changes and trigger a pulse + chime**

In `bsu-registrar-queue/frontend/src/views/DisplayBoardView.vue`, change the script imports from:

```js
import { onMounted, onUnmounted, ref, computed } from 'vue'
```

to:

```js
import { onMounted, onUnmounted, ref, computed, watch } from 'vue'
```

Then, immediately after the existing `servingTickets`/`waitingTickets`/`waitingPreview`/`waitingOverflow` computed declarations (i.e. right after the line `const waitingOverflow = computed(() => Math.max(0, waitingTickets.value.length - WAITING_PREVIEW_LIMIT))`), add:

```js
const lastCalledAt = ref({})
const justCalled = ref({})

const playChime = () => {
  try {
    const AudioContextClass = window.AudioContext || window.webkitAudioContext
    const ctx = new AudioContextClass()
    const oscillator = ctx.createOscillator()
    const gain = ctx.createGain()
    oscillator.type = 'sine'
    oscillator.frequency.value = 880
    gain.gain.setValueAtTime(0.3, ctx.currentTime)
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.4)
    oscillator.connect(gain)
    gain.connect(ctx.destination)
    oscillator.start()
    oscillator.stop(ctx.currentTime + 0.4)
  } catch (err) {
    // Audio may be blocked by the browser's autoplay policy - fail silent,
    // the visual pulse below still happens regardless.
  }
}

watch(servingTickets, (tickets) => {
  tickets.forEach((ticket) => {
    if (!ticket.called_at) return
    const previous = lastCalledAt.value[ticket.ticket_number]
    lastCalledAt.value[ticket.ticket_number] = ticket.called_at
    // Only pulse on a genuine change seen after the first time we've observed
    // this ticket - otherwise a display board that loads fresh would
    // immediately pulse for a call that happened before the page even opened.
    if (previous !== undefined && previous !== ticket.called_at) {
      justCalled.value[ticket.ticket_number] = true
      playChime()
      setTimeout(() => {
        justCalled.value[ticket.ticket_number] = false
      }, 2000)
    }
  })
})
```

- [ ] **Step 2: Apply the pulse class conditionally**

In the same file's template, change:

```html
            <div
              v-for="ticket in servingTickets"
              :key="ticket.ticket_number"
              class="bg-bsu-primary rounded-2xl px-16 py-12 shadow-lg shadow-pink-900/40 animate-pulse-slow"
            >
```

to:

```html
            <div
              v-for="ticket in servingTickets"
              :key="ticket.ticket_number"
              class="bg-bsu-primary rounded-2xl px-16 py-12 shadow-lg shadow-pink-900/40"
              :class="justCalled[ticket.ticket_number] ? 'animate-called-pulse' : 'animate-pulse-slow'"
            >
```

- [ ] **Step 3: Add the pulse animation**

In the same file's `<style scoped>` block, change:

```css
<style scoped>
@keyframes pulse-slow {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.85; }
}
.animate-pulse-slow {
  animation: pulse-slow 2.5s ease-in-out infinite;
}
</style>
```

to:

```css
<style scoped>
@keyframes pulse-slow {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.85; }
}
.animate-pulse-slow {
  animation: pulse-slow 2.5s ease-in-out infinite;
}

@keyframes called-pulse {
  0%, 100% { transform: scale(1); box-shadow: 0 0 0 0 rgba(190, 24, 93, 0.7); }
  50% { transform: scale(1.05); box-shadow: 0 0 0 20px rgba(190, 24, 93, 0); }
}
.animate-called-pulse {
  animation: called-pulse 0.6s ease-in-out 3;
}
</style>
```

- [ ] **Step 4: Start the full dev stack**

From `bsu-registrar-queue/`, run `.\dev.ps1` (or restart the frontend if already running).

- [ ] **Step 5: Verify — Call triggers a pulse and chime within one poll cycle, and doesn't fire on initial page load**

Open the single-queue display board (`/display/:id`) for a queue that already has a ticket in "serving" status (from before the page loads). Confirm it does NOT pulse/chime immediately on load (only the existing steady `animate-pulse-slow` should be visible). Then, from the Counter screen (Task 2) for that same queue, click "Call". Within about 4 seconds (the display board's poll interval), confirm the serving number visibly pulses/glows and a short chime plays. Confirm the all-queues overview page (`/display/overview`) shows no such effect for the same event (it doesn't consume `called_at` at all).

- [ ] **Step 6: Commit**

```bash
git add bsu-registrar-queue/frontend/src/views/DisplayBoardView.vue
git commit -m "feat(counter): pulse and chime the display board when a ticket is called"
```
