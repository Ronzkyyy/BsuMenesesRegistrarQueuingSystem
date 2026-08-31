# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**BSU Registrar Queue System** - A queue management system for Bulacan State University - Meneses Campus Registrar.

**Tech Stack:**
- **Backend**: Python FastAPI, Celery, Redis, PostgreSQL, SQLAlchemy 2.0, Pydantic v2
- **Frontend**: Vue 3 (Vite), Pinia, Vue Router, Axios, Tailwind CSS, date-fns
- **Deployment**: Docker Compose (backend, frontend, PostgreSQL, Redis, Celery worker)

## Project Structure

```
bsu-registrar-queue/
├── backend/
│   ├── app/
│   │   ├── api/           # REST endpoints (auth, queues, tickets, students)
│   │   ├── core/          # Database, config, security
│   │   ├── models/        # Pydantic models (API schemas)
│   │   ├── services/      # Business logic (queue, ticket, student, notifications)
│   │   ├── db_models.py   # SQLAlchemy ORM models
│   │   ├── main.py        # FastAPI app entry point
│   │   └── worker.py      # Celery worker config
│   ├── migrations/        # Alembic migrations
│   ├── requirements.txt
│   ├── alembic.ini
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── views/         # Page views (Home, Queues, QueueDetail, Admin)
│   │   ├── stores/        # Pinia stores (queue.js)
│   │   ├── router/        # Vue Router
│   │   └── assets/        # Tailwind CSS
│   ├── package.json
│   ├── vite.config.js
│   └── Dockerfile
└── docker-compose.yml
```

## Common Development Commands

### Docker (Full Stack)
```bash
cd bsu-registrar-queue
docker-compose up -d              # Start all services
docker-compose up -d --build      # Rebuild and start
docker-compose down               # Stop all services
docker-compose logs -f backend    # View backend logs
docker-compose logs -f worker     # View Celery worker logs
```

### Backend Development
```bash
cd bsu-registrar-queue/backend
pip install -r requirements.txt   # Install dependencies
uvicorn app.main:app --reload     # Run FastAPI dev server (port 8000)
alembic upgrade head              # Apply migrations
alembic revision --autogenerate -m "msg"  # Create new migration
python -m pytest                  # Run tests (if pytest configured)
```

### Frontend Development
```bash
cd bsu-registrar-queue/frontend
npm install                       # Install dependencies
npm run dev                       # Vite dev server (port 5173, proxies /api to :8000)
npm run build                     # Production build
npm run preview                   # Preview production build
```

### Database
```bash
cd bsu-registrar-queue/backend
alembic upgrade head              # Apply all migrations
alembic downgrade -1              # Rollback last migration
alembic history                   # Show migration history
```

## Architecture Overview

### Backend Layers
1. **API Layer** (`app/api/`): FastAPI routers with dependency injection for DB sessions and auth
2. **Service Layer** (`app/services/`): Business logic (QueueService, TicketService, StudentService, Notifications)
3. **Data Layer** (`app/db_models.py`): SQLAlchemy ORM models with relationships
4. **Schema Layer** (`app/models/`): Pydantic v2 models for request/response validation

### Key Domain Models
- **Queue**: Service queues (Enrollment, Document Request, Clearance, Scholarship, Others)
- **Student**: Student profiles with priority flags (scholar, varsity, graduating)
- **Ticket**: Queue tickets with priority levels (Normal, Priority, Urgent) and status (Waiting, Serving, Completed, Cancelled, No-Show)
- **User**: Staff authentication (Admin, Registrar, Staff roles with JWT)

