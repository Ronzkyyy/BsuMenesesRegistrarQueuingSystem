# Staff Waiting-Ticket Notification — Design

**Date:** 2026-09-16
**Status:** Approved for planning
**Path type:** Architectural (new cross-page staff UI element + shared polling)

## Problem

Staff have no way to know a student is waiting unless they're actively looking
at the Counter view for that specific queue. `CounterView.vue` already polls
its *currently selected* queue every 5s and silently refreshes the waiting
list, but: (1) nothing calls attention to a new arrival, and (2) staff get no
signal at all for queues they haven't selected, or while on any other admin
page (Dashboard, Queue Management, Students, etc.). There is currently no
staff-facing notification mechanism of any kind in this codebase — the
`notifications.py` Celery module only handles (stubbed) student SMS/email
reminders.

## Goals

1. A live, always-visible indicator of how many tickets are currently waiting
   across all queues, visible from every staff/admin page.
2. A breakdown by queue, so staff know *where* to go without first opening
   Counter or Queue Management to check.
3. Zero disruption when nothing's waiting — no popups, no sound; the
   indicator should be unobtrusive at rest.

## Non-goals / YAGNI

- No toast/popup on new arrivals, no audible alert — confirmed with user: a
  live badge count is enough.
- No new backend endpoint, no schema change. `GET /api/tickets/now-serving-overview`
  already exists (public, used by the display boards) and already returns a
  per-queue `waiting_count`; `stores/queue.js`'s `fetchNowServingOverview()`
  action and `nowServingOverview` state already wrap it.
- No WebSocket/SSE push infrastructure — this codebase has none today, and
  10-second polling of an already-public, already-used-elsewhere endpoint is
  more than adequate at this app's scale (a single registrar office).
- No per-user "mark as seen"/dismiss state, no persistence — the badge always
  reflects live server state.
- No deep-linking from the dropdown into Counter with a queue pre-selected
  (Counter's service-selection logic is untouched) — rows link to `/admin/counter`
  plain; staff select the service themselves, same as today.

## Decisions (confirmed with user)

| Question | Decision |
|---|---|
| Where it appears | Everywhere in the staff/admin panel, not just Counter. |
| Notification style | Live badge count only — no toast, no sound. |
| Detail level | Total count + per-queue dropdown breakdown. |
| Visible to which roles | All staff roles (Staff/Registrar/Admin) — Counter is used by all of them. |
| Data source | Reuse existing public `GET /api/tickets/now-serving-overview` (no new endpoint). |
| Placement | `AppHeader`'s actions slot (via `AdminLayout.vue`), not the sidebar — the sidebar is `hidden sm:block` (invisible on mobile), the header is not. |

## Architecture

```
Frontend                              Backend (unchanged)
--------                              -------
AdminLayout.vue                       GET /api/tickets/now-serving-overview
  ├─ setInterval(10s) on mount   ──►     (already public, already used by
  │    └─ queueStore.fetchNowServingOverview()  DisplayOverviewView.vue)
  ├─ clearInterval on unmount
  └─ <WaitingNotificationBell />  (new small component, in AppHeader's #actions slot)
       ├─ totalWaiting = computed sum of nowServingOverview[].waiting_count
       ├─ waitingByQueue = computed filter (waiting_count > 0)
       └─ dropdown listing waitingByQueue, each row → router-link to /admin/counter
```

No backend changes. The existing `fetchNowServingOverview()` action already
sets `this.error` on failure, but nothing in the frontend currently reads
`queueStore.error` directly in a template (every view uses its own local
error ref) — so a failed background poll degrades silently: the badge just
keeps showing its last-known value until the next successful poll, the same
resilience `CounterView.vue`'s own poll already has.

## Components

**`WaitingNotificationBell.vue`** (new, `frontend/src/components/`)
- Props: none — reads `useQueueStore()` directly, same pattern as other
  small shared components in this app (e.g. `StatusBadge.vue`).
- A bell icon button; a small numeric badge overlays it only when
  `totalWaiting > 0` (hidden entirely at zero, per the "unobtrusive at rest"
  goal).
- Click toggles a dropdown/popover listing each `{queue_name, waiting_count}`
  from `waitingByQueue`, each row a `router-link` to `/admin/counter`. Empty
  state ("Nothing waiting") is unreachable in practice since the bell itself
  is hidden at zero, but the dropdown still needs to close cleanly if the
  count drops to zero while it's open (e.g. staff serves the last ticket from
  another tab) — closes itself via a watcher on `totalWaiting`.
- Closes on outside click / route navigation, matching how the existing
  `ConfirmDialog`/modal patterns in this app already behave for similar
  transient UI.

**`AdminLayout.vue`** (modified)
- Owns the polling lifecycle: `onMounted` starts a 10s `setInterval` calling
  `queueStore.fetchNowServingOverview()` (wrapped in try/catch, discarding
  errors — same resilience approach as `CounterView.vue`'s own poll);
  `onUnmounted` clears it. One poll immediately on mount too, so the badge
  isn't empty for the first 10 seconds.
- Renders `<WaitingNotificationBell />` inside `<AppHeader>`'s `#actions`
  slot, alongside the existing "Logged in as" / "Change Password" / "Logout"
  controls.

**`stores/queue.js`** — no changes. `fetchNowServingOverview()` and
`nowServingOverview` already exist and already do exactly what this feature
needs.

## Error handling

- Poll failures (network blip, brief backend hiccup) are caught and ignored
  in `AdminLayout.vue` — the badge simply keeps its last-known value and
  tries again on the next tick. No error banner, no console noise beyond
  what axios itself logs.
- The endpoint is public and already exercised continuously by any open
  display board, so there's no new failure mode being introduced — this
  feature adds a second, independent caller of an already-proven endpoint.

## Testing

No component-testing infrastructure exists anywhere in this codebase yet —
the only frontend tests are Pinia-store-level (`stores/__tests__/queue.spec.js`).
This feature adds no new store logic (the action/state it depends on already
have implicit coverage via existing usage), so no new automated tests are
planned. Verification is live-browser, same approach used for every other
feature built this session:
1. Seed a waiting ticket for some queue; confirm the badge appears with the
   correct count within ~10s without a manual refresh.
2. Confirm the dropdown lists the right queue name(s) and count(s), and a row
   click navigates to `/admin/counter`.
3. Serve/complete the ticket; confirm the badge count decrements and the
   badge disappears entirely once nothing is waiting anywhere.
4. Confirm the badge is visible and correct from a non-Counter admin page
   (e.g. Dashboard), proving the polling isn't scoped to one view.
5. Confirm no console errors and no regression to existing Counter/Dashboard
   polling.
