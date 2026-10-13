# Appointment Email Notifications — Design

**Date:** 2026-10-13
**Status:** Draft — awaiting review
**Origin:** Defense panel revision #2
**Path type:** Architectural (new outgoing student email, a scheduled
trigger outside the app, schema migration on the shared production
database)

## Problem

A student who books an appointment gets the reference code and QR code
only once, on the booking screen, and is told to screenshot them. Nothing
reminds them on the day. A lost screenshot or a forgotten date means a
missed slot. The panel asked that students who booked are emailed before
their appointment.

The app already sends staff email (verification and password resets)
through the Gmail API (`app/services/email_sender.py`). It has never
emailed a student.

## Goals

1. **Booking confirmation.** Right after a booking, the student is emailed
   the details and the check-in QR code.
2. **Same-day reminder.** At **5:00 AM Manila time on the appointment
   day**, every student still booked for that day is emailed the same
   details and QR code.
3. Both emails include, for Request Documents, the requested documents,
   their fees and what to bring.
4. Reminders go out even though Render's free tier puts the server to sleep
   when idle.
5. Staff can see whether each reminder was sent, and can resend the
   confirmation.
6. Students can spot a wrong email address before booking.

## Non-goals

- **No SMS.** Email only.
- **No reminder the day before**, and none at a fixed number of hours
  before the slot. There is one reminder, in the morning.
- **No cancel link in the email.** Students cancel from the appointment
  lookup page, as they do today.
- **No emails for walk-in kiosk tickets.** These emails are for
  appointments only.
- **No self-service email change for students.** The public pages can't
  change a stored student email. That would let anyone who knows a student
  number redirect that student's QR code. Staff fix emails in Student
  Management, as they do today.
- **No paid Render plan and no new third-party service.** The trigger is
  GitHub Actions, which the repo already uses.

## Decisions (confirmed with user)

| Question | Decision |
|---|---|
| When | Morning of the appointment, **5:00 AM** Manila. |
| Confirmation | Yes, an email right after booking, plus the reminder. |
| Content | Basics + **QR code image** + **documents, fees and requirements** (Request Documents). No cancel link. |
| Trigger | **GitHub Actions schedule** calls a secret-protected endpoint. That call also wakes the Render server. |
| Retry | Runs at 5:00 and 5:30 AM. Each run sends only what hasn't been sent. A reminder is attempted at most twice and never sent twice. |
| Typo protection | The booking form shows the **masked** address ("j***@gmail.com") before the student confirms. |
| Staff view | **Reminder** status column + **Resend** (confirmation) button in Appointment Management. |

## The Render sleep problem, and why GitHub Actions

On Render's free tier the web service sleeps after about 15 minutes with no
requests. The Celery worker runs inside that same container
(`RUN_WORKER_INLINE=true`), so a beat task scheduled for 5:00 AM simply
doesn't run if nobody has visited the site since 4:45 AM. That is the
normal case at 5 AM.

A scheduled GitHub Actions workflow sends an HTTP request at 5:00 AM. The
request wakes the server, and the server sends the reminders while
handling it. This costs nothing, needs no new account, and runs from the
repo itself.

Known limits, accepted:
- GitHub can start scheduled jobs **5–15 minutes late** under load. 5:00 AM
  leaves about three hours before the first 8:00 AM slot.
- GitHub **disables scheduled workflows after 60 days with no commits** to
  the repo, and emails the owner first. Over a long break, someone must
  re-enable the workflow (Actions → workflow → "Enable workflow").
  Rollout step 5 covers this.

## Architecture

```
Booking (public)                         5:00 / 5:30 AM Manila
POST /api/appointments                   GitHub Actions (cron, UTC 21:00 / 21:30)
   │  creates appointment                    │  POST /api/internal/appointment-reminders
   │  BackgroundTasks ──► send confirmation  │  X-Cron-Secret: <secret>
   ▼                                         ▼
appointment_email.send_confirmation()    appointment_email.send_due_reminders()
   │                                         │  advisory lock → one run at a time
   └──────────────► build_appointment_email() ◄──┘   claim → send → record
                         │
                         ▼
               email_sender.send_email(..., inline_images=[QR png])
```

New units, each with one purpose:

- `app/services/appointment_email.py`: builds the appointment email (text
  + HTML + QR), sends the confirmation, and runs the reminder batch. It
  depends on `email_sender`, `campus_time` and `AppointmentDB`.
- `app/api/internal.py`: one cron endpoint, secret-gated, with no user
  session.
- `.github/workflows/appointment-reminders.yml`: the schedule.
- Edits to `email_sender.py` (inline image support), `api/appointments.py`
  (send the confirmation, resend route), `models/student.py` (masked
  email), and the frontend booking form and Appointment Management.