### API Endpoints
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/auth/login` | Public | Staff login |
| GET | `/api/queues/active` | Public | List active queues for students |
| POST | `/api/tickets` | Public | Student takes a ticket |
| GET | `/api/tickets/my-ticket` | Public | Get student's current ticket |
| POST | `/api/tickets/{id}/cancel` | Public | Student cancels ticket |
| GET | `/api/queues` | Staff | List all queues (admin/registrar) |
| POST | `/api/queues` | Admin/Registrar | Create queue |
| PATCH | `/api/queues/{id}/status` | Admin/Registrar | Update queue status |
| POST | `/api/tickets/{id}/serve` | Staff | Mark ticket as serving |
| POST | `/api/tickets/{id}/complete` | Staff | Mark ticket completed |
| POST | `/api/tickets/queue/{id}/next` | Staff | Serve next ticket (priority-aware) |

### Background Tasks (Celery)
Defined in `app/worker.py` with Redis broker:
- `update_all_wait_times` - Every minute
- `check_no_show_tickets` - Every 5 minutes
- `send_reminder_check` - Every 5 minutes
- `send_ticket_reminder` / `send_ticket_called` - On-demand tasks

### Authentication & Authorization
- Passwords hashed with **bcrypt** via passlib `CryptContext(schemes=["bcrypt"])`
  in `app/core/security.py`. All storage goes through `get_password_hash`,
  all checks through `verify_password` — never compare or store plaintext.
  Password inputs are capped at 72 bytes (bcrypt's limit) in the Pydantic models.
- **Failed-login lockout.** `POST /auth/login` counts consecutive bad passwords
  in `users.failed_login_attempts`; after `MAX_FAILED_LOGIN_ATTEMPTS` (5) it
  sets `users.locked_until` and returns `429` for `ACCOUNT_LOCKOUT_MINUTES`
  (15) — the correct password is refused while locked. Any successful login
  clears both fields. This is per-account; the `@limiter.limit("5/minute")`
  on the same route is the complementary per-IP layer.
- **Security audit log** (`app/core/audit.py`): `log_security_event(event, *,
  outcome, request=None, actor=…, target=…, detail=…)` emits one JSON line on
  the `bsu.security` logger (stdout, INFO, never suppressed by `LOG_LEVEL`).
  Never pass a password, token, or request body. Events currently emitted:
  `auth.login` (success / failure / blocked / denied), `auth.account_locked`,
  `auth.portal_denied`, `auth.user_created`, `auth.password_changed`,
  `auth.user_deactivated` / `auth.user_activated`, `authz.denied` (role check
  failed, from `require_role`), `student.deleted`, `student.bulk_imported`,
  `queue.deleted`, `security.rate_limited`. Add a `log_security_event` call
  when you add any new sensitive action.
  - `migrations/env.py` calls `fileConfig(..., disable_existing_loggers=False)`
    so running migrations in-process (tests) doesn't switch this logger off.
- JWT tokens (HS256, `ACCESS_TOKEN_EXPIRE_MINUTES`-minute expiry, default 30)
  via `app/core/security.py`, transported in an httpOnly `registrar_token`
  cookie — never in the response body or an `Authorization` header. See
  **Defense in Depth** below.
- Role-based access: `Admin` > `Registrar` > `Staff`
- Dependency injection: `get_current_active_user`, `require_role(UserRole.REGISTRAR)`
  (pass the *minimum* role a route needs — see **Principle of Least Astonishment**)

**Authorize every sensitive action on the server** — the UI hiding a button is
not a control.

- Every staff/admin mutation declares `Depends(require_role(...))`; read-only
  staff endpoints use `Depends(get_current_active_user)`. A new `@router`
  method without one of these is a bug unless it is deliberately public.
- Deliberately public endpoints: `POST /auth/login`, `GET /queues/active`,
  `GET /queues/{id}`, the display-board reads (`/tickets/queue/{id}/display`,
  `/tickets/now-serving-overview`, `/announcements/active`, `/media/active`),
  student self-service (`POST /students`, `GET /students/search`,
  `POST /tickets`, `GET /tickets/my-ticket`, `POST /tickets/{id}/cancel`,
  the `/appointments` booking/lookup/cancel routes).
- **Public student-flow endpoints that read or mutate one student's data must
  verify ownership** by requiring that student's 10-digit `student_id` and
  matching it against the row — never key on the internal numeric id, which is
  small and enumerable. Pattern: `service.cancel_ticket(id, student_number)` /
  `get_student_ticket(student_number)` / `appointment_service.cancel(id,
  student_number)`. A mismatch returns the same 404 as "not found" so
  existence isn't leaked.
- Public endpoints are rate-limited (`@limiter.limit(...)` + a `request:
  Request` param).

## Key Configuration

### Environment Variables (backend/.env.example)
```env
DATABASE_URL=postgresql://postgres:password@localhost/bsu_queue
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=your-secret-key-here
DEBUG=True
LOG_LEVEL=info
CAMPUS_NAME=Bulacan State University - Meneses Campus
```
`.env.example` sets `DEBUG=True` for local dev convenience, but the code
default (when a var is absent entirely, as in a bare production environment)
is `DEBUG=False` — see **Secure Defaults** above. Production deployments may
also set `INITIAL_ADMIN_USERNAME` / `INITIAL_ADMIN_PASSWORD` to bootstrap the
first admin account.

### Frontend Proxy (vite.config.js)
Proxies `/api` requests to `http://localhost:8000` during development.

