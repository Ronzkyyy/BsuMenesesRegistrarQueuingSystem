# Appointment System — Design

## Problem

Students currently only interact with a queue by physically arriving and taking a ticket on the spot (`POST /api/tickets`, keyed by `student_id` lookup, no login). There is no way to reserve a future time slot ahead of a visit, which means every visit — regardless of how routine — requires standing in a walk-in line. This feature adds a booking step in front of the existing ticket flow: a student books a time slot for a service, receives a QR code representing that booking, and when they arrive, registrar staff scan the QR to automatically create a normal queue ticket for them, reusing the existing ticket/priority/position logic unchanged.

## Decision

Add a new `appointments` domain, integrated into the existing queue app (not a separate service): a booking flow reachable from the public frontend, a `/admin/checkin` scan page for staff, and a check-in endpoint that creates a ticket via the **existing, unmodified** `TicketService.create_ticket`. Time slots are computed on the fly from existing/extended `Queue` settings rather than stored as their own rows. The QR encodes a single opaque, cryptographically random token — validated with a live server round-trip at scan time.

### Why compute slots from Queue settings instead of a dedicated slot table

- **Dedicated `AppointmentSlot` table**: allows per-slot overrides (e.g. a half-day closure) but requires a generation job/migration path and admin UI just to manage slot rows, for a campus-scale system that doesn't need that flexibility yet.
- **Computed from `Queue` fields (chosen)**: `slot_duration_minutes` already exists on `Queue`; add `operating_start_time`, `operating_end_time`, `slot_capacity`, `booking_window_days`, `booking_enabled`. A slot is just `(date, start_time)` derived from these, and its availability is `COUNT(appointments WHERE queue_id, date, start_time, status='booked') < slot_capacity`. Zero new tables for slots, always consistent with the queue's current configuration, editable from the existing Queue Management screen.

### Why an opaque random token instead of a signed token

An earlier iteration of this design used a signed (asymmetric-keypair) token so a scan could be verified without a live database call, to support scanning while the registrar counter was offline. That requirement has been dropped: **the QR always travels on the student's own phone** (screenshot or downloaded image) and is scanned live at the counter, so there is no offline verification case to design for.

- **Signed/JWT token**: adds a keypair to manage and asymmetric-crypto code for no benefit once every scan is already an online, live API call.
- **Opaque random token (chosen)**: `secrets.token_urlsafe(32)` generated at booking time, stored on the `appointments` row, encoded directly in the QR. Scanning is always `POST /api/appointments/checkin { token }`, which looks the token up, and atomically flips its status — unguessable (256 bits of entropy) and inherently single-use because reuse is a database check, not a client-side one.

### Why appointment check-in produces a normal ticket (no queue-jump)