## Data model

Migration `c0d1e2f3a4b5` (down_revision `b9c0d1e2f3a4`) adds three
nullable or defaulted columns to `appointments`. This is additive and safe
for old code:

| column | type | meaning |
|---|---|---|
| `confirmation_sent_at` | `DateTime(timezone=True)`, null | When the latest confirmation (or resend) was handed to Gmail |
| `reminder_sent_at` | `DateTime(timezone=True)`, null | When the reminder was handed to Gmail; non-null = never send again |
| `reminder_attempts` | `Integer`, not null, server default `0` | Reminder sends tried; capped at `REMINDER_MAX_ATTEMPTS` (2) |

The API derives a **reminder status** from these. It is not stored:

| `reminder_status` | when |
|---|---|
| `sent` | `reminder_sent_at` is set |
| `failed` | not sent, and `reminder_attempts >= 2`, or the appointment day has passed with ≥ 1 attempt |
| `pending` | still `booked`, the appointment day is today or later, not sent, and attempts are left |
| `not_applicable` | cancelled, expired, or checked in before any reminder was due |

Timestamps are written with `campus_time.campus_now()`, which is
timezone-aware. A naive `datetime.now()` would be stored 8 hours off on a
machine set to Manila time.

## Backend

### Configuration (`app/core/config.py`)

- `CRON_SECRET: Optional[str] = None`. When unset, the cron endpoint
  returns `404`, as if it didn't exist. When set it must be at least 32
  characters, and the app fails fast at import otherwise, following the
  `SECRET_KEY` precedent.
- `REMINDER_MAX_ATTEMPTS = 2`, a module constant in `appointment_email.py`
  (not an env var, to keep it simple).
- Existing settings used as-is: `EMAIL_BACKEND`, `EMAIL_FROM`, the
  `GMAIL_*` settings, `CAMPUS_NAME`, `CAMPUS_TIMEZONE`.

### Inline images — `email_sender.py`

`send_email(to, subject, text, html=None, inline_images=None)`.
`inline_images` is a list of `(content_id, png_bytes)`. `build_message`
attaches each one as a `related` part of the HTML alternative
(`Content-ID: <qr@bsu>`), and the HTML references it as `src="cid:qr@bsu"`.

**Why CID and not a `data:` URI:** Gmail, Outlook and most other clients
strip `data:` images from email. A CID inline attachment shows up
everywhere. Clients that block images still get the reference code as
text.

`send_email` keeps its contract: it never raises and returns `True` only
when Gmail accepted the message. The console backend logs that an image
was attached, never its bytes.

### QR generation

Add **`segno`** (pure Python, no Pillow or other native dependency),
pinned with `==` in `requirements.txt` per the supply-chain rule.
`segno.make(appointment.qr_token, error="m").save(buf, kind="png",
scale=8, border=2)`. It encodes exactly the `qr_token` string the booking
page encodes with the `qrcode` npm package, so the Check-In scanner reads
both the same way.

### The email — `build_appointment_email(appointment, kind)`

`kind` is `"confirmation"` or `"reminder"`. Both share one template.

- **Subject.** Confirmation: `Your registrar appointment is booked —
  APT-000123`. Reminder: `Reminder: your registrar appointment is today at
  9:00 AM — APT-000123`. The subject never contains the student's name,
  because `email_sender` logs subjects and log lines must not name students
  (the same rule as the Celery tasks).