## Database Migrations
- Alembic configured in `backend/alembic.ini`
- Initial migration: `migrations/versions/001_initial_migration.py`
- Models use SQLAlchemy 2.0 declarative style with `mapped_column`

## Queue Logic (Priority Handling)
- **Priorities**: Normal < Priority < Urgent
- **Student priority flags**: `is_graduating`, `is_scholar`, `is_varsity` → auto-assigned priority
- **Serve next ticket**: Ordered by priority (desc) then position (asc)
- **Wait time estimation**: Based on queue slot duration and position

## Input Validation

All request input is treated as untrusted and validated at the edge (Pydantic
models + FastAPI `Query`/`Path` params). Reject unexpected input with `422` —
never coerce or sanitize-then-accept. Constraints currently enforced:

| Model / param | Field | Constraint |
|---|---|---|
| `StudentBase` | `student_id` | `^\d{10}$` |
| | `first_name`, `last_name` | 1–50 chars, whitespace-stripped, non-blank |
| | `email` | `EmailStr` (also on `Student`/`StudentInDB`/`StudentPublic` responses) |
| | *(no `is_scholar`/`is_varsity`/`is_graduating` — see **Avoid Trusting User Input**)* | |
| `TicketBase` | `student_id`, `queue_id` | `> 0` |
| | `purpose` | ≤ 500 chars |
| `QueueBase` | `name` | 1–100 chars, non-blank |
| | `description` | ≤ 1000 chars |
| | `max_capacity` / `slot_duration_minutes` / `slot_capacity` / `booking_window_days` | bounded `ge`/`le` (see model) |
| | `ticket_letter` | single `A`–`Z` (validator) |
| `AppointmentCreate` | `student_id`, `queue_id` | `> 0` |
| | `purpose` | ≤ 500 chars |
| `AppointmentCheckInRequest` | `token` / `reference_code` | ≤ 64 / ≤ 20 chars |
| `UserBase` | `username` | 3–50 chars, `^[A-Za-z0-9_.-]+$` |
| | `full_name` | 1–100 chars |
| `UserCreate` / `PasswordChange` | `password` / `new_password` | 8–72 chars (72 = bcrypt limit) |
| `AnnouncementBase` | `text` | 1–500 chars, whitespace-stripped |
| `MediaItemBase` / `MediaItemUpdate` | `url` | ≤ 2048 chars; must start `http://`, `https://`, or `/api/uploads/media/` (blocks `javascript:`/`data:`/`file:` — rendered as `src` on the public display board) |
| Query params | `student_id` (search/lookup/cancel) | `^\d{10}$` |
| | `skip` / `limit` (student & queue lists) | `skip ≥ 0`; `limit` bounded (`1–100` students, `1–200` queues) |
| | `my-ticket` `student_id` / `queue_id` | `> 0` |
| | id path params (`get`/`update`/`delete` student, `cancel` appointment) | `> 0` |
| | appointment `search` `query` | 1–50 chars |

`EmailStr` requires the `email-validator` package (in `requirements.txt`).
Response models keep `EmailStr` too, so a malformed email reaching the DB by
any other route surfaces as a `500` rather than being served silently.

## Avoid Trusting User Input

Passing shape/type/length validation isn't the same as being safe to act on —
a field can be well-formed and still be a value the caller shouldn't be
trusted to set. One real case fixed here:

- **`is_scholar`/`is_varsity`/`is_graduating` are not on `StudentBase`
  anymore — only on `StudentCreate(StudentBase)`.** These three flags feed
  directly into `TicketService.calculate_priority()`
  (`is_graduating` → **URGENT**, `is_scholar`/`is_varsity` → **PRIORITY**,
  ahead of every `NORMAL` ticket). `POST /students` is the *public,
  unauthenticated* kiosk self-registration endpoint — until this fix, its
  request model included these flags with no verification, and the kiosk
  registration form (`QueuesView.vue`) literally had "Scholar" / "Varsity
  Athlete" / "Graduating Student" checkboxes anyone could tick before taking
  a ticket, self-escalating to the front of every queue. Fixed by splitting
  the model: `StudentBase` (identity/enrollment fields only) is what the
  public endpoint accepts — sending the flags there is a `422`, not a
  silently-ignored claim. `StudentCreate` adds the three flags back for
  trusted callers only: the registrar-gated `PATCH /students/{id}` and the
  admin-only `POST /students/bulk-import`. `StudentService.create_student`
  reads them via `getattr(student_data, "is_scholar", False)` etc., so a
  caller passing bare `StudentBase` (no such attribute at all) always gets
  `False` — never a value it tried to supply.
  - The admin "Add Student" UI (`StudentManagementView.vue`) still needs to
    set these flags for a legitimately-verified new student in one click:
    `stores/queue.js`'s `createStudent` action does `POST /students` without
    the flags, then a follow-up `PATCH /students/{id}` (registrar-gated) if
    any flag was requested — two backend calls, one admin click.
  - Test coverage: `tests/test_student_priority_trust.py` (public register
    rejects the flags with 422; a public register without them defaults to
    `False`; registrar can set them via PATCH; staff — below registrar — is
    403'd from that route).
- When adding a new field that feeds a privilege, priority, or trust
  decision anywhere in the app, ask which endpoints can set it and whether
  every one of those callers is actually authorized to make that call before
  wiring it into the same model a public endpoint accepts.

## Error Handling

- **Unhandled exceptions never reach the client.** `app/main.py` registers a
  catch-all `add_exception_handler(Exception, ...)`: it logs the real
  exception with its full traceback server-side on the `bsu.app` logger (INFO
  level `bsu.security` is for security events specifically — this is a
  separate, ERROR-level logger for bugs) and returns a generic
  `{"detail": "An unexpected error occurred. Please try again later."}` 500 —
  never the exception type, message, or stack trace. Without this, an
  uncaught exception (e.g. a `ValueError`-only `except` block letting an
  unexpected `IntegrityError` or similar through) fell through to Starlette's
  default plain-text 500, which is inconsistent with the API's `{"detail":
  ...}` shape and untracked in any log.
- **Validation-error responses never echo sensitive field values back.**
  `app/main.py` also overrides FastAPI's default `RequestValidationError`
  handler to strip Pydantic's `"input"` key from every error entry before
  returning it. Pydantic v2 includes the client's raw rejected value in
  `"input"` by default — for most fields (a malformed `student_id`) that's
  harmless, but for `UserCreate.password` / `PasswordChange.new_password` /
  `PasswordChange.current_password` (length-constrained fields on a JSON
  body), a too-short or too-long password would otherwise be reflected
  verbatim in the 422 response body. Stripped globally rather than
  allowlisting field names, so any future sensitive field is covered
  automatically.
- Deliberate `except ValueError as e: raise HTTPException(400, detail=str(e))`
  conversions in `app/api/{queues,students,tickets,appointments}.py` are
  fine as-is — every `ValueError` they catch is raised by our own service
  layer with a hand-written, non-sensitive message (e.g. "Queue not found",
  "That time slot has already passed today"). This pattern is safe *only*
  because those call sites raise `ValueError` deliberately for expected
  failure cases — don't extend it to wrap arbitrary/unexpected exceptions.
- The frontend's Pinia store (`stores/queue.js`) already only ever reads
  `err.response?.data?.detail`, falling back to a hardcoded generic string
  per action when `detail` is absent (e.g. a non-JSON error body) — no
  frontend change was needed for this principle.

## Secure Defaults

- **`Settings.DEBUG` defaults to `False`** (`app/core/config.py`). `DEBUG` is
  the master switch for docs exposure, the relaxed CSP, and HSTS (see
  Deployment Hardening below) — an operator who forgets to set it in a
  production environment now gets the locked-down posture, not the permissive
  dev one. Local dev is unaffected: `backend/.env` (via `dev.ps1`'s template)
  and the test `.env` both set `DEBUG=True` explicitly.
- **`SECRET_KEY` fails fast if left at its placeholder value in production.**
  `app/core/config.py` raises `RuntimeError` at import time if
  `SECRET_KEY == "your-secret-key-here"` (the shipped default) while
  `DEBUG=False` — otherwise every JWT would be signed with a secret anyone
  can read in this public repo. Not enforced when `DEBUG=True`, so local dev
  can leave `SECRET_KEY` unset.
- **No hardcoded demo credentials in production.** `app/core/init_db.py`'s
  `seed_initial_data()` only creates the three demo accounts
  (`admin`/`admin123`, `registrar`/`registrar123`, `staff`/`staff123`) when
  `settings.DEBUG` is `True`. This matters because `start.sh` (the production
  container entrypoint) runs this seeder unconditionally on every boot — a
  well-known default admin password was previously a standing backdoor into
  any real deployment. For production, set `INITIAL_ADMIN_USERNAME` +
  `INITIAL_ADMIN_PASSWORD` (≥ 8 chars, checked before use) to have the
  seeder create exactly one admin account from those env vars instead; if
  neither DEBUG nor those vars are set, no admin account is created at all
  and the seeder logs that one must be added manually.
- Queue and sample-student seeding (`Enrollment`, `Document Request`, …,
  `Juan Dela Cruz` et al.) is unconditional — it's placeholder business data,
  not a credential, so it isn't gated by `DEBUG`.

## Defense in Depth

- **Staff auth uses an httpOnly cookie, not `localStorage` + `Authorization`
  header.** `POST /api/auth/login` sets the JWT via `Set-Cookie:
  registrar_token=…; HttpOnly; SameSite=Strict; Max-Age=<ACCESS_TOKEN_EXPIRE_
  MINUTES*60>; Path=/` (`Secure` added too when `DEBUG=False` — see below) and
  returns the `User` body, never the token; `POST /api/auth/logout` clears it
  server-side via `Response.delete_cookie`. The JWT itself, its algorithm, and
  its expiry are unchanged — only the transport. This closes a real class of
  attack this app didn't have an incident for, but was flagged as a standing
  risk: `localStorage` is readable by any JavaScript on the page, so a single
  successful XSS bug (anywhere in the app or a dependency) could previously
  exfiltrate a staff session outright; an httpOnly cookie can't be read by
  injected script at all, adding a second, independent barrier behind the CSP
  that already tries to stop the script from running in the first place — the
  essence of defense in depth: one control failing (XSS bypassing CSP)
  shouldn't automatically mean full account compromise.
  - **`SameSite=Strict` is the CSRF defense**, not a double-submit token. This
    app is same-origin (frontend and API share an origin behind the platform
    proxy/nginx, per **HTTPS everywhere**) with no legitimate cross-site
    request pattern, so `SameSite=Strict` alone means a cross-site page's
    request never carries the cookie — a complete mitigation for this app's
    shape, not a partial one. Revisit if the deployment ever becomes
    cross-origin/cross-subdomain.
  - **`Secure` is gated on `not settings.DEBUG`**, matching the existing
    HSTS/`upgrade-insecure-requests` convention (see **HTTPS everywhere**) —
    local dev and the pytest suite run over plain `http`, where a `Secure`
    cookie would simply never be sent/stored.
  - `get_current_user` (`app/core/security.py`) reads the cookie via
    `get_token_from_cookie` (401 if absent) instead of
    `OAuth2PasswordBearer` — `oauth2_scheme` and the now-dead `Token`
    response model were removed. A side effect: the DEBUG-only `/docs`
    Swagger UI no longer has a one-click "Authorize" button; exercise
    authenticated routes through the real frontend or a cookie-jar-aware
    client instead.
  - Frontend: `stores/queue.js`'s axios instance sets `withCredentials: true`
    and no longer reads/writes any token; `isAuthenticated` is
    `!!currentUser`, resolved via `GET /auth/me` (see `router/index.js`'s
    `requiresAuth` guard) since an httpOnly cookie can't be read by frontend
    JS the way a `localStorage` flag could. The two direct-`axios` call sites
    in `QueueManagementView.vue` (booking/queue settings) also set
    `withCredentials: true` instead of manually attaching a bearer header.
- **Brute-force login protection is two independent layers**, not one:
  `@limiter.limit("5/minute")` per-IP (slowapi) *and* the per-account
  `failed_login_attempts`/`locked_until` lockout (see **Limit failed login
  attempts** in Authentication & Authorization) — an attacker rotating IPs
  doesn't bypass the account lock, and one blocked IP doesn't stop a
  different attacker from trying a different account.
- **SQL injection has two independent layers**: the ORM-only rule (bound
  parameters by construction) *and* `escape_like` for `LIKE` wildcards (see
  **Database Access & SQL Safety**) — either one failing to be followed in a
  future change doesn't automatically mean an injectable query, since the
  other layer (parameterization) still holds.

## Keep Security Simple

- **One `get_db` dependency, not two.** `app/core/security.py` used to define
  its own byte-for-byte copy of `app/core/database.py`'s `get_db()` — the
  same open/yield/close session logic, duplicated. Every API route already
  imported the one in `database.py`; only `get_current_user` and the test
  `client` fixture (which had to override *both* copies) touched the
  duplicate. `security.py` now imports `get_db` from `.database` instead of
  redefining it. Two parallel definitions of a security-relevant dependency
  is exactly the kind of complexity this principle targets — a future change
  to session handling could get applied to one copy and not the other, and
  nothing would catch the drift until it caused a real bug.
- **`User.model_validate(user)`, not a hand-copied field list.**
  `get_current_user` (`app/core/security.py`) and `login`/`register_user`/
  `list_users` (`app/api/auth.py`) each used to manually copy 6–7 fields
  from a `UserDB` row into a `User` model by hand — and three of the four
  additionally did an unnecessary manual enum conversion
  (`UserRoleModel(user.role.value)`) that the fourth site didn't bother
  with. `User` already has `from_attributes=True` configured (needed for
  every other read path), so `User.model_validate(user)` does the same
  mapping in one line, correctly and consistently. Four inconsistent
  hand-written copies of the same mapping in authentication code is the
  kind of place a future field addition (e.g. a new `User` attribute) is
  most likely to get updated in three places and missed in the fourth.

## Database Access & SQL Safety

- **ORM only.** All runtime DB access goes through the SQLAlchemy ORM query
  builder (`.filter(Model.col == value)`, `.ilike(...)`), which sends values as
  bound parameters — SQL text and user data stay separated. Do not add
  `cursor.execute`, string-formatted queries, or `text()` with f-strings.
- If a raw statement is genuinely unavoidable, use bound params:
  `db.execute(text("... WHERE x = :x"), {"x": value})` — never an f-string.
- **LIKE searches** must escape user wildcards:
  `.ilike(f"%{escape_like(term)}%", escape=LIKE_ESCAPE)` from
  `app/services/search_utils.py`. Used by `student_service.search_students`
  and `appointment_service.search`.
- **No SQL by string concatenation / f-string**, anywhere — including data
  migrations. Existing data migrations use
  `op.execute(sa.text("... :x").bindparams(x=value))`; follow that form.
  The only interpolation that remains is SQL *identifiers* (a database or
  table name in `tests/conftest.py`) which cannot be bind parameters and are
  hardcoded constants / schema metadata, never user input.

## Deployment Hardening

- **Containers run as non-root.** `backend/Dockerfile` creates `appuser`
  (uid 1000) and drops to it before `CMD`; the `worker` service reuses that
  image so Celery is unprivileged too. `frontend/Dockerfile` (nginx) already
  runs workers as `nginx`.
- `db` and `redis` are **not** published to the host in `docker-compose.yml` —
  only `backend`/`worker` reach them over the internal compose network. Add a
  `ports:` mapping back temporarily if you need a local client.
- Interactive API docs (`/docs`, `/redoc`, `/openapi.json`) are served only
  when `DEBUG=True`.
- **Secure HTTP headers** are set in two places, by design:
  - `app/main.py` middleware → every API / static response:
    `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy`,
    `Cross-Origin-Opener-Policy`, `Cross-Origin-Resource-Policy: same-site`,
    a locked-down `Content-Security-Policy: default-src 'none'; …` (relaxed
    only for the DEBUG-only docs routes), `Server: api`, and HSTS when
    `DEBUG=False`.
  - `frontend/nginx.conf` `location /` → the SPA document and assets: the same
    baseline plus a real `Content-Security-Policy` (`default-src 'self'`,
    `script-src 'self'`, `style-src` adds `'unsafe-inline'` + Google Fonts,
    `img-src 'self' data: https:`, `frame-ancestors 'none'`, …),
    `Permissions-Policy` (camera allowed for QR check-in, everything else
    denied), HSTS, and `server_tokens off`.
  - If you add an off-origin dependency (font host, CDN, analytics), the CSP in
    `nginx.conf` must be widened for it or the browser will block it.
- **HTTPS everywhere.** TLS is terminated by the platform proxy in front of the
  containers; both apps sit behind it on plain HTTP internally.
  - `frontend/nginx.conf` 301-redirects any request whose `X-Forwarded-Proto`
    is `http` to `https` (no-op in local compose, where that header is absent).
  - `start.sh` runs uvicorn with `--proxy-headers --forwarded-allow-ips="*"`
    so `request.url.scheme` reflects the external HTTPS.
  - `app/main.py` sends `Strict-Transport-Security` (1 year, includeSubDomains)
    and `Content-Security-Policy: upgrade-insecure-requests` **when
    `DEBUG=False`** — never in local http dev.
  - Media item `url`s must be `https://` or the local `/api/uploads/media/`
    path (`app/models/media.py`); plain `http://` is rejected as future mixed
    content on the HTTPS display board.
  - In production `.env`, `ALLOWED_ORIGINS` must list `https://` origins only.
  - The frontend API client uses a relative `/api` base URL, so it inherits
    the page's scheme — keep it that way, never hardcode a host.

