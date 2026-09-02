# Transaction History & Peak-Transactions Audit Calendar — Design

**Date:** 2026-09-03
**Status:** Approved for planning
**Path type:** Architectural (new read-only reporting subsystem)

## Problem

Admins have no way to review past registrar activity. The dashboard
(`GET /api/queues/dashboard-summary`) is a *today-only* snapshot, and the
security audit log (`app/core/audit.py`) writes JSON lines to stdout only —
nothing queryable. There is no view of historical tickets/appointments and no
way to see which days or hours are busiest for audit and staffing review.

## Goals

1. **Transaction history** — an admin-only view listing past *transactions*
   (tickets **and** appointments) merged into one filterable, paginated
   timeline.
2. **Peak-transactions calendar** — a monthly heatmap grid showing transaction
   volume per day, with a busiest-hours breakdown, so peak periods are visible
   at a glance. Clicking a day filters the history list to that day.
3. **Audit export** — a CSV download of all rows matching the current filters.

## Non-goals / YAGNI

- **No schema change.** "Existing data only" — we do not add staff-actor
  columns (`served_by` etc.). The trail is timestamps + status, not "who".
- No persistence of the stdout security audit log into a DB table.
- No editing, no soft-delete, no annotations on historical rows — read-only.
- No cross-month range on the calendar (one calendar month at a time); the
  *table* supports arbitrary date ranges.
- No new frontend charting/calendar dependency — `date-fns` and
  `vue-chartjs`/`chart.js` are already in the bundle.

## Decisions (confirmed with user)

| Question | Decision |
|---|---|
| Data scope | Tickets **and** appointments, merged. Default view shows the *attended* set (`completed`, `serving`, `checked_in`); a status filter surfaces the rest (`waiting`, `cancelled`, `no_show`, `booked`, `expired`) for audit. |
| Audit depth | Existing data only — no schema change, no prod migration. |
| Calendar | Monthly heatmap grid; click a day → filter table. Plus busiest-hours bar chart. |
| Access | **Admin only** (`require_role(UserRole.ADMIN)` + route `meta.requiresAdmin`). |
| CSV export | Yes — server-side endpoint, logged as a security event. |
| Timezone | Day/hour bucketing in **campus local time** (`Asia/Manila`), new `CAMPUS_TIMEZONE` setting. |

## Architecture

```
Frontend                        Backend
--------                        -------
TransactionHistoryView.vue  ──► GET /api/reports/transactions      ──► ReportService.get_transactions()
  ├─ month heatmap (date-fns)   GET /api/reports/calendar               ReportService.get_calendar()
  ├─ busiest-hours Bar chart    GET /api/reports/transactions.csv       ReportService.get_transactions() + audit log
  ├─ filter row
  └─ paginated table
stores/queue.js
  ├─ fetchTransactionHistory()
  └─ fetchTransactionCalendar()
```

New backend units, each with one purpose:

- `app/models/report.py` — Pydantic response schemas only (no request bodies,
  so no `extra="forbid"` needed).
- `app/services/report_service.py` — `ReportService(db)`, all query/aggregation
  logic. Depends on: `TicketDB`, `AppointmentDB`, `StudentDB`, `QueueDB`,
  `settings.CAMPUS_TIMEZONE`.
- `app/api/reports.py` — thin router, admin-gated, param validation only.
- `frontend/src/views/TransactionHistoryView.vue` — the view.
- Store actions + sidebar link + route are edits to existing files.

## Data model — the normalized transaction

No DB change. A transaction is one `TicketDB` row **or** one `AppointmentDB`
row, projected into `TransactionRow`:

| field | type | ticket source | appointment source |
|---|---|---|---|
| `kind` | `"ticket"` \| `"appointment"` | literal | literal |
| `id` | int | `tickets.id` | `appointments.id` |
| `reference` | str | ticket code = `queue.ticket_letter` + `ticket_number` | `appointments.reference_code` |
| `student_number` | str | `students.student_id` | `students.student_id` |
| `student_name` | str | `first_name + " " + last_name` | same |
| `service` | str | `tickets.purpose` or `queues.name` | `appointments.purpose` or `queues.name` |
| `queue_name` | str | `queues.name` | `queues.name` |
| `status` | str | `tickets.status` value | `appointments.status` value |
| `priority` | str \| null | `tickets.priority` value | `null` |
| `created_at` | datetime | `tickets.created_at` | `appointments.created_at` |
| `occurred_at` | datetime \| null | `completed_at` ?? `served_at` | `checked_in_at` |
| `appointment_date` | date \| null | `null` | `appointments.appointment_date` |

`occurred_at` is the "when the transaction actually happened" column; for
still-open rows it is `null`.

## Backend — `ReportService`

### `get_transactions(*, date_from, date_to, kinds, statuses, queue_id, student_number, priority, skip, limit) -> TransactionHistoryPage`

- Build a SQLAlchemy Core `select()` per kind with **identical labeled
  columns** (the `TransactionRow` shape), each joined to `students` and
  `queues`.
- Filters applied to each select:
  - `created_at >= date_from` (start of day, campus tz → UTC) and
    `created_at < date_to + 1 day`.
  - `status in statuses` when provided; otherwise the default attended set
    per kind (`ticket`: `completed, serving`; `appointment`: `checked_in`).
  - `queue_id == queue_id` when provided.
  - `students.student_id == student_number` when provided.
  - `priority` — tickets select only; the appointments select is dropped
    entirely when `priority` is set (appointments have no priority).
  - `kind` not in `kinds` → that select is omitted.
- `union_all()` the selects, order by `created_at DESC, kind, id DESC`,
  then `.limit(limit).offset(skip)` — pagination happens in Postgres.
- `total` via `select(func.count()).select_from(union_subquery)`.
- **SQL safety:** all values are bound params via Core constructs; no
  `text()`, no f-strings. Satisfies the "ORM only" rule (Core `select` with
  bound params is equivalent to the ORM query builder for this purpose).
- Returns `TransactionHistoryPage(items=[TransactionRow...], total, skip, limit)`.

### `get_calendar(*, year, month) -> CalendarSummary`

- Compute the month's `[first, last]` in campus tz, convert bounds to UTC.
- One lightweight query per kind: `created_at`, `status` for rows in the
  window (no joins needed).
- In Python, convert each `created_at` to `Asia/Manila`, bucket by
  `date()` and by `hour`.
- Produce:
  - `days: [CalendarDay{ date, total, tickets, appointments, by_status }]`
    — one entry per calendar day of the month (zero-filled).
  - `peak_day: date | null`, `peak_count: int`.
  - `busiest_hours: [int; 24]` — total transactions per hour-of-day.
  - `month_total: int`.
- Invalid `year`/`month` combos are prevented by `Query` bounds; a
  defensive `ValueError` in the service is converted to 400.

## Backend — API (`app/api/reports.py`)

Registered in `app/api/router.py`:
`router.include_router(reports_router, prefix="/reports", tags=["reports"])`.

Every route: `current_user: User = Depends(require_role(UserRole.ADMIN))`.

### `GET /api/reports/transactions`

| Param | Type / constraint | Default |
|---|---|---|
| `date_from` | `date` | today − 30 days |
| `date_to` | `date` | today |
| `kind` | repeated / csv, values `ticket`,`appointment` | both |
| `status` | repeated / csv, values from ticket+appointment status enums | attended set |
| `queue_id` | `int > 0` | — |
| `student_number` | `str`, `^\d{10}$` | — |
| `priority` | `normal`\|`priority`\|`urgent` | — |
| `skip` | `int >= 0` | 0 |
| `limit` | `int`, `1..200` | 50 |

`date_from > date_to` → 400. Response: `TransactionHistoryPage`.

### `GET /api/reports/calendar`

