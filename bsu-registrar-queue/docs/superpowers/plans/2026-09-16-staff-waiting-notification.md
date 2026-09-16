# Staff Waiting-Ticket Notification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give staff a live, always-visible count of tickets currently
waiting across all queues (with a per-queue breakdown), visible from every
page in the staff/admin panel, so they no longer have to be looking at
Counter to notice a waiting student.

**Architecture:** Pure frontend change. `AdminLayout.vue` (already wraps
every staff/admin route) starts a 10-second poll of the existing public
`GET /api/tickets/now-serving-overview` endpoint via the store action that
already wraps it (`queueStore.fetchNowServingOverview()`), and renders a new
`WaitingNotificationBell.vue` component in the shared header. The component
derives its total/per-queue numbers from a new pure helper function so that
logic can be unit-tested with Vitest (this codebase has no Vue
component-testing harness, only Vitest for plain `.js`/Pinia-store logic).

**Tech Stack:** Vue 3 `<script setup>`, Pinia, Vitest (jsdom environment,
already configured in `frontend/vite.config.js`), Tailwind utility classes.

**Spec:** `docs/superpowers/specs/2026-09-16-staff-waiting-notification-design.md`

## Global Constraints

- No backend changes, no new API endpoint, no DB migration — reuse
  `GET /api/tickets/now-serving-overview` (already public) and
  `queueStore.fetchNowServingOverview()` / `queueStore.nowServingOverview`
  (already exist, already used by `DisplayOverviewView.vue`).
- No toast, no sound — a live badge count only, hidden entirely when the
  total is 0.
- Poll interval: 10 seconds.
- Visible to all staff roles (Staff/Registrar/Admin) — no role gating.
- Badge/dropdown lives in `AppHeader`'s `#actions` slot (rendered via
  `AdminLayout.vue`), not the sidebar — the sidebar is `hidden sm:block` and
  invisible on mobile.
- No new frontend dependency — click-outside-to-close is hand-rolled (no
  existing precedent or library for it in this codebase; don't add one for
  a single dropdown).
- Poll failures are caught and silently ignored (keep last-known value) —
  matches `CounterView.vue`'s existing poll resilience. No new error UI.

---

### Task 1: Waiting-summary helper (pure logic, TDD)

**Files:**
- Create: `frontend/src/services/waitingSummary.js`
- Test: `frontend/src/services/__tests__/waitingSummary.spec.js`

**Interfaces:**
- Consumes: nothing (pure function, no store/component dependency).
- Produces: `summarizeWaiting(overview)` — `overview` is the array shape
  returned by `GET /api/tickets/now-serving-overview` (and already stored at
  `queueStore.nowServingOverview`), each item shaped
  `{ queue_id: number, queue_name: string, queue_type: string, serving_ticket_codes: string[], next_ticket_code: string|null, waiting_count: number }`.
  Returns `{ total: number, byQueue: Array<{ queue_id: number, queue_name: string, waiting_count: number }> }`
  where `byQueue` only includes entries with `waiting_count > 0`, sorted by
  `waiting_count` descending (busiest queue first). Later tasks (Task 2) call
  this exact function name and rely on this exact return shape.

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/services/__tests__/waitingSummary.spec.js`:

```js
import { describe, expect, it } from 'vitest'
import { summarizeWaiting } from '../waitingSummary.js'

