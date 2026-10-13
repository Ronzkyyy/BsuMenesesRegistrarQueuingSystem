# Document Request Checklist — Design

**Date:** 2026-10-13
**Status:** Draft — awaiting review
**Origin:** Defense panel revision #1
**Path type:** Architectural (new catalog table, one-to-many documents per
transaction, schema migration on the shared production database)

## Problem

A Document Request ticket or appointment can carry exactly **one** document.
`tickets.document_type` / `appointments.document_type` is a single
`String(30)` validated against the hardcoded `DocumentType` enum
(`app/models/ticket.py`), mirrored by a hardcoded list in
`frontend/src/services/documentTypes.js`. A student who needs a TOR *and* a
Good Moral has to queue twice. The panel asked that one transaction can
request several documents.

The list itself is also hardcoded in two places. Changing it takes a code
change and a deploy, and it can't hold the fees, processing times or
requirements students ask about at the window.

## Goals

1. A student picks **one or more** documents from a checklist in a single
   Document Request transaction, both at the walk-in kiosk (`QueuesView`)
   and in online booking (`AppointmentsView`).
2. The document list becomes an **Admin-managed catalog**. Each document has
   a name, a short code, a requirements note, a processing time, a fee and a
   display order, and can be deactivated.
3. The kiosk and booking form show each document's fee, processing time and
   requirements, plus a **fee total** for the checked documents.
4. The Counter shows every requested document and the fee total for the
   ticket being served.
5. Transaction History and the Excel export show the documents of each
   transaction in one column and can filter by document.

## Non-goals

- **No number of copies.** A document is checked or not. Copies are settled
  at the window.
- **No tracking per document.** Completing the ticket completes the whole
  request. No document is "released later".
- **No payment handling.** Fees are shown for information only. Nothing is
  charged, recorded as paid or receipted.
- **No change to wait times or slot capacity.** One ticket is still one
  queue position and one appointment slot, however many documents it has.
- **No hard delete** of catalog entries. Deactivating is the only way to
  remove one.