| Param | Type / constraint | Default |
|---|---|---|
| `year` | `int`, `2020..2100` | current year (campus tz) |
| `month` | `int`, `1..12` | current month (campus tz) |

Response: `CalendarSummary`.

### `GET /api/reports/transactions.csv`

Same query params as `/transactions` minus `skip`/`limit` (exports **all**
matches, capped defensively at 10 000 rows → 400 with "narrow your filters"
if exceeded). `Content-Type: text/csv`, `Content-Disposition: attachment;
filename="transactions_<from>_<to>.csv"`. Columns = `TransactionRow` fields.

On success emits:
`log_security_event("report.exported", outcome="success", request=request,
actor=current_user.username, detail=f"{row_count} rows, {date_from}..{date_to}")`.
Add `report.exported` to the CLAUDE.md audit-events list.

## Backend — config

`app/core/config.py`: add `CAMPUS_TIMEZONE: str = "Asia/Manila"` to `Settings`.
Used only for bucketing; parsed with `zoneinfo.ZoneInfo` (stdlib). Add to
`backend/.env.example` with a comment.

## Frontend

### Routing & nav

- `frontend/src/router/index.js`: add child route under `/admin`:
  `{ path: 'reports', name: 'admin-reports', component: () => import('../views/TransactionHistoryView.vue'), meta: { requiresAdmin: true } }`.
  The existing `requiresAdmin` guard already redirects non-admins to
  `admin-dashboard`.
- `frontend/src/components/AdminLayout.vue`: add a sidebar `router-link` to
  `/admin/reports`, label **"History & Audit"**, `v-if="queueStore.currentUser?.role === 'admin'"`, matching the existing active-state class pattern.

### Store (`frontend/src/stores/queue.js`)

- State: `transactionHistory: { items: [], total: 0, skip: 0, limit: 50 }`,
  `transactionCalendar: null`.
- `fetchTransactionHistory(params)` → `GET /reports/transactions`, stores result.
- `fetchTransactionCalendar(year, month)` → `GET /reports/calendar`, stores result.
- Error handling: same pattern as existing actions — throw, let the view read
  `err.response?.data?.detail` with a hardcoded fallback string.

### `TransactionHistoryView.vue`

Layout top → bottom:

1. **Header** — "Transaction History & Audit", short description.
2. **Calendar panel**
   - Month label + prev/next buttons (`date-fns` `addMonths`/`subMonths`).
   - 7-column grid: weekday headings, leading blanks via `getDay(startOfMonth)`,
     one cell per day from `eachDayOfInterval`.
   - Cell shade: helper `intensityClass(count, max)` → one of 5 Tailwind
     classes (`bg-bsu-primary/10`, `/25`, `/45`, `/70`, `/100`); `0` → plain
     border only. Cell shows day number + count.
   - Peak day gets a ring/badge.
   - Click a day → `filters.date_from = filters.date_to = isoDate(day)` then
     `reload()`.
3. **Busiest-hours panel** — `vue-chartjs` `Bar`, 24 labels (`0`–`23` or
   `12am`…`11pm`), data = `busiest_hours`. Reuses the dashboard's bar styling.
4. **Filters row** — `<input type="date">` ×2, kind checkboxes (Tickets /
   Appointments), status multi-select (checkbox list), queue `<select>`
   (from `queueStore.queues` — fetch if empty), student-number `<input>`
   (`maxlength=10`, numeric), "Apply" + "Reset".
5. **Table** — columns: Reference · Kind (badge) · Student (name + number) ·
   Service · Queue · Status (`StatusBadge` where the status maps; plain text
   for appointment-only statuses) · Priority · Created · Occurred. Empty state
   when `items` is empty.
6. **Footer** — "Showing `skip+1`–`skip+items.length` of `total`" · Prev/Next
   (step `limit`) · **Download CSV** button (builds the query string from the
   current filters, opens `/api/reports/transactions.csv?…`; cookie auth is
   sent automatically).