## Dependency Hygiene

- **Dependabot** (`.github/dependabot.yml`) opens weekly PRs for `pip`, `npm`,
  `docker` (base images) and `github-actions`. Minor/patch bumps are grouped
  into one PR per ecosystem to cut noise.
- **CI gates** (`.github/workflows/ci.yml`) fail the build on a known-vulnerable
  dependency:
  - backend: `pip-audit --ignore-vuln PYSEC-2026-1325`
  - frontend: `npm audit --omit=dev --audit-level=high` (audits only what ships
    in the bundle)
- Run the same checks locally: `pip-audit` in `backend/`, `npm audit` in
  `frontend/`.
- **Known exceptions:**
  - `PYSEC-2026-1325` — timing side-channel in `ecdsa` (via `python-jose`), no
    upstream fix. Unreachable here: tokens are HS256 (HMAC), the ECDSA signing
    path is never called. The real fix is to move auth off `python-jose` to
    `PyJWT` — worth doing in its own PR.
  - `vite` / `esbuild` dev-server advisories — build tooling only
    (`devDependencies`), not in the deployed app. The vite 5→8 major bump is
    left for a dedicated Dependabot PR so it can be tested in isolation.

## Software Supply Chain

- **`backend/requirements.txt` pins every dependency to an exact `==` version**
  (no bare `>=` floors). A floor-only range means a fresh `pip install -r
  requirements.txt` — every CI run, every Docker build, every Render deploy —
  re-resolves to whatever is newest on PyPI *at that moment*, with zero review;
  an exact pin makes every install reproducible and means Dependabot (already
  configured, grouped minor/patch) is the only path a version ever changes,
  each via its own CI-gated PR. `frontend/package-lock.json` + `npm ci`
  (already used in both `frontend/Dockerfile` and CI) gives the frontend the
  same guarantee for its whole dependency tree, hashes included — no
  equivalent change was needed there.