describe('summarizeWaiting', () => {
  it('sums waiting_count across all queues into total', () => {
    const overview = [
      { queue_id: 1, queue_name: 'Clearance', waiting_count: 2 },
      { queue_id: 2, queue_name: 'Enrollment', waiting_count: 3 },
    ]

    const result = summarizeWaiting(overview)

    expect(result.total).toBe(5)
  })

  it('excludes queues with zero waiting_count from byQueue', () => {
    const overview = [
      { queue_id: 1, queue_name: 'Clearance', waiting_count: 0 },
      { queue_id: 2, queue_name: 'Enrollment', waiting_count: 1 },
    ]

    const result = summarizeWaiting(overview)

    expect(result.byQueue).toEqual([
      { queue_id: 2, queue_name: 'Enrollment', waiting_count: 1 },
    ])
  })

  it('sorts byQueue with the busiest queue first', () => {
    const overview = [
      { queue_id: 1, queue_name: 'Clearance', waiting_count: 1 },
      { queue_id: 2, queue_name: 'Enrollment', waiting_count: 4 },
      { queue_id: 3, queue_name: 'Document Request', waiting_count: 2 },
    ]

    const result = summarizeWaiting(overview)

    expect(result.byQueue.map((q) => q.queue_id)).toEqual([2, 3, 1])
  })

  it('returns total 0 and an empty byQueue for an empty overview', () => {
    const result = summarizeWaiting([])

    expect(result).toEqual({ total: 0, byQueue: [] })
  })

  it('ignores extra fields on each overview entry (only picks queue_id/queue_name/waiting_count)', () => {
    const overview = [
      {
        queue_id: 1, queue_name: 'Clearance', queue_type: 'clearance',
        serving_ticket_codes: ['C-001'], next_ticket_code: 'C-002',
        waiting_count: 1,
      },
    ]

    const result = summarizeWaiting(overview)

    expect(result.byQueue).toEqual([
      { queue_id: 1, queue_name: 'Clearance', waiting_count: 1 },
    ])
  })
})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run (from `bsu-registrar-queue/frontend/`): `npm run test -- waitingSummary`
Expected: FAIL — `Cannot find module '../waitingSummary.js'` (or similar
resolution error), since the module doesn't exist yet.

- [ ] **Step 3: Write the minimal implementation**

Create `frontend/src/services/waitingSummary.js`:

```js
// Derives the staff waiting-ticket notification's badge/dropdown data from
// the now-serving-overview response (GET /api/tickets/now-serving-overview,
// already public and already polled elsewhere) - one place that decides
// "how many are waiting, and where" so the component stays pure display.
export function summarizeWaiting(overview) {
  const byQueue = overview
    .filter((q) => q.waiting_count > 0)
    .map((q) => ({
      queue_id: q.queue_id,
      queue_name: q.queue_name,
      waiting_count: q.waiting_count,
    }))
    .sort((a, b) => b.waiting_count - a.waiting_count)

  const total = overview.reduce((sum, q) => sum + (q.waiting_count || 0), 0)

  return { total, byQueue }
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `npm run test -- waitingSummary`
Expected: PASS — all 5 tests green.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/services/waitingSummary.js frontend/src/services/__tests__/waitingSummary.spec.js
git commit -m "feat: add pure waiting-ticket summary helper for staff notification"
```

---

### Task 2: `WaitingNotificationBell.vue` component

**Files:**
- Create: `frontend/src/components/WaitingNotificationBell.vue`

**Interfaces:**
- Consumes: `summarizeWaiting` from `frontend/src/services/waitingSummary.js`
  (Task 1); `useQueueStore()` from `frontend/src/stores/queue.js` (existing,
  unmodified) — specifically `queueStore.nowServingOverview` (existing
  state, already an array of the shape described in Task 1).
- Produces: a renderable component with no props (reads the store directly,
  matching `StatusBadge.vue`'s and other small shared components' pattern in
  this app) and no emits — self-contained. Later tasks (Task 3) import it as
  `import WaitingNotificationBell from '@/components/WaitingNotificationBell.vue'`
  and render it as `<WaitingNotificationBell />` with no props.

No automated test for this task: this codebase has no Vue
component-testing harness (only Vitest against plain `.js`/Pinia-store
logic — see `frontend/src/stores/__tests__/queue.spec.js`), and the spec
(`docs/superpowers/specs/2026-09-16-staff-waiting-notification-design.md`,
Testing section) explicitly defers to live-browser verification, done in
Task 4. This task's own verification is `npm run build` succeeding (Step 2
below) plus the Task 4 end-to-end check.

- [ ] **Step 1: Write the component**

Create `frontend/src/components/WaitingNotificationBell.vue`:

```vue
<template>
  <div class="relative" ref="rootEl">
    <button
      type="button"
      class="relative p-2 rounded-xl text-gray-500 hover:bg-bsu-primary/10 hover:text-bsu-primary-dark transition-colors"
      :aria-expanded="open"
      aria-label="Waiting tickets"
      @click="open = !open"
    >
      <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75v-.7V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0" />
      </svg>
      <span
        v-if="summary.total > 0"
        class="absolute -top-0.5 -right-0.5 min-w-[1.1rem] h-[1.1rem] px-1 flex items-center justify-center rounded-full bg-red-500 text-white text-[0.65rem] font-bold leading-none"
      >
        {{ summary.total }}
      </span>
    </button>

    <Transition
      enter-active-class="transition duration-150 ease-out"
      enter-from-class="opacity-0 scale-95"
      enter-to-class="opacity-100 scale-100"
      leave-active-class="transition duration-100 ease-in"
      leave-from-class="opacity-100 scale-100"
      leave-to-class="opacity-0 scale-95"
    >
      <div
        v-if="open"
        class="absolute right-0 mt-2 w-64 bg-white rounded-2xl shadow-soft-lg border border-gray-100 py-2 z-50"
      >
        <p class="px-4 py-1.5 text-xs font-semibold text-gray-400 uppercase tracking-wide">
          Waiting ({{ summary.total }})
        </p>
        <p v-if="summary.byQueue.length === 0" class="px-4 py-2 text-sm text-gray-500">
          Nothing waiting right now.
        </p>
        <router-link
          v-for="q in summary.byQueue"
          :key="q.queue_id"
          to="/admin/counter"
          class="flex items-center justify-between px-4 py-2 text-sm text-gray-700 hover:bg-bsu-primary/10 hover:text-bsu-primary-dark transition-colors"
          @click="open = false"
        >
          <span>{{ q.queue_name }}</span>
          <span class="font-semibold">{{ q.waiting_count }}</span>
        </router-link>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useQueueStore } from '@/stores/queue'
import { summarizeWaiting } from '@/services/waitingSummary'

const queueStore = useQueueStore()
const open = ref(false)
const rootEl = ref(null)

const summary = computed(() => summarizeWaiting(queueStore.nowServingOverview))

// If the count drops to zero while the dropdown is open (e.g. the last
// waiting ticket was served from another tab), close it rather than leave
// an empty dropdown open with a now-hidden bell badge behind it.
watch(() => summary.value.total, (total) => {
  if (total === 0) open.value = false
})

const onDocumentClick = (event) => {
  if (open.value && rootEl.value && !rootEl.value.contains(event.target)) {
    open.value = false
  }
}

onMounted(() => document.addEventListener('click', onDocumentClick))
onUnmounted(() => document.removeEventListener('click', onDocumentClick))
</script>
```

- [ ] **Step 2: Verify the build succeeds**

Run (from `bsu-registrar-queue/frontend/`): `npm run build`
Expected: build succeeds with no errors (this only proves the SFC compiles
and imports resolve correctly — full behavior is verified live in Task 4,
once this component is actually wired up and rendered in Task 3).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/WaitingNotificationBell.vue
git commit -m "feat: add WaitingNotificationBell component"
```

---

### Task 3: Wire polling and render the bell in `AdminLayout.vue`

**Files:**
- Modify: `frontend/src/components/AdminLayout.vue`

**Interfaces:**
- Consumes: `WaitingNotificationBell` (Task 2, no props); `queueStore.fetchNowServingOverview()`
  (existing action in `frontend/src/stores/queue.js`, already used by
  `DisplayOverviewView.vue` — takes no arguments, returns a Promise, throws
  on failure).
- Produces: nothing new consumed by later tasks — this is the final wiring
  task.

- [ ] **Step 1: Add the polling lifecycle to the script**

In `frontend/src/components/AdminLayout.vue`, the `<script setup>` block
currently starts with:

```js
import { onMounted, ref } from 'vue'
```

Change it to also import `onUnmounted` (needed for the polling cleanup
below):

```js
import { onMounted, onUnmounted, ref } from 'vue'
```

A few lines below that, add the new component import right after the
existing `ConfirmDialog` import:

```js
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import WaitingNotificationBell from '@/components/WaitingNotificationBell.vue'
```

The `<script setup>` block currently ends with:

```js
onMounted(async () => {
  try {
    await queueStore.fetchCurrentUser()
  } catch (err) {
    await queueStore.logout()
    router.push('/login')
  }
})
```

Replace that block with (adds the waiting-ticket poll alongside the
existing current-user check, and the matching `onUnmounted` cleanup):

```js
let waitingPollTimer = null

