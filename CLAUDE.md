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
- JWT tokens (HS256, 30 min expiry) via `app/core/security.py`
- Role-based access: `Admin` > `Registrar` > `Staff`
- Dependency injection: `get_current_active_user`, `require_role(UserRole.ADMIN, UserRole.REGISTRAR)`

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