- **`.github/workflows/ci.yml` pins third-party GitHub Actions to a commit SHA**,
  not a movable tag (`actions/checkout@11d5960a…  # v4.4.0`, etc.). A tag like
  `@v4` can be repointed — by a compromised maintainer account or a hijacked
  repo, as happened to `tj-actions/changed-files` in 2025 — and every workflow
  referencing it silently runs the new code with the job's full permissions
  and secrets on the next trigger. Dependabot's `github-actions` ecosystem
  (already configured) bumps these SHAs by PR when a new release ships.
- **Docker base images are pinned to an exact patch tag**, not a floating
  major/minor one: `python:3.11.16-slim` (`backend/Dockerfile`),
  `node:20.20.2-alpine` and `nginx:1.27.5-alpine` (`frontend/Dockerfile`) —
  previously `python:3.11-slim`, `node:20-alpine`, `nginx:1.27-alpine`. A
  floating tag can resolve to a different underlying image weeks apart with no
  record of what changed; Dependabot's `docker` ecosystem (already configured
  for both directories) needs an explicit version segment to track and PR
  bumps against, same as the pip/npm ecosystems above.

## Principle of Least Astonishment

- **`require_role()` (`app/core/security.py`) enforces an actual role
  hierarchy**, matching what this doc already claims ("Role-based access:
  Admin > Registrar > Staff") instead of silently being a flat allow-list.
  Call it with the *minimum* role a route needs — `require_role(UserRole.
  REGISTRAR)` permits Registrar and Admin, not just an exact match — rather
  than listing every permitted role. Before this fix the mechanism was a bare
  `role not in allowed_roles` check: every existing call site happened to list
  roles correctly, but nothing stopped a future endpoint written as
  `require_role(UserRole.REGISTRAR)` alone (trusting the documented hierarchy)
  from silently locking out Admins — the mechanism didn't match the promise.
- **Every request-body Pydantic model sets `extra="forbid"`** (`StudentBase`,
  `QueueBase`/`QueueBookingSettings`/`QueueSettingsUpdate`, `TicketBase`,
  `UserBase`/`PasswordChange`, `AnnouncementBase`/`AnnouncementUpdate`,
  `MediaItemBase`/`MediaItemUpdate`, `AppointmentCreate`/
  `AppointmentCheckInRequest`). Pydantic v2's default is to silently *ignore*
  unexpected JSON fields rather than reject them — surprising to a caller who
  sends a field expecting it to do something, and inconsistent with this doc's
  own **Input Validation** rule ("reject unexpected input with 422 — never
  coerce or sanitize-then-accept"). Response-only models (`*Public`, and
  read models built with `from_attributes=True` from an ORM row) don't need
  this — there's no untrusted caller-supplied dict to police there.

## Frontend State (Pinia)
- `stores/queue.js` - Manages queues, tickets, and display data

## Development Notes

### Adding New Queue Types
1. Add to `QueueDBType` enum in `app/db_models.py`
2. Add to `QueueType` enum in `app/models/queue.py`
3. Create migration: `alembic revision --autogenerate -m "add queue type"`

### Adding API Endpoints
1. Create Pydantic models in `app/models/` — constrain every field (type, length,
   format, allowed values); see **Input Validation** above
2. Add service methods in `app/services/`
3. Create router in `app/api/` — bound `Query`/`Path` params (`ge`/`le`/`gt`,
   `pattern`, `max_length`)
4. Include router in `app/api/router.py`

### Running Tests
No test framework currently configured. Consider adding pytest for backend and Vitest for frontend.

### Common Issues
- **Database connection**: Ensure PostgreSQL is running and `DATABASE_URL` is correct
- **Redis connection**: Required for Celery worker; check `REDIS_URL`
- **Migrations**: Run `alembic upgrade head` after model changes
- **Frontend API calls**: Use relative `/api` paths (proxied by Vite in dev)