onMounted(async () => {
  try {
    await queueStore.fetchCurrentUser()
  } catch (err) {
    await queueStore.logout()
    router.push('/login')
    return
  }

  // Poll runs on every staff/admin page (not just Counter) so the waiting
  // count is visible everywhere. Failures are silently ignored - the badge
  // just keeps its last-known value and retries on the next tick, same
  // resilience CounterView's own poll already has.
  const pollWaiting = () => queueStore.fetchNowServingOverview().catch(() => {})
  pollWaiting()
  waitingPollTimer = setInterval(pollWaiting, 10000)
})

onUnmounted(() => {
  if (waitingPollTimer) clearInterval(waitingPollTimer)
})
```

- [ ] **Step 2: Render the bell in the header's actions slot**

In the `<template>` block, find the `<AppHeader subtitle="Registrar Staff Dashboard">`
opening and its `<template #actions>` block:

```vue
    <AppHeader subtitle="Registrar Staff Dashboard">
      <template #actions>
        <span class="hidden md:block text-sm text-gray-500">
```

Insert the bell as the first action, before that `<span>`:

```vue
    <AppHeader subtitle="Registrar Staff Dashboard">
      <template #actions>
        <WaitingNotificationBell />
        <span class="hidden md:block text-sm text-gray-500">
```

- [ ] **Step 3: Verify the build succeeds**

Run (from `bsu-registrar-queue/frontend/`): `npm run build`
Expected: build succeeds with no errors.

- [ ] **Step 4: Run the full frontend test suite**