- The display board and `TicketPublic` (a student's own ticket lookup) are
  unchanged.

## Decisions (confirmed with user)

| Question | Decision |
|---|---|
| Entry points | Kiosk **and** online booking. A booked appointment brings its documents onto the ticket at check-in. |
| Copies | None. Checkbox only. |
| Catalog | Admin-managed table, replacing the hardcoded enum. |
| Who manages it | **Admin only** (`require_role(UserRole.ADMIN)`). |
| Removal | Deactivate only. History keeps the document. |
| Fields per document | Name, requirements note, processing time, fee, display order (+ short code and active flag). |
| Fees | Fee per document **and** a total on the kiosk, booking summary and Counter. Information only. |
| Counter | Shows the list only, with no per-document status. |
| Reports | One row per transaction with a joined "Documents" column. Filtering by a document matches any transaction that includes it. |
| Limit | At least 1, no upper limit beyond the active catalog. |
| Wait time | Unchanged. |

## Data model

### `documents` — the catalog (new)

| column | type | notes |
|---|---|---|
| `id` | `Integer` PK | |
| `name` | `String(100)`, not null, unique (case-insensitive) | Full label shown to students, e.g. "Certified True Copy - Transcript of Records (TOR)" |
| `short_name` | `String(30)`, not null, unique (case-insensitive) | Compact label for the Counter, reports and Excel, e.g. "TOR" |
| `requirements` | `String(500)`, nullable | e.g. "Bring a valid school ID and your clearance form" |
| `processing_time` | `String(50)`, nullable | Free text, e.g. "3–5 working days" |
| `fee` | `Numeric(10, 2)`, nullable | `NULL` = no fee listed; `0` = free |
| `display_order` | `Integer`, not null | Checklist order, ascending |
| `is_active` | `Boolean`, not null, default `true` | Inactive = hidden from kiosk/booking, kept in history |
| `created_at` / `updated_at` | `DateTime(timezone=True)` | |

Case-insensitive uniqueness is enforced with a unique index on
`lower(name)` / `lower(short_name)`, plus a service-layer check that returns
a readable `400` instead of a raw `IntegrityError`.

### `ticket_documents` / `appointment_documents` — what was requested (new)

Two association tables with the same shape:

| column | type | notes |
|---|---|---|
| `ticket_id` / `appointment_id` | FK, `ON DELETE CASCADE` | |
| `document_id` | FK → `documents.id`, `ON DELETE RESTRICT` | |
| `name` | `String(100)`, not null | **Snapshot** at request time |
| `short_name` | `String(30)`, not null | **Snapshot** |
| `fee` | `Numeric(10, 2)`, nullable | **Snapshot** |
| `position` | `Integer`, not null | Catalog order at request time, for stable display |

Primary key `(ticket_id, document_id)` / `(appointment_id, document_id)`,
which also blocks duplicates. Index on `document_id` for the report filter.

**Why snapshot?** An admin will rename documents and change fees over time.
A ticket served in October must still show what the student asked for and
the fee in force at the time. It must not show today's catalog values. The
`document_id` FK is kept so reports can still group and filter by catalog
entry across renames.

### Existing `document_type` columns

They are **kept but no longer written** in this release. After the
migration, only the association tables are read. The columns are dropped in
a later cleanup migration (see Rollout). The `DocumentType` enum and
`frontend/src/services/documentTypes.js` are deleted.

## Migration (`b9c0d1e2f3a4`, down_revision `a8b9c0d1e2f3`)

The `upgrade()` steps:

1. Create `documents`, `ticket_documents` and `appointment_documents`.
2. Seed the seven current documents in their current order. `name` is the
   current frontend label and `short_name` is the current stored value, so
   existing rows map exactly:

   | order | short_name | name |
   |---|---|---|
   | 1 | TOR | Certified True Copy - Transcript of Records (TOR) |
   | 2 | COR | Certified True Copy - Certificate of Registration (COR) |
   | 3 | COG | Certified True Copy - Certificate of Grades (COG) |
   | 4 | Diploma | Certified True Copy - Diploma |
   | 5 | Good Moral | Certified True Copy - Good Moral Certificate |
   | 6 | Graduation Form | Certified True Copy - Graduation Form |
   | 7 | Form 137 | Certified True Copy - Form 137 |

   `fee`, `processing_time` and `requirements` start `NULL`. The Admin
   fills them in after deploy.
3. **Backfill**: for every ticket and appointment with a non-null
   `document_type`, insert one association row joined on `short_name`, with
   the seeded `name` as the snapshot and `fee = NULL`. This is done in pure
   SQL (`INSERT … SELECT … JOIN documents ON documents.short_name =
   tickets.document_type`) with no Python loop. It follows the
   `sa.text(...)` bound-parameter rule (there are no user values here at
   all).

`downgrade()` copies each transaction's lowest-`position` `short_name` back
into `document_type` (only where it is null), then drops the three tables.
A downgrade loses the extra documents of multi-document requests. That is
acceptable for a rollback, and the migration docstring says so.

## Backend

### Pydantic models — `app/models/document.py` (new)

- `DocumentBase` (`extra="forbid"`, whitespace-stripped):
  `name` 1–100, non-blank; `short_name` 1–30, non-blank; `requirements`
  ≤ 500; `processing_time` ≤ 50; `fee: Optional[Decimal]` with `ge=0`,
  `le=100000`, `max_digits=10`, `decimal_places=2`.
- `DocumentCreate(DocumentBase)`.
- `DocumentUpdate`: all fields optional, plus `is_active: Optional[bool]`,
  `extra="forbid"`.
- `DocumentOrder`: `document_ids: list[int]` (each `> 0`, 1–200 items).
- `Document` (response, `from_attributes`): every column.
- `DocumentPublic` (response for the kiosk): `id`, `name`, `short_name`,
  `requirements`, `processing_time`, `fee`. No timestamps or flags.
- `RequestedDocument` (response): `document_id`, `name`, `short_name`,
  `fee`, from the snapshot row.

Fees travel as `Decimal`. Pydantic v2 serializes them to JSON **strings**
(`"50.00"`), and the frontend formats them with `Number(...)`. That avoids
float rounding in totals.

### Request/response changes

- `TicketBase.document_type` → `document_ids: list[int] = []`, each
  `> 0`, max 50 items (a sanity bound, well above any real catalog size).
  The same change applies to `AppointmentCreate`.
- `Ticket` and `Appointment` responses: `document_type` →
  `documents: list[RequestedDocument]` and
  `documents_fee_total: Optional[Decimal]`. The total is the sum of non-null
  snapshot fees, or `null` when none of the documents has a fee.
- `TransactionRow.document_type` → `documents: Optional[str]`, the
  snapshot `short_name`s joined with `", "` in `position` order.

### Validation — `validate_documents()` (replaces `validate_document_type`)

This is a shared function in `ticket_service.py`, used by both
`TicketService.create_ticket` and `AppointmentService.book`, so the rule
can't drift between them:

- Request Documents queue: `document_ids` must be non-empty
  ("Select at least one document you are requesting.").
- Any other queue: `document_ids` must be empty (same rejection as today).
- Duplicates → `400` ("Each document can only be selected once.").
- Every id must exist **and be active**. Otherwise → `400` ("One or more
  selected documents are no longer available."). The message is the same
  for unknown and inactive ids.
- It returns the catalog rows in `display_order`. The service writes the
  snapshot rows in the same transaction as the ticket or appointment.

### Check-in

`AppointmentService.check_in` must **copy the appointment's snapshot rows**
onto the new ticket. It must not re-validate against the live catalog. If a
document was deactivated or repriced between booking and check-in, the
student still gets what they booked at the price they saw.
`create_ticket` gains an internal keyword argument
(`document_snapshots=...`) for this path. That argument is not reachable
from the API.

### Catalog service and API

`app/services/document_service.py` → `DocumentService(db)`:
`list_active()`, `list_all()`, `create()`, `update()`, `reorder()`.

- `create` appends at the end (`max(display_order) + 1`).
- `update` refuses to deactivate the **last active** document with `400`,
  because the Request Documents service would then be impossible to use.
- `reorder` requires `document_ids` to be exactly the set of all catalog
  ids. Otherwise it returns `400`.

`app/api/documents.py`, included in `app/api/router.py`:

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/api/documents/active` | Public, `@limiter.limit("30/minute")` | Active catalog in display order (`DocumentPublic`) for the kiosk and booking form |
| GET | `/api/documents` | Admin | Full catalog including inactive entries |
| POST | `/api/documents` | Admin | Create a document |
| PATCH | `/api/documents/{id}` | Admin | Edit fields and/or `is_active` (`id` > 0) |
| PUT | `/api/documents/order` | Admin | Save a new display order |

Report filter dropdowns use `GET /api/documents`, which is Admin-only just
like the reports themselves.

**Audit events** (`log_security_event`): `document.created`,
`document.updated` (with `detail` naming the changed fields, e.g. `fee`),
`document.deactivated`, `document.activated`, `document.reordered`. Fee
changes count as sensitive here because students rely on the posted price.

### Reports — `report_service.py`, `reports.py`, `report_export.py`

- New optional query param `document_id: int (gt=0)` on
  `/reports/transactions` and `/reports/transactions.xlsx`. It filters with
  an `EXISTS` subquery on `ticket_documents` / `appointment_documents`, so
  a three-document ticket still counts as **one** transaction.
- Each page's documents are loaded with **one** extra query per source
  (`WHERE ticket_id IN (...)`), not one per row.
- Excel: the "Document Type" column becomes "Documents", widened, with text
  wrapping. It is still written with `write_string`. The filter summary in
  the title block names the selected document.
- The `/reports/calendar` volume counts are unchanged, since they count
  transactions.

## Frontend

### Shared component — `components/DocumentChecklist.vue` (new)

`v-model` is an array of selected ids, and the prop is the active catalog.
Each document is a tappable card with a checkbox, `name`, fee (`₱50.00`,
"Free" for `0`, nothing for `null`) and processing time. Its
`requirements` note expands under the card once it is checked, so the
student sees what to bring for exactly what they chose. A sticky footer
shows "N documents · Total ₱X". When some selected documents have no
listed fee, it reads "Total of listed fees ₱X". The cards are big enough
to tap on the kiosk touch screen and work at phone width for online
booking.

### Kiosk — `QueuesView.vue`

- In step 1, the `<select>` is replaced by `DocumentChecklist`, loaded from
  `/documents/active` when Request Documents is chosen. "Next" is enabled
  once at least one document is checked.
- The step 2 banner and the confirmation/summary panels (currently lines
  ~201, 322 and 376) list the selected documents' short names and the
  total in place of the single "Document Type" line.
- The ticket request sends `document_ids`.

### Online booking — `AppointmentsView.vue`

Uses the same component in place of the `<select>`, with the same summary
changes. The booking request sends `document_ids`.

### Staff screens

- **Counter (`CounterView.vue`)**: the single `document_type` span becomes
  a list of the requested documents (full names, since the staff member
  has to prepare them) with the fee total underneath.
- **Appointment Management**: the Document column shows the joined short
  names.
- **Transaction History**: the column is renamed "Documents", and a
  "Document" filter dropdown (all catalog entries, inactive ones marked)
  is passed through to the list and the Excel download.

### Catalog admin — `views/DocumentCatalogView.vue` (new)

- Route `/admin/documents` (`name: 'admin-documents'`,
  `meta.requiresAdmin`), with a sidebar link in `AdminLayout.vue` next to
  User Management.
- It is a table with name, short name, fee, processing time, status and
  actions. Add/Edit open a modal form with the same limits as the backend.
  Deactivate/Activate use `ConfirmDialog`. Move-up/move-down buttons
  reorder and save through `PUT /documents/order`. Buttons are used rather
  than drag-and-drop because they work on touch screens and with a
  keyboard, with no new dependency.
- Inactive rows are greyed out and sorted after the active ones.

### Store — `stores/queue.js`

New actions: `fetchActiveDocuments`, `fetchAllDocuments`, `createDocument`,
`updateDocument`, `reorderDocuments`. The existing ticket and appointment
actions pass `document_ids` through. Error handling keeps the existing
`err.response?.data?.detail` + fallback pattern.

## Testing

**Backend (pytest)**

- `test_document_service.py`: create/update/reorder, case-insensitive name
  uniqueness, refusing to deactivate the last active document, reorder
  rejecting a partial or foreign id set.
- `test_documents_api.py`: public `/active` hides inactive entries and admin
  fields; Registrar/Staff are `403`'d from every write; `extra="forbid"`
  and the fee bounds return `422`; audit events are emitted.
- `test_ticket_service.py` / `test_appointment_service.py` (updating the
  existing `document_type` tests): several documents are stored with
  snapshots; empty list rejected for Request Documents; non-empty rejected
  for other queues; duplicate, unknown and inactive ids rejected; **check-in
  copies the snapshot even after the document is deactivated and repriced**.
- `test_report_service.py` / `test_reports_api.py`: joined column order;
  `document_id` filter counts a multi-document ticket once; Excel column
  written as text.
- Migration test: upgrade on a database with legacy `document_type` rows
  produces matching association rows, and downgrade restores
  `document_type`.

**Frontend (Vitest)**

- `DocumentChecklist` spec: toggling, the total with and without missing
  fees, the requirements note appearing on check.
- Store spec: the new actions send `document_ids` and read `detail` on
  error.

Both suites are run before pushing, and the kiosk and booking flows are
clicked through on the real stack (backend + test DB).

## Rollout

1. **Do not run `alembic upgrade head` locally against `DATABASE_URL`**. It
   is the shared Supabase database that also backs Render production.
   Develop and test against `bsu_queue_test` only.
2. The migration only **adds** tables and leaves `document_type` alone, so
   it is safe if production briefly runs old code against the migrated
   database. `start.sh` runs the migration on boot of the new image. The
   tickets the old instance creates in that short window still get
   `document_type`. The cleanup migration below backfills them again before
   dropping anything.
3. After deploy, the Admin fills in fees, processing times and requirements
   on `/admin/documents`.
4. **Follow-up PR (later, once this is stable in production):** a cleanup
   migration that re-runs the backfill for any stray `document_type` rows,
   then drops both `document_type` columns.
5. Update `CLAUDE.md`: the new endpoints in the API table, the new models in
   the Input Validation table, the new audit events, and the Admin-only
   catalog.

## Open questions

- **Real fees, processing times and requirements.** The registrar needs to
  supply these. They are data entered after deploy, not code, so they don't
  block the build.
