# One Active Ticket Per Student Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enforce that a student can hold at most one active (WAITING/SERVING) ticket at a time, across all queues — not just per-queue as today — and remove the now-redundant "View All My Tickets" feature.

**Architecture:** `TicketService.create_ticket` currently checks for a duplicate active ticket scoped to `student_id + queue_id`. Broaden that check to `student_id` only (any queue), and raise a `ValueError` with a specific message (naming the conflicting queue and ticket code) instead of returning `None`. The API layer catches `ValueError` and turns it into an HTTP 400, following the existing pattern already used in `queues.py`/`students.py`. On the frontend, the registration wizard's pre-check (`checkExistingTicketForSelectedService`) is broadened the same way, so a student with an active ticket in *any* queue is routed to "My Queue Status" before reaching the confirm step. Finally, the "View All My Tickets" feature (frontend button/modal, store state/action, backend endpoint/service method) is deleted — it's fully redundant once only one active ticket can ever exist.

**Tech Stack:** Python FastAPI + SQLAlchemy (backend), Vue 3 + Pinia (frontend). No test framework is configured in this repo (per `CLAUDE.md`), so verification is manual against the real running stack (per project convention — see `feedback_verify_with_real_stack` memory), not mocked.

## Global Constraints

- No time-based cooldown — this is a concurrency limit only (one active ticket at a time), not a per-day/session rate limit.
- No DB schema or migration changes — pure query/business-logic change.
- Follow the existing codebase convention: services raise `ValueError` for business-rule violations; API routers catch `ValueError` and re-raise as `HTTPException(400, detail=str(e))` (see `app/api/queues.py:27-30`, `app/api/students.py:28`).
- Don't touch staff-facing serve/complete/cancel/no-show endpoints.
- Delete dead code fully (no unused imports, no orphaned routes/state) — don't leave commented-out remnants.

---

### Task 1: Backend — one active ticket per student, any queue

**Files:**
- Modify: `bsu-registrar-queue/backend/app/services/ticket_service.py:100-107`
- Modify: `bsu-registrar-queue/backend/app/api/tickets.py:21-34`

**Interfaces:**
- Consumes: `_format_ticket_code(letter: str, ticket_number: int) -> str` (already defined at `ticket_service.py:21`, no changes needed). `QueueDB` model (already imported).
- Produces: `TicketService.create_ticket` now raises `ValueError(message: str)` for the duplicate-active-ticket case (in addition to its existing `Optional[Ticket]` return for the other `None` cases). The API endpoint at `POST /api/tickets` now returns HTTP 400 with that message as `detail` for this case, and keeps the existing generic 400 for the other cases.

- [ ] **Step 1: Replace the same-queue duplicate check with a global one that raises `ValueError`**

In `bsu-registrar-queue/backend/app/services/ticket_service.py`, replace lines 100-107:

```python
        # Check if student already has an active ticket in this queue
        existing = self.db.query(TicketDB).filter(
            TicketDB.student_id == ticket_data.student_id,
            TicketDB.queue_id == ticket_data.queue_id,
            TicketDB.status.in_([TicketDBStatus.WAITING, TicketDBStatus.SERVING])
        ).first()
        if existing:
            return None  # Student already has active ticket
```

with:

```python
        # Check if student already has an active ticket in ANY queue - only
        # one transaction in flight per student is allowed, across all queues.
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

- [ ] **Step 2: Catch the `ValueError` in the API layer**

In `bsu-registrar-queue/backend/app/api/tickets.py`, replace lines 21-34:

```python
@router.post("", response_model=Ticket)
def create_ticket(
    ticket: TicketCreate,
    db: Session = Depends(get_db)
):
    """Student takes a queue ticket (public endpoint)"""
    service = TicketService(db)
    result = service.create_ticket(ticket)
    if not result:
        raise HTTPException(
            status_code=400,
            detail="Could not create ticket. Queue may be full, inactive, or student already has an active ticket."
        )
    return result
```

with:

```python
@router.post("", response_model=Ticket)
def create_ticket(
    ticket: TicketCreate,
    db: Session = Depends(get_db)
):
    """Student takes a queue ticket (public endpoint)"""
    service = TicketService(db)
    try:
        result = service.create_ticket(ticket)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not result:
        raise HTTPException(
            status_code=400,
            detail="Could not create ticket. Queue may be full, inactive, or student not found."
        )
    return result