Per requirement, a checked-in appointment is inserted using the same `calculate_priority` / `calculate_position` logic as any walk-in ticket (student's `is_scholar`/`is_varsity`/`is_graduating` flags still apply). The appointment only guarantees a reserved slot existed and the visit was expected — not a jump ahead of same-priority walk-ins. This keeps `TicketService` completely untouched, so the entire existing ticket/priority/display/counter pipeline is reused as-is with zero regression risk.

## Data Model

New table `appointments`:

| Column | Type | Notes |
|---|---|---|
| `id` | PK | |
| `reference_code` | String, unique | Short human-readable code (e.g. `APT-000482`), shown alongside the QR and used for manual lookup |
| `student_id` | FK → students | |
| `queue_id` | FK → queues | |
| `appointment_date` | Date | |
| `slot_start_time` / `slot_end_time` | Time | Captured at booking time; stays fixed even if the queue's settings change later |
| `purpose` | Text, nullable | Same idea as `ticket.purpose` |
| `qr_token` | String, unique, indexed | Random 32-byte token encoded in the QR. Never returned by any endpoint after the initial booking response (e.g. excluded from any future "list appointments" admin view) |
| `status` | Enum: `booked`, `checked_in`, `cancelled`, `expired` | |
| `checked_in_at` | DateTime, nullable | |
| `checked_in_by` | FK → users, nullable | Staff who performed the check-in |
| `ticket_id` | FK → tickets, nullable | Set once check-in creates a ticket |
| `created_at` / `updated_at` | DateTime | |

Extend `QueueDB` (all additive, defaulted columns — no backfill needed):
- `booking_enabled: bool` (default `False` — opt-in per queue)
- `operating_start_time`, `operating_end_time: Time`
- `slot_capacity: int` — appointments allowed per slot
- `booking_window_days: int` — how many days ahead a student may book (default e.g. 14)

## Data Flow

**Booking → QR:**
1. Student, on their own device at any time, opens an "Appointments" flow: enters student ID (same search-by-ID pattern as the existing ticket flow), picks a service/queue, then a date/slot. `GET /api/appointments/availability?queue_id=&date=` returns each computed slot with its `booked/capacity` count.
2. `POST /api/appointments` validates: no other active (`booked`) appointment for this student, slot has capacity, date within `booking_window_days`, queue has `booking_enabled=true`. Creates the row, generates `reference_code` and `qr_token`, returns both.
3. Frontend renders the token as a QR code client-side (new `qrcode` npm dependency) with `reference_code` printed underneath as a fallback if the camera can't read it. The QR/reference code screen is screenshot-able and the image is downloadable.
4. Student can revisit the booking later via `GET /api/appointments/lookup?student_id=&reference_code=` (mirrors the existing `my-ticket` pattern) and cancel it via `POST /api/appointments/{id}/cancel`, provided it's still `booked`.

**Scan → Queue creation:**
5. New admin route `/admin/checkin` (role: admin/registrar/staff, same as Counter) opens the device camera to decode a QR (new `qr-scanner` npm dependency, wraps `getUserMedia`) or accepts manual entry of the `reference_code`.
6. `POST /api/appointments/checkin { token? , reference_code? }` — looks up the appointment, checks `status == 'booked'`, atomically transitions it (`UPDATE ... WHERE status='booked'`, preventing a double-scan race between two counters from creating two tickets), then calls `TicketService.create_ticket` unchanged, and links the resulting `ticket_id` back onto the appointment. Returns the created ticket for the staff UI.
7. If outside the appointment's window (early/late) but not yet `expired`, the server responds with a "needs confirmation" result; the frontend shows an override prompt, and a confirmed override resends the request with `force=true`.
8. **Manual lookup fallback:** the same `/admin/checkin` page has a search box (student ID or reference code) calling `GET /api/appointments/search?...`, letting staff trigger the same check-in without a working camera.

## API Endpoints

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/api/appointments/availability` | Public | Slot list + booked/capacity counts for a queue/date |
| POST | `/api/appointments` | Public | Book an appointment |
| GET | `/api/appointments/lookup` | Public | Student re-views their booking by student ID + reference code |
| POST | `/api/appointments/{id}/cancel` | Public | Student cancels their own `booked` appointment |
| GET | `/api/appointments/search` | Staff | Manual lookup fallback (student ID or reference code) |
| POST | `/api/appointments/checkin` | Staff | Scan/manual check-in → creates a ticket |

Follows the existing pattern: booking-side endpoints are public (mirroring `POST /api/tickets`), staff-side endpoints use `require_role(UserRole.ADMIN, UserRole.REGISTRAR, UserRole.STAFF)`.

## Edge Cases & Failure Modes

- **Unknown/garbled token or reference code** → "invalid code — try manual lookup."
- **Already checked in** (scanned again, e.g. a screenshot shown twice) → "already used at HH:MM by `<staff>`," no ticket created.
- **Cancelled before scan** → "cancelled — book again or take a walk-in ticket."
- **Expired** (slot passed without check-in, marked `expired` by a Celery beat task alongside the existing `check_no_show_tickets`) → "expired — use manual lookup or take a walk-in ticket."
- **Outside window but not expired** → override prompt; staff's decision to override is implicit in `checked_in_by` on the resulting record.
- **Queue closed/paused at scan time** → same rejection `TicketService.create_ticket` already returns for an inactive queue.
- **Student already holds an active ticket/appointment** → blocked by the existing one-active-ticket rule; the appointment stays `booked` so the student can resolve the conflict and retry.
- **Two counters scan the same QR near-simultaneously** → the atomic status flip lets exactly one succeed; the second gets an immediate "already checked in" response (always-online, so this resolves in real time, not asynchronously).
- **Student cancels in one tab while being scanned in another** → whichever write lands first wins; the loser sees a normal "already checked in" or "cannot cancel — already checked in" message, no corrupted state.

## Testing

No automated test framework is configured for this project (per `CLAUDE.md`). Plan, against the real running stack (per this project's standing guidance to verify against the real backend+DB, not mocks):

1. **Booking limits**: attempt to book a second active appointment for the same student → blocked; book at `booking_window_days + 1` → blocked; book a slot at `slot_capacity` → blocked with a clear "slot full" message; book the last open slot → succeeds and the slot now shows full in `availability`.
2. **QR round-trip**: book an appointment, confirm the rendered QR decodes (via a phone camera or a QR-reading tool) to a token that matches what `POST /api/appointments/checkin` accepts.
3. **Check-in success**: scan a valid `booked` appointment → a ticket appears with the correct queue/priority, and is visible end-to-end in the existing Counter and Display Board views, unmodified.
4. **Reuse/race**: check in the same appointment twice in a row → second attempt rejected with "already checked in"; fire two concurrent check-in requests for the same appointment (e.g. via two browser tabs) → exactly one ticket is created.
5. **Rejections**: verify each edge case above produces its documented, distinct error message (expired, cancelled, invalid code, outside window, queue closed, student already has an active ticket).
6. **Manual lookup fallback**: with the camera unavailable/denied, complete a full check-in via the reference-code search box alone.
7. **Cancel flow**: student cancels a `booked` appointment via `student_id` + `reference_code`; confirm the slot's `availability` count frees up and the token stops validating for check-in.
8. **No-show expiry job**: manually trigger the Celery beat task against a `booked` appointment whose slot is in the past → transitions to `expired`, and no longer blocks the student's one-active-appointment rule.
9. **Migration**: `alembic upgrade head` / `alembic downgrade -1` round-trip cleanly against a copy of the dev DB (per this project's standing guidance to check `alembic current` and use real migrations, not drop/recreate).

## Risks & Irreversible Steps

- The migration only adds a new table and new nullable/defaulted `Queue` columns — additive and reversible via `alembic downgrade`, no risk to existing `tickets`/`students`/`queues` data.
- Check-in reuses `TicketService.create_ticket` unmodified, so the existing walk-in flow has effectively zero regression risk from this feature.
- `qr_token` must never be included in any future "list/export appointments" staff-facing endpoint — it should only ever appear once, in the booking response. Worth flagging explicitly since it's an easy field to accidentally include in a generic serializer later.
- New camera-permission requirement on staff devices for `/admin/checkin` — an operational/rollout risk (browser camera permissions, lighting, device availability), mitigated by the manual reference-code fallback always being available.
- Rolling out with `booking_enabled=false` by default on all existing queues means the feature ships inert until explicitly turned on per queue — low blast radius for the initial deploy.

## Rollout Plan

1. Migration: `appointments` table + new `Queue` columns (additive, `booking_enabled` defaults false everywhere).
2. Backend: models/services/API for booking, availability, lookup, cancel — no check-in yet.
3. Frontend: booking flow (service → date/slot → confirm) + QR/reference-code display, lookup, and cancel pages.
4. Backend: check-in endpoint + Celery no-show/expiry beat task.
5. Frontend: `/admin/checkin` scan page (camera + manual lookup fallback).
6. Enable `booking_enabled` on one pilot queue, verify end-to-end with real staff and real students, then roll out to remaining queues.

## Out of Scope

- Offline scanning/check-in (dropped — the QR always travels on the student's phone and is scanned live).
- Email/SMS delivery of the QR (no such infrastructure exists today; booking confirmation is in-browser only, with re-lookup via student ID + reference code).
- Student self-reschedule (cancel-and-rebook only).
- Multiple simultaneous active appointments per student.
- Per-slot capacity overrides or slot closures beyond the queue's normal operating hours/status.
- Any change to `TicketService`, existing ticket endpoints, Counter, or Display Board behavior.