State: `filters` reactive object, `page` derived from `skip`/`limit`,
`calendarMonth` ref. `onMounted` → fetch calendar (current month) + first
page of history. Watch `calendarMonth` → refetch calendar.

## Error handling

- Service raises `ValueError` for logically-bad input (`date_from > date_to`,
  export too large); API layer converts to `HTTPException(400, str(e))` —
  identical to the existing `queues`/`tickets` pattern, and safe because every
  message is hand-written and non-sensitive.
- `Query`/`Path` constraints reject malformed params with 422.
- Admin gate → 403 (wrong role) / 401 (no cookie), via `require_role`.
- Unexpected exceptions → existing catch-all handler in `app/main.py`.
- Frontend reads `err.response?.data?.detail` with per-action fallback strings.

## Testing

### `backend/tests/test_report_service.py`

Fixtures: `make_queue`, `make_student`, `make_user`, plus tickets/appointments
created directly through the services with controlled `created_at` /
`completed_at` (set on the ORM row and committed).

- `get_transactions` default window + default status set returns only attended
  rows, newest first.
- Explicit `statuses=["cancelled"]` returns cancelled tickets and nothing else.
- `kinds=["appointment"]` excludes tickets and vice-versa.
- `queue_id` filter scopes correctly.
- `student_number` filter scopes correctly.
- Pagination: `total` is the full count; `limit`/`skip` slice; page 2 has no
  overlap with page 1.
- `get_calendar`: per-day totals zero-filled for the whole month; `peak_day`
  is the highest-count day; `busiest_hours` sums to `month_total`.
- **Timezone edge case:** a ticket created at `2026-06-01T16:30:00Z`
  (= `2026-06-02 00:30` Manila) is bucketed into **June 2** and hour **0**,
  not June 1 / hour 16.

### `backend/tests/test_reports_api.py`

- Admin (cookie) → 200 on all three routes.
- Registrar → 403; Staff → 403; no cookie → 401.
- `.csv` route: `text/csv` content type, header row + N data rows, and a
  `report.exported` line on the `bsu.security` logger (reuse the caplog
  pattern from `test_audit_logging.py`).
- Param validation: `limit=0` → 422; `student_number=abc` → 422;
  `date_from` after `date_to` → 400.

### Frontend

`vitest` is configured (`frontend/src/stores/__tests__/queue.spec.js` exists).

- Add store tests for `fetchTransactionHistory` / `fetchTransactionCalendar`
  (mocked axios) mirroring the existing spec style.
- Unit-test the `intensityClass(count, max)` helper (pure function, extracted
  to a module or tested via component).
- Full view behaviour verified manually with the `run-bsu-registrar-queue`
  skill (screenshots of the calendar + table).

## Files touched

**New**
- `backend/app/models/report.py`
- `backend/app/services/report_service.py`
- `backend/app/api/reports.py`
- `backend/tests/test_report_service.py`
- `backend/tests/test_reports_api.py`
- `frontend/src/views/TransactionHistoryView.vue`

**Edited**
- `backend/app/api/router.py` — include reports router
- `backend/app/services/__init__.py` — export `ReportService`
- `backend/app/core/config.py` — `CAMPUS_TIMEZONE`
- `backend/.env.example` — document `CAMPUS_TIMEZONE`
- `frontend/src/router/index.js` — `/admin/reports` route
- `frontend/src/components/AdminLayout.vue` — sidebar link
- `frontend/src/stores/queue.js` — two actions + state
- `frontend/src/stores/__tests__/queue.spec.js` — action tests
- `CLAUDE.md` — add `report.exported` to the audit-events list; note the new
  reports module under API endpoints

## Rollout

- No migration. Deploys as ordinary code.
- Feature branch `feat/transaction-history-audit` off `master`; PR with the
  full test suite green (`cd backend && python -m pytest`, `cd frontend &&
  npm run test`).
- `CAMPUS_TIMEZONE` is optional (defaults to `Asia/Manila`); no env change
  required on Render for correct behaviour.