- **Body, in order:**
  1. a greeting with the student's first name;
  2. a summary with the service (queue name), the date (e.g. "Wednesday,
     October 14, 2026") and the slot ("9:00 – 9:30 AM");
  3. the check-in window, worded from `GRACE_MINUTES_BEFORE` /
     `GRACE_MINUTES_AFTER` ("Check in from 8:45 AM until 9:45 AM");
  4. the QR code image with the reference code in large text under it;
  5. for Request Documents only: the requested documents (snapshot name +
     fee), the total (using the same "Total" / "Total of listed fees" rule
     as the kiosk), and a "What to bring" list of each requirements note;
  6. the place (`CAMPUS_NAME` Registrar's Office) and a line saying this is
     an automated message and replies aren't read.
- The HTML uses table layout and inline styles only (email clients ignore
  `<style>` blocks and modern CSS), in the BSU pink accent `#E85D8E`. The
  plain-text part has the same content without the image.
- Every value inserted into the HTML is passed through `html.escape`.
  Student names, requirements notes and document names are free text from
  the kiosk or an admin, and must never become markup in a mail client.

### Confirmation on booking

`POST /api/appointments` (public) gains `background_tasks:
BackgroundTasks`. After `create_appointment` succeeds, it calls
`background_tasks.add_task(appointment_email.send_confirmation,
appointment.id)`, and the response returns at once as today.

`send_confirmation(appointment_id)` opens its own `SessionLocal()`,
because the request session is closed by then. It reloads the appointment
and skips it unless it is still `booked`. It sends, and on success sets
`confirmation_sent_at`. It never raises.

### Reminder batch — `send_due_reminders()`

1. `SELECT pg_try_advisory_xact_lock(<constant key>)`. If another run holds
   the lock, return `{"status": "already_running"}`. This is what makes
   overlapping 5:00 and 5:30 runs (or a manual run) unable to email anyone
   twice.
2. Select appointments where `status = booked`, `appointment_date =
   campus_today()`, `reminder_sent_at IS NULL`, `reminder_attempts <
   REMINDER_MAX_ATTEMPTS`, and the slot's end hasn't passed
   (`campus_datetime(date, slot_end_time) > campus_now()`), so a late run
   doesn't remind someone whose slot is over. The select uses the ORM with
   bound parameters.
3. For each one: increment `reminder_attempts` and commit, then send, and
   on success set `reminder_sent_at = campus_now()` and commit. The attempt
   is counted *before* sending, so a crash mid-send can't loop forever.
4. Return `{"status": "ok", "due": n, "sent": s, "failed": f}`. Counts only,
   never names or addresses.

Sending is sequential. At a few seconds per Gmail call, about 100
appointments fit well inside the workflow's 5-minute timeout. Gmail's
per-day cap for this kind of account (≈ 500 messages) is far above the
registrar's daily appointment volume.

### Cron endpoint — `app/api/internal.py`

`POST /api/internal/appointment-reminders`

- **Auth:** an `X-Cron-Secret` header compared with
  `hmac.compare_digest` against `settings.CRON_SECRET`. A wrong or missing
  header returns `403`. An unset `CRON_SECRET` returns `404`. There is no
  cookie or JWT, since this is machine-to-machine.
- `@limiter.limit("6/hour")` + `request: Request`. It is a public URL, so
  it gets the same per-IP layer as other public routes.
- It runs `send_due_reminders()` inside the request and returns its counts.
- **Audit:** `log_security_event("appointment.reminders_run",
  outcome=…, detail="due=…, sent=…, failed=…")`. A bad secret logs
  `outcome="denied"`.
- It is added to CLAUDE.md's list of deliberately public endpoints, with
  the reason for the secret gate.

### Resend — `POST /api/appointments/{id}/resend-confirmation`

- `require_role(UserRole.STAFF)`, with `id` `> 0`.
- `404` if the appointment doesn't exist, and `400` unless it is `booked`.
- It queues `send_confirmation` as a background task and returns `202`
  `{"detail": "Sending the confirmation to j***@gmail.com."}` (masked even
  for staff, since the screen may be visible at the counter).
- **Audit:** `appointment.confirmation_resent` (actor = staff username,
  target = `appointment#id`).

### Masking the public student email (related fix)

`GET /api/students/search` and `POST /api/students` are public and return
`StudentPublic`, which currently includes the student's **full email**.
Student numbers are guessable (10 digits, sequential by year), so anyone
can collect addresses. The booking form's masked notice would hide nothing
if the full address were already in the response.

`StudentPublic.email` → `email_masked: str`, built by `mask_email()` in
`app/services/email_mask.py`:

| input | output |
|---|---|
| `juan.delacruz@gmail.com` | `j***@gmail.com` |
| `ab@bulsu.edu.ph` | `a***@bulsu.edu.ph` |
| `x@yahoo.com` | `*@yahoo.com` |

The domain stays visible because it's where typos tend to show
(`gmial.com`, `gmail.co`). Staff endpoints (`Student`, `StudentInDB`)
keep the full address.

## Frontend

- **Booking form (`AppointmentsView.vue`)**: once the student is found or
  registered, a notice above **Confirm Booking** reads: "We'll email your
  QR code and a reminder on the morning of your appointment to
  **j***@gmail.com**. Not your email? Ask at the registrar's window to
  update it." The confirmation screen adds "We've also emailed this to
  j***@gmail.com." The screenshot advice stays, since email can be slow or
  filtered.
- **Kiosk (`QueuesView.vue`)**: the read-only email box shows
  `email_masked`.
- **Appointment Management**: a **Reminder** column with a badge (Sent /
  Pending / Failed / —), plus a **Resend** button on `booked` rows. The
  button shows the API's masked message as a notice. It is disabled while
  sending.
- **Store**: a `resendAppointmentConfirmation(id)` action. `searchStudent`
  and `registerStudent` callers read `email_masked`.

## GitHub Actions — `.github/workflows/appointment-reminders.yml`

```yaml
on:
  schedule:
    - cron: "0 21 * * *"    # 05:00 Asia/Manila (UTC+8, no DST)
    - cron: "30 21 * * *"   # 05:30 retry run
  workflow_dispatch: {}      # manual "Run workflow" button for testing
permissions: {}              # no repo access needed
jobs:
  remind:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - run: |
          curl -fsS --max-time 300 --retry 6 --retry-delay 20 --retry-all-errors \
            -X POST -H "X-Cron-Secret: $CRON_SECRET" \
            "$BACKEND_URL/api/internal/appointment-reminders"
        env:
          CRON_SECRET: ${{ secrets.CRON_SECRET }}
          BACKEND_URL: ${{ secrets.BACKEND_URL }}
```

- The `--retry` options cover the cold start: a sleeping Render service can
  answer `502`/`503` for up to about a minute while it boots. Retrying is
  safe because the endpoint is idempotent.
- No third-party actions are used, so there is nothing to pin.
- Both values are repository **secrets**, so neither appears in logs.

## Testing

**Backend (pytest)**: mail captured by patching `email_sender.send_email`,
as in `tests/test_email_password_reset.py`. The clock is pinned with
`monkeypatch.setattr(campus_time, "campus_now", …)`.

- `test_appointment_email.py`:
  - The confirmation is queued on booking; it has the reference code,
    the date, the slot and one inline PNG whose decoded QR text equals
    `qr_token` (checked by re-generating with `segno` and comparing the
    bytes); the subject has no student name.
  - The Request Documents email lists the snapshot documents, fees, total
    and requirements; other services have no documents section.
  - HTML escaping: a student named `<b>x</b>` and a requirement containing
    `<script>` appear escaped.
  - Reminder batch: it sends only today's `booked` appointments; skips
    cancelled, expired, checked-in, tomorrow's, already-sent and
    slot-ended ones; a second run sends nothing (no duplicates); a failed
    send increments attempts and retries once; after 2 failures it gives up
    with status `failed`.
  - Advisory lock: while the lock is held, a second run returns
    `already_running` and sends nothing.
- `test_internal_api.py`: correct secret → `200` + counts; wrong or missing
  → `403` + a `denied` audit event; `CRON_SECRET` unset → `404`; the
  response body never contains an email address.
- `test_appointments_api.py` (resend): Staff can resend (`202`, masked
  address), anonymous gets `401`, a non-booked appointment gets `400`, and
  the audit event is emitted.
- `test_student_public_email_masked.py`: `mask_email` cases; `GET
  /students/search` and `POST /students` return `email_masked` and no
  `email` key; staff student routes still return the full address.
- `test_config.py`: a `CRON_SECRET` shorter than 32 characters fails at
  import.

**Frontend (Vitest)**: the store's `resendAppointmentConfirmation`
action; a reminder-status badge helper.

**End-to-end**: on `bsu_queue_test` with `EMAIL_BACKEND=console`, book an
appointment and see the confirmation in the backend log. Pin the date by
booking for tomorrow and calling the endpoint with a
`campus_today`-patched test, or run it the next morning. Then a real
send: after deploy, run the workflow manually (`workflow_dispatch`) with a
test booking dated today on a staff member's own email.

## Rollout

1. **Don't run `alembic upgrade head` locally against `DATABASE_URL`.**
   It is the shared database behind production. The migration applies on
   the Render deploy after merge. It only adds columns with defaults, so
   it's safe if old code briefly runs against it.
2. Generate a secret: `python -c "import secrets;
   print(secrets.token_urlsafe(48))"`.
3. **Render** → backend service → Environment: add `CRON_SECRET` = that
   value. `EMAIL_BACKEND=gmail` and the `GMAIL_*` values are already set
   from the password-reset work.
4. **GitHub** → repo → Settings → Secrets and variables → Actions → New
   repository secret, twice: `CRON_SECRET` (the same value) and
   `BACKEND_URL` (the Render backend's `https://…onrender.com` base URL,
   with no trailing slash).
5. After merging, open Actions → "Appointment reminders" → **Run
   workflow** once to check the wiring (it reports `due=0` if nobody is
   booked today). **If the repo goes 60 days without a commit, GitHub
   pauses the schedule.** Re-enable it on that same page.
6. Update `CLAUDE.md`: the new endpoints, the public cron endpoint and its
   secret gate, the new audit events, `CRON_SECRET`, the `segno`
   dependency, masked `StudentPublic`, and a "Background tasks" note that
   the reminder is triggered by GitHub Actions, not Celery beat.

## Open questions

- **Sender name.** `EMAIL_FROM` currently names the system for staff
  password resets. Should students see something friendlier, e.g.
  "BSU Meneses Registrar"? That only changes an env var, not code.
