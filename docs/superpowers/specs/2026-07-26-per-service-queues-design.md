# Per-Service Queues — Design

## Problem

The student registration wizard offers 8 distinct services, but only 5 underlying `QueueDBType` values exist in the backend. Three services (Adding & Dropping, Enrollment, Petition Class) all map to the one `enrollment` queue; two services (General Inquiry, Others) both map to the one `others` queue. This was already surfaced piecemeal on the Counter (via the `purpose` label) and Admin Dashboard (by grouping stats by `purpose` instead of queue), and Queue Management now lists 8 service cards — but 3 of those cards control the exact same underlying queue (shared capacity, ticket numbering, position tracking), which isn't what's wanted going forward.

## Decision

Give each of the 8 services its own independent queue. This requires 3 new queue types — `adding_dropping`, `petition_class`, and `other_concerns` — added to the existing 5.

### The "Others" naming wrinkle

The existing `others`-typed queue is named "General Inquiry" in the seed data (`init_db.py`) — so today, both the "General Inquiry" service and the catch-all "Others" service share that one queue. Splitting them: "General Inquiry" keeps the existing `others` queue (the name already matches it). The catch-all "Others" service gets a genuinely new type, named `other_concerns` to avoid colliding with the existing `others` value.

### Resulting mapping (8 services → 8 queues)

| Service key | Queue type | Queue name | Status |
|---|---|---|---|
| clearance | `clearance` | Clearance | existing, unchanged |
| request_documents | `document_request` | Document Request | existing, unchanged |
| enrollment | `enrollment` | Enrollment | existing, unchanged |
| general_inquiry | `others` | General Inquiry | existing, unchanged |
| scholarship | `scholarship` | Scholarship | existing, unchanged |
| adding_dropping | `adding_dropping` | Adding & Dropping | **new** |
| petition_class | `petition_class` | Petition Class | **new** |
| others | `other_concerns` | Others | **new** |

### New queue defaults

| Queue | Ticket letter | Capacity | Slot duration | Priority |
|---|---|---|---|---|
| Adding & Dropping | A | 50 | 15 min | yes |
| Petition Class | P | 30 | 20 min | yes |
| Others | X | 30 | 15 min | no |

No other queue endpoint exists to edit capacity/slot/letter after creation (only Pause/Resume/Close/Delete) - these defaults are effectively fixed until a future edit-queue feature exists.

### Historical data

Existing tickets keep the `queue_id` they were actually created under (the old shared Enrollment/General-Inquiry-as-others queues). No retroactive reassignment of historical tickets to the new queues - only tickets created after this change land on the correct split queue, based on which service the student picks.

## Changes

### Backend - schema

**`app/db_models.py`** - add 3 members to `QueueDBType`:
```python
class QueueDBType(str, enum.Enum):
    ENROLLMENT = "enrollment"
    DOCUMENT_REQUEST = "document_request"
    CLEARANCE = "clearance"
    SCHOLARSHIP = "scholarship"
    OTHERS = "others"
    ADDING_DROPPING = "adding_dropping"
    PETITION_CLASS = "petition_class"
    OTHER_CONCERNS = "other_concerns"
```

**`app/models/queue.py`** - mirror the same 3 additions on the Pydantic `QueueType` enum.

**Alembic migration** - Postgres can't safely add enum values and use them in the same transaction, so follow the existing precedent in this repo (`8de3c8b4f094_replace_college_with_course_and_major.py`) of rename-old-type → create-new-type-with-all-values → swap the column over → drop old type - but **without truncating any data**, since (unlike that migration) real ticket/queue history now exists that must be preserved. After the type swap, `INSERT` the 3 new `queues` rows per the defaults table above (name, queue_type, ticket_letter, description, allow_priority, max_capacity, slot_duration_minutes, status=`ACTIVE`, current_ticket_number=0). `downgrade()` deletes the 3 new queues (and any tickets created against them, to satisfy the FK before the type swap-back) and restores the original 5-value enum.

**`app/core/init_db.py`** - add the same 3 queues to `seed_initial_data`'s queue list, for consistency on fresh installs that never ran this migration's data step directly (`seed_initial_data` is guarded by "skip if any queue already exists," so this only matters for a genuinely fresh database).

### Frontend

**`src/services/studentServices.js`** - repoint 3 services' `queueType`:
- `adding_dropping`: `'enrollment'` → `'adding_dropping'`
- `petition_class`: `'enrollment'` → `'petition_class'`
- `others`: `'others'` → `'other_concerns'`

(`enrollment` and `general_inquiry` keep their current `queueType` values unchanged.)

**`src/components/icons/QueueIcons.js`** - add `adding_dropping`/`petition_class`/`other_concerns` entries to `ICONS_BY_TYPE` (reusing the existing `AddDropIcon`/`PetitionIcon`/`OthersIcon` components already defined there) and to `LABELS_BY_TYPE` (`'Adding & Dropping'`, `'Petition Class'`, `'Others'`).

**`src/views/QueueManagementView.vue`** - add the 3 new types to `queueTypeOptions` (the Create-Queue dropdown) and `TYPE_TO_DEFAULT_LETTER`, so admins can still recreate one of these queues manually in the future (e.g. after a hypothetical deletion) with the dropdown staying complete. No other code changes needed here - the service-card grid (`serviceCards` computed) already matches services to queues generically by `queue_type`, so once the 3 new queues exist, their cards resolve automatically instead of showing the "no queue exists yet" fallback.

**`CounterView.vue`** - no code changes needed; its service-to-queue resolution is the same generic `queue_type` match, so the 3 previously-shared services now resolve to their own distinct queue automatically.

## Testing

No automated test framework is configured for this project (per `CLAUDE.md`). Manual verification plan, against the real running stack:

1. Run `alembic upgrade head` and confirm it succeeds without errors; check `alembic current` lands on the new revision.
2. Query `/api/queues` (staff-authenticated) and confirm 8 queues exist total, with the 3 new ones present at their specified defaults (ticket letter, capacity, slot duration, priority flag).
3. Take one ticket per service via `POST /api/tickets`, for all 8 services, and confirm each lands on a distinct `queue_id` with the correct `ticket_code` prefix (A-, P-, X- for the 3 new ones).
4. On Queue Management: confirm all 8 service cards now show independent status/capacity, and pausing one (e.g. Adding & Dropping) does NOT affect its former queue-mates (Enrollment, Petition Class).
5. On the Counter: confirm selecting each of the 8 services now shows its own independent waiting list (previously, picking any of the 3 enrollment-sharing services showed the same combined list).
6. Confirm existing (pre-migration) tickets are untouched - still attached to their original queue_id, no data loss.
7. Optionally run `alembic downgrade -1` against a disposable copy of the dev DB (not the primary one) to sanity-check the downgrade path doesn't error, given it needs to delete rows before shrinking the enum.

## Out of Scope

- An "edit queue" feature (capacity/slot/ticket-letter changes after creation) - not built here; the new queues' defaults are fixed by the migration.
- Reassigning historical tickets from the old shared queues to the new split queues.
- Any change to how Dashboard aggregates by `purpose` (already correct and unaffected - grouping by `purpose` naturally continues to work once purposes map to distinct queues too).