Run: `npm run test`
Expected: all existing tests still pass (this task doesn't touch any tested
logic, but confirms nothing else broke).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/AdminLayout.vue
git commit -m "feat: poll waiting tickets and show the notification bell in the admin layout"
```

---

### Task 4: End-to-end verification (live browser)

**Files:** none (verification only).

**Interfaces:** none — this task drives the app built by Tasks 1-3 through
a real browser against an isolated database, per this repo's
`run-bsu-registrar-queue` skill (`.claude/skills/run-bsu-registrar-queue/`).
`backend/.env`'s `DATABASE_URL` points at a shared Supabase Postgres that
also backs Render production — do this against the disposable
`bsu_queue_test` database, not the default one.

- [ ] **Step 1: Start the backend against the isolated test database**

From `bsu-registrar-queue/backend/`:

```bash
DB=$(PYTHONPATH="$PWD" ./.venv/Scripts/python.exe -c "
from urllib.parse import urlparse, urlunparse
from app.core.config import settings
p=urlparse(settings.DATABASE_URL); print(urlunparse(p._replace(path='/bsu_queue_test')))")
DATABASE_URL="$DB" ./.venv/Scripts/python.exe -m uvicorn app.main:app --port 8000 &
```

Expected: `Uvicorn running on http://127.0.0.1:8000`. If port 8000 is
already listening, that's someone else's dev session — don't start a
second one, target the existing instance instead.

- [ ] **Step 2: Seed the test database and enable one queue for booking (not required, just leaves it consistent for other checks)**

From `bsu-registrar-queue/backend/` (same `DATABASE_URL` override as Step 1):

```bash
DATABASE_URL="$DB" ./.venv/Scripts/python.exe seed.py
```

Expected: `Database tables created successfully` and either `Initial data
seeded successfully` or `Database already seeded, skipping...` (both are
fine — either way the demo accounts `admin`/`admin123`,
`registrar`/`registrar123`, `staff`/`staff123` and the five demo queues now
exist).

- [ ] **Step 3: Start the frontend**

From `bsu-registrar-queue/frontend/`:

```bash
npm run dev -- --port 5173 &
```

Expected: Vite prints `Local: http://localhost:5173/`.

- [ ] **Step 4: Confirm the badge is hidden when nothing is waiting**

Using the `run-bsu-registrar-queue` skill's Playwright driver
(`.claude/skills/run-bsu-registrar-queue/driver.mjs`) or a real browser: log
in at `http://localhost:5173/login` as `admin` / `admin123`, portal
`admin`. Land on `/admin` (Dashboard).

Expected: the bell icon is visible in the header with **no** numeric badge
on it (since the freshly-seeded test DB has no waiting tickets yet).

- [ ] **Step 5: Create a waiting ticket directly in the database**

From `bsu-registrar-queue/backend/` (same `DATABASE_URL` override as Step
1), insert a ticket the same way `tests/conftest.py`'s fixtures do, so this
matches how the rest of the test suite builds ticket rows:

```bash
DATABASE_URL="$DB" ./.venv/Scripts/python.exe -c "
import os
assert 'bsu_queue_test' in os.environ['DATABASE_URL']
from app.core.database import SessionLocal
from app.db_models import TicketDB, TicketDBStatus, QueueDB, StudentDB
db = SessionLocal()
queue = db.query(QueueDB).first()
student = db.query(StudentDB).first()
ticket = TicketDB(
    ticket_number=1, student_id=student.id, queue_id=queue.id,
    status=TicketDBStatus.WAITING, position=0,
)
db.add(ticket)
db.commit()
print('created waiting ticket in queue:', queue.name)
db.close()
"
```

- [ ] **Step 6: Confirm the badge appears within 10 seconds, without a manual page refresh**

Stay on `/admin` (Dashboard) in the same browser session from Step 4 — do
not reload. Wait up to 10 seconds (the poll interval).

Expected: the bell now shows a red badge with `1` on it, with no manual
action taken.

- [ ] **Step 7: Confirm the dropdown shows the right queue and links to Counter**

Click the bell.

Expected: a dropdown opens showing "Waiting (1)" and one row with the
seeded queue's name and count `1`. Click that row.

Expected: navigates to `/admin/counter`, and the dropdown closes.

- [ ] **Step 8: Confirm the badge is visible from a non-Counter, non-Dashboard page too**

Navigate to `/admin/students` (Students, via the sidebar).

Expected: the bell + badge (still showing `1`) are visible here too,
proving the poll isn't scoped to one view.

- [ ] **Step 9: Serve the ticket and confirm the badge disappears**

From `bsu-registrar-queue/backend/` (same `DATABASE_URL` override):

```bash
DATABASE_URL="$DB" ./.venv/Scripts/python.exe -c "
import os
assert 'bsu_queue_test' in os.environ['DATABASE_URL']
from app.core.database import SessionLocal
from app.db_models import TicketDB, TicketDBStatus
db = SessionLocal()
db.query(TicketDB).filter(TicketDB.status == TicketDBStatus.WAITING).update({'status': TicketDBStatus.COMPLETED})
db.commit()
print('marked all waiting tickets completed')
db.close()
"
```

Stay in the same browser session, wait up to 10 seconds.

Expected: the badge disappears entirely (the bell has no numeric overlay).

- [ ] **Step 10: Check for console errors**

Using the driver's `console` command (or the browser DevTools console
directly): confirm no new `pageerror`/`console.error` entries were logged
during Steps 4-9.

Expected: clean console (`[]` from the driver's `console` command).

- [ ] **Step 11: Stop the dev servers**

Only stop the backend/frontend processes started in Steps 1 and 3 of *this*
task — never a pre-existing dev session found already listening.

```bash
# find PIDs
netstat -ano | grep -E ':8000|:5173'
# stop the ones started in Step 1/3 (Windows):
taskkill //PID <backend_pid> //F
taskkill //PID <frontend_pid> //F
```

- [ ] **Step 12: Final commit (only if Steps 4-10 required any fixes)**

If everything passed as-is, there's nothing to commit here — Task 3's
commit already covers the working feature. If any step above required a
code fix, commit it:

```bash
git add -A
git commit -m "fix: address live-verification findings for the waiting-ticket notification"
```
