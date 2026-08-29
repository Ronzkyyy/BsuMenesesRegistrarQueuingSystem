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
- JWT tokens (HS256, 30 min expiry) via `app/core/security.py`
- Role-based access: `Admin` > `Registrar` > `Staff`
- Dependency injection: `get_current_active_user`, `require_role(UserRole.ADMIN, UserRole.REGISTRAR)`

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
- Alembic migrations that only interpolate hardcoded constants into
  `op.execute()` are acceptable, but new migrations touching row data should
  parameterize via `op.get_bind().execute(text(...), {...})`.

## Deployment Hardening

- **Containers run as non-root.** `backend/Dockerfile` creates `appuser`
  (uid 1000) and drops to it before `CMD`; the `worker` service reuses that
  image so Celery is unprivileged too. `frontend/Dockerfile` (nginx) already
  runs workers as `nginx`.
- `db` and `redis` are **not** published to the host in `docker-compose.yml` —
  only `backend`/`worker` reach them over the internal compose network. Add a
  `ports:` mapping back temporarily if you need a local client.
- Interactive API docs (`/docs`, `/redoc`, `/openapi.json`) are served only
  when `DEBUG=True`; security headers are set by middleware in `app/main.py`.

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