```

Note the generic message drops "student already has an active ticket" since that case now raises `ValueError` with a specific message instead of falling through to `not result`.

- [ ] **Step 3: Start the real backend stack and verify manually**

Per project convention, verify against the real running stack, not mocks.

```bash
cd bsu-registrar-queue/backend
uvicorn app.main:app --reload
```

In a second terminal, find two active queue IDs (create two via the admin API/UI first if fewer than two exist):

```bash
curl -s http://localhost:8000/api/queues/active | python -m json.tool
```

Pick two queue IDs from the output (call them `<QUEUE_A>` and `<QUEUE_B>`), and use any existing student ID (call it `<STUDENT_ID>` — look one up via the student search endpoint or the frontend if needed).

Take a ticket in queue A:

```bash
curl -s -X POST http://localhost:8000/api/tickets \
  -H "Content-Type: application/json" \
  -d '{"student_id": <STUDENT_ID>, "queue_id": <QUEUE_A>, "purpose": "test"}'
```

Expected: 200, a `Ticket` JSON body with `"queue_id": <QUEUE_A>`.

Attempt to take a second ticket in queue B for the same student:

```bash
curl -s -X POST http://localhost:8000/api/tickets \
  -H "Content-Type: application/json" \
  -d '{"student_id": <STUDENT_ID>, "queue_id": <QUEUE_B>, "purpose": "test"}'
```

Expected: HTTP 400, JSON body like:
```json
{"detail": "You already have an active ticket in <Queue A name> (<ticket code>). Complete or cancel it before taking a new one."}
```

Then cancel the first ticket (use its `id` from the first response):

```bash
curl -s -X POST http://localhost:8000/api/tickets/<TICKET_A_ID>/cancel
```

Retry taking a ticket in queue B — expected: 200, success this time.

- [ ] **Step 4: Commit**

```bash
git add bsu-registrar-queue/backend/app/services/ticket_service.py bsu-registrar-queue/backend/app/api/tickets.py
git commit -m "fix(registration): allow only one active ticket per student across all queues"
```

---

### Task 2: Frontend — broaden the wizard's active-ticket pre-check to any queue

**Files:**
- Modify: `bsu-registrar-queue/frontend/src/views/QueuesView.vue:582-596`

**Interfaces:**
- Consumes: `queueStore.fetchMyTicket(studentId, queueId = null)` and `queueStore.startPollingMyTicket(studentId, queueId = null, interval = 10000)` — both already support omitting `queueId` (defined in `stores/queue.js`, unchanged by this task).
- Produces: no new interfaces; behavior of `checkExistingTicketForSelectedService` changes from "check this one queue" to "check any queue."

- [ ] **Step 1: Drop the `queueId` argument from the pre-check**

In `bsu-registrar-queue/frontend/src/views/QueuesView.vue`, replace lines 582-596:

```javascript
const checkExistingTicketForSelectedService = async () => {
  if (!queueStore.currentStudent || !selectedQueueId.value) return
  try {
    await queueStore.fetchMyTicket(queueStore.currentStudent.id, selectedQueueId.value)
    if (queueStore.myTicket && !['completed', 'cancelled', 'no_show'].includes(queueStore.myTicket.status)) {
      queueStore.startPollingMyTicket(queueStore.currentStudent.id, selectedQueueId.value)
      showMyQueueStatus.value = true
    }
  } catch (err) {
    if (err.response?.status !== 404) {
      error.value = err.response?.data?.detail || 'Failed to check for an existing ticket. Please try again.'
    }
    // a 404 here just means no active ticket exists yet - continue with registration
  }
}
```

with:

```javascript
const checkExistingTicketForSelectedService = async () => {
  if (!queueStore.currentStudent || !selectedQueueId.value) return
  try {
    // Unscoped from any single queue - a student can only ever hold one
    // active ticket at a time, in any queue, so check across all of them.
    await queueStore.fetchMyTicket(queueStore.currentStudent.id)
    if (queueStore.myTicket && !['completed', 'cancelled', 'no_show'].includes(queueStore.myTicket.status)) {
      queueStore.startPollingMyTicket(queueStore.currentStudent.id)
      showMyQueueStatus.value = true
    }
  } catch (err) {
    if (err.response?.status !== 404) {
      error.value = err.response?.data?.detail || 'Failed to check for an existing ticket. Please try again.'
    }
    // a 404 here just means no active ticket exists yet - continue with registration
  }
}
```

- [ ] **Step 2: Start the frontend dev server and verify manually in the browser**

```bash
cd bsu-registrar-queue/frontend
npm run dev
```

Make sure the backend from Task 1 is still running (`uvicorn app.main:app --reload` on port 8000).

In the browser (http://localhost:5173):
1. As a student who currently has no active ticket, go through the wizard, select a service in Queue A, look up/register, confirm — reach the "Your Ticket Number" screen for Queue A.
2. Reload the page (or open a new tab) and start the wizard again for the *same* student, this time selecting a service that maps to Queue B.
3. Expected: after looking up the student in step 2, the wizard should immediately show "My Queue Status" for the Queue A ticket (not the Queue B registration form) — because the pre-check is no longer scoped to Queue B only.
4. Cancel the Queue A ticket from that status screen, then retry step 2's flow for Queue B — expected: the registration form now appears normally since there is no more conflicting active ticket.

- [ ] **Step 3: Commit**

```bash
git add bsu-registrar-queue/frontend/src/views/QueuesView.vue
git commit -m "fix(registration): check for an active ticket in any queue before registering"
```

---

### Task 3: Remove the dead "View All My Tickets" feature

**Files:**
- Modify: `bsu-registrar-queue/frontend/src/views/QueuesView.vue:89-95` (button)
- Modify: `bsu-registrar-queue/frontend/src/views/QueuesView.vue:397-428` (modal)
- Modify: `bsu-registrar-queue/frontend/src/views/QueuesView.vue:492` (`showMyTicketsModal` ref)
- Modify: `bsu-registrar-queue/frontend/src/views/QueuesView.vue:728-732` (`viewAllMyTickets` function)
- Modify: `bsu-registrar-queue/frontend/src/stores/queue.js:33` (`myTickets` state)
- Modify: `bsu-registrar-queue/frontend/src/stores/queue.js:538-551` (`fetchMyTickets` action)
- Modify: `bsu-registrar-queue/backend/app/api/tickets.py:51-58` (`GET /my-tickets` endpoint)
- Modify: `bsu-registrar-queue/backend/app/services/ticket_service.py:395-407` (`get_student_tickets` method)

**Interfaces:**
- Consumes: none.
- Produces: none. This task only deletes code; nothing later depends on any of it (confirmed by grep — no other references to `myTickets`, `fetchMyTickets`, `viewAllMyTickets`, `showMyTicketsModal`, `get_student_tickets`, or `/my-tickets` anywhere in the repo).

- [ ] **Step 1: Remove the "View All My Tickets" button**

In `bsu-registrar-queue/frontend/src/views/QueuesView.vue`, delete lines 89-95:

```html
            <button
              @click="viewAllMyTickets"
              :disabled="loading"
              class="flex-1 inline-flex justify-center items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-bsu-primary disabled:opacity-50"
            >
              View All My Tickets
            </button>
```

The remaining button block (lines 81-88, "Take Another Ticket") stays as-is; just close the wrapping `<div>` after it:

```html
          <div class="flex flex-col sm:flex-row gap-3 mt-3">
            <button
              @click="takeAnotherTicket"
              :disabled="loading"
              class="flex-1 inline-flex justify-center items-center px-4 py-2 border border-bsu-primary text-sm font-medium rounded-md text-bsu-primary bg-white hover:bg-bsu-primary/5 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-bsu-primary disabled:opacity-50"
            >
              Take Another Ticket
            </button>
          </div>
```

- [ ] **Step 2: Remove the "My Tickets modal" block**

In the same file, delete lines 397-428 (the entire `<!-- My Tickets modal -->` comment through its closing `</div>`):

```html
    <!-- My Tickets modal -->
    <div v-if="showMyTicketsModal" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 px-4">
      <div class="bg-white rounded-xl shadow-xl max-w-md w-full">
        <div class="px-6 py-4 border-b border-gray-200">
          <h3 class="text-lg font-bold text-gray-900">My Active Tickets</h3>
        </div>
        <div class="px-6 py-4 space-y-3 max-h-96 overflow-y-auto">
          <div v-if="queueStore.myTickets.length === 0" class="text-center text-gray-500 py-4">
            You have no active tickets right now.
          </div>
          <div
            v-for="t in queueStore.myTickets"
            :key="t.id"
            class="flex items-center justify-between px-4 py-3 rounded-lg border border-gray-200 bg-gray-50"
          >
            <div>
              <p class="font-medium text-gray-900">{{ t.queue_name }}</p>
              <p class="text-sm text-gray-500">Ticket {{ t.ticket_code }} &middot; Position {{ t.position }}</p>
            </div>
            <StatusBadge :status="t.status" />
          </div>
        </div>
        <div class="px-6 py-4 border-t border-gray-200 flex justify-end">
          <button
            @click="showMyTicketsModal = false"
            class="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200 focus:outline-none focus:ring-2 focus:ring-bsu-primary"
          >
            Close
          </button>
        </div>
      </div>
    </div>
```

- [ ] **Step 3: Remove the `showMyTicketsModal` ref**

In the same file, delete line 492:

```javascript
const showMyTicketsModal = ref(false)
```

- [ ] **Step 4: Remove the `viewAllMyTickets` function**

In the same file, delete lines 728-732:

```javascript
const viewAllMyTickets = async () => {
  if (!queueStore.currentStudent) return
  await queueStore.fetchMyTickets(queueStore.currentStudent.id)
  showMyTicketsModal.value = true
}
```

- [ ] **Step 5: Remove `myTickets` state and `fetchMyTickets` action from the store**

In `bsu-registrar-queue/frontend/src/stores/queue.js`, delete line 33:

```javascript
    myTickets: [],
```

And delete lines 538-551:

```javascript
    async fetchMyTickets(studentId) {
      this.loading = true
      this.error = null
      try {
        const response = await api.get('/tickets/my-tickets', { params: { student_id: studentId } })
        this.myTickets = response.data
        return response.data
      } catch (err) {
        this.error = err.response?.data?.detail || 'Failed to fetch tickets'
        throw err
      } finally {
        this.loading = false
      }
    },
```

- [ ] **Step 6: Remove the backend `GET /my-tickets` endpoint**

In `bsu-registrar-queue/backend/app/api/tickets.py`, delete lines 51-58:

```python
@router.get("/my-tickets", response_model=List[Ticket])
def get_my_tickets(
    student_id: int,
    db: Session = Depends(get_db)
):
    """Get all of a student's currently active tickets, across every queue (public endpoint)"""
    service = TicketService(db)
    return service.get_student_tickets(student_id)
```

- [ ] **Step 7: Remove the `get_student_tickets` service method**

In `bsu-registrar-queue/backend/app/services/ticket_service.py`, delete lines 395-407:

```python
    def get_student_tickets(self, student_id: int) -> List[Ticket]:
        """Get all of a student's currently active tickets, across every queue"""
        tickets = self.db.query(TicketDB).filter(
            TicketDB.student_id == student_id,
            TicketDB.status.in_([TicketDBStatus.WAITING, TicketDBStatus.SERVING])
        ).all()

        student = self.db.query(StudentDB).filter(StudentDB.id == student_id).first()
        result = []
        for ticket in tickets:
            queue = self.db.query(QueueDB).filter(QueueDB.id == ticket.queue_id).first()
            result.append(self._to_ticket(ticket, student, queue))
        return result
```

- [ ] **Step 8: Verify no dangling references remain**

```bash
cd "bsu-registrar-queue"
grep -rn "myTickets\|fetchMyTickets\|viewAllMyTickets\|showMyTicketsModal\|get_student_tickets\|my-tickets" frontend/src backend/app
```

Expected: no output (empty).

- [ ] **Step 9: Confirm the frontend still builds and the button is gone in the browser**

```bash
cd bsu-registrar-queue/frontend
npm run build
```

Expected: build succeeds with no errors (e.g. no unresolved reference errors).

Then in the browser (dev server from Task 2 still running, or restart it), go through the wizard to the "Your Ticket Number" screen and confirm only the "Take Another Ticket" button remains — no "View All My Tickets" button, and no modal appears anywhere in the flow.

- [ ] **Step 10: Commit**

```bash
git add bsu-registrar-queue/frontend/src/views/QueuesView.vue bsu-registrar-queue/frontend/src/stores/queue.js bsu-registrar-queue/backend/app/api/tickets.py bsu-registrar-queue/backend/app/services/ticket_service.py
git commit -m "refactor(registration): remove dead View All My Tickets feature"
```
