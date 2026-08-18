# Appointment System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a student book a future time slot for a registrar service from their own device, receive a QR code for it, and have registrar staff scan that QR at the counter to automatically create a normal queue ticket for them.

**Architecture:** A new `appointments` table + `AppointmentService` sits alongside the existing queue/ticket domain. Bookable time slots are computed on the fly from new `Queue` settings (`operating_start_time`, `operating_end_time`, `slot_capacity`, `booking_window_days`, `booking_enabled`) rather than stored as their own rows. The QR encodes a single opaque random token (`secrets.token_urlsafe(32)`), stored on the appointment and validated with a live database round-trip at scan time - there is no offline verification path. Check-in atomically flips the appointment's status (`booked → checked_in`) and then calls the existing, unmodified `TicketService.create_ticket` to produce a normal ticket, so the entire existing ticket/priority/counter/display pipeline is reused with zero changes.

**Tech Stack:** Python FastAPI + SQLAlchemy + Alembic (backend), Vue 3 + Pinia + `qrcode` + `qr-scanner` (frontend, two new npm dependencies). No automated test framework is configured for either side (per `CLAUDE.md`) - verification is manual, against the real running stack (backend + PostgreSQL + Celery + frontend dev server), per this project's established convention (see `docs/superpowers/plans/2026-08-03-student-list-pagination.md`).

## Global Constraints

- QR token is an opaque random string (`secrets.token_urlsafe(32)`) validated only via a live server round-trip - no offline/signed-token verification path.
- Bookable slots are computed from `Queue` fields at request time - no dedicated slot table.
- Check-in must create the ticket by calling `TicketService.create_ticket` unmodified - do not change `ticket_service.py`.
- `qr_token` must never be included in any response after the initial booking response (`AppointmentBooked`) - every other appointment response uses the `Appointment` model, which omits it.
- No email/SMS delivery - booking confirmation is in-browser only; students re-view a booking via student ID + `reference_code`.
- A student may hold only one active (`booked`) appointment at a time; cancel-and-rebook only, no reschedule.
- `booking_enabled` defaults to `false` on every queue (existing and new) - the feature ships inert until explicitly turned on per queue.
- No automated test framework is configured - verify manually against the real running stack (backend on `:8000`, frontend dev server on `:5173`, real PostgreSQL).
- All file paths below are relative to the repo root (`thesis project/`), i.e. prefixed with `bsu-registrar-queue/`.

---

### Task 1: Database — `appointments` table and `Queue` booking columns

**Files:**
- Modify: `bsu-registrar-queue/backend/app/db_models.py`
- Create: `bsu-registrar-queue/backend/migrations/versions/b7c8d9e0f1a2_add_appointments.py`

**Interfaces:**
- Consumes: existing `QueueDB`, `StudentDB`, `TicketDB`, `UserDB` models - no changes to those classes' existing columns.
- Produces: `AppointmentDB` ORM model and `AppointmentDBStatus` enum (`BOOKED`, `CHECKED_IN`, `CANCELLED`, `EXPIRED`) with columns `id, reference_code, student_id, queue_id, appointment_date, slot_start_time, slot_end_time, purpose, qr_token, status, checked_in_at, checked_in_by, ticket_id, created_at, updated_at`. `QueueDB` gains `booking_enabled: bool`, `operating_start_time: time`, `operating_end_time: time`, `slot_capacity: int`, `booking_window_days: int`. Every later task depends on these exact names.

- [ ] **Step 1: Add `AppointmentDB` and extend `QueueDB` in `db_models.py`**

Change the import line at the top of `bsu-registrar-queue/backend/app/db_models.py`:

```python
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Enum, Text
```

to:

```python
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Enum, Text, Date, Time
from datetime import time
```

In the `QueueDB` class, add these columns right after `slot_duration_minutes = Column(Integer, default=30)` and before `current_ticket_number = Column(Integer, default=0)`:

```python
    booking_enabled = Column(Boolean, default=False, nullable=False)
    operating_start_time = Column(Time, default=time(8, 0), nullable=False)
    operating_end_time = Column(Time, default=time(17, 0), nullable=False)
    slot_capacity = Column(Integer, default=3, nullable=False)
    booking_window_days = Column(Integer, default=14, nullable=False)
```

At the end of the file, after the `AnnouncementDB` class, append:

```python


class AppointmentDBStatus(str, enum.Enum):
    BOOKED = "booked"
    CHECKED_IN = "checked_in"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class AppointmentDB(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    reference_code = Column(String(20), unique=True, index=True, nullable=False)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    queue_id = Column(Integer, ForeignKey("queues.id"), nullable=False)
    appointment_date = Column(Date, nullable=False)
    slot_start_time = Column(Time, nullable=False)
    slot_end_time = Column(Time, nullable=False)
    purpose = Column(Text)
    qr_token = Column(String(64), unique=True, index=True, nullable=False)
    status = Column(Enum(AppointmentDBStatus), default=AppointmentDBStatus.BOOKED, nullable=False)
    checked_in_at = Column(DateTime(timezone=True))
    checked_in_by = Column(Integer, ForeignKey("users.id"))
    ticket_id = Column(Integer, ForeignKey("tickets.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    student = relationship("StudentDB")
    queue = relationship("QueueDB")
```

- [ ] **Step 2: Write the Alembic migration**

Create `bsu-registrar-queue/backend/migrations/versions/b7c8d9e0f1a2_add_appointments.py`:

```python
"""add appointments table and queue booking settings

Revision ID: b7c8d9e0f1a2
Revises: a1b2c3d4e5f6
Create Date: 2026-08-18 00:00:00.000000

Adds the appointments table (QR-based booking, checked in at the registrar
counter to auto-create a queue ticket) and five new booking-config columns
on queues, all additive and defaulted so existing queues/rows are unaffected
until an admin explicitly enables booking on a given queue.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7c8d9e0f1a2'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('queues', sa.Column('booking_enabled', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    op.add_column('queues', sa.Column('operating_start_time', sa.Time(), nullable=False, server_default='08:00:00'))
    op.add_column('queues', sa.Column('operating_end_time', sa.Time(), nullable=False, server_default='17:00:00'))
    op.add_column('queues', sa.Column('slot_capacity', sa.Integer(), nullable=False, server_default='3'))
    op.add_column('queues', sa.Column('booking_window_days', sa.Integer(), nullable=False, server_default='14'))

    op.create_table(
        'appointments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('reference_code', sa.String(length=20), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('queue_id', sa.Integer(), nullable=False),
        sa.Column('appointment_date', sa.Date(), nullable=False),
        sa.Column('slot_start_time', sa.Time(), nullable=False),
        sa.Column('slot_end_time', sa.Time(), nullable=False),
        sa.Column('purpose', sa.Text(), nullable=True),
        sa.Column('qr_token', sa.String(length=64), nullable=False),
        sa.Column('status', sa.Enum('BOOKED', 'CHECKED_IN', 'CANCELLED', 'EXPIRED', name='appointmentdbstatus'), nullable=False),
        sa.Column('checked_in_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('checked_in_by', sa.Integer(), nullable=True),
        sa.Column('ticket_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['student_id'], ['students.id']),
        sa.ForeignKeyConstraint(['queue_id'], ['queues.id']),
        sa.ForeignKeyConstraint(['checked_in_by'], ['users.id']),
        sa.ForeignKeyConstraint(['ticket_id'], ['tickets.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('reference_code'),
        sa.UniqueConstraint('qr_token'),
    )
    op.create_index(op.f('ix_appointments_id'), 'appointments', ['id'], unique=False)
    op.create_index(op.f('ix_appointments_reference_code'), 'appointments', ['reference_code'], unique=True)
    op.create_index(op.f('ix_appointments_qr_token'), 'appointments', ['qr_token'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_appointments_qr_token'), table_name='appointments')
    op.drop_index(op.f('ix_appointments_reference_code'), table_name='appointments')
    op.drop_index(op.f('ix_appointments_id'), table_name='appointments')
    op.drop_table('appointments')
    op.execute('DROP TYPE IF EXISTS appointmentdbstatus')

    op.drop_column('queues', 'booking_window_days')
    op.drop_column('queues', 'slot_capacity')
    op.drop_column('queues', 'operating_end_time')
    op.drop_column('queues', 'operating_start_time')
    op.drop_column('queues', 'booking_enabled')
```

- [ ] **Step 3: Run the migration against the real dev database**

```bash
cd bsu-registrar-queue/backend
source .venv/Scripts/activate
alembic current
alembic upgrade head
alembic current
```

Expected: first `alembic current` shows `a1b2c3d4e5f6 (head)`, the upgrade runs with no errors, and the second `alembic current` shows `b7c8d9e0f1a2 (head)`.

- [ ] **Step 4: Verify the new table and columns exist, then round-trip the downgrade/upgrade**

```bash
python -c "
from sqlalchemy import inspect
from app.core.database import engine

inspector = inspect(engine)
assert 'appointments' in inspector.get_table_names(), 'appointments table missing'
columns = {c['name'] for c in inspector.get_columns('appointments')}
expected = {'id','reference_code','student_id','queue_id','appointment_date','slot_start_time','slot_end_time','purpose','qr_token','status','checked_in_at','checked_in_by','ticket_id','created_at','updated_at'}
assert expected.issubset(columns), f'missing columns: {expected - columns}'

queue_columns = {c['name'] for c in inspector.get_columns('queues')}
expected_queue = {'booking_enabled','operating_start_time','operating_end_time','slot_capacity','booking_window_days'}
assert expected_queue.issubset(queue_columns), f'missing queue columns: {expected_queue - queue_columns}'
print('OK - appointments table and queue booking columns present')
"
```

Expected: `OK - appointments table and queue booking columns present`, no assertion errors.

Then verify `alembic downgrade -1` cleanly reverses it and `alembic upgrade head` restores it:

```bash
alembic downgrade -1
alembic current
alembic upgrade head
alembic current
```

Expected: downgrade succeeds with no errors, shows `a1b2c3d4e5f6 (head)`, then upgrade restores `b7c8d9e0f1a2 (head)`.

- [ ] **Step 5: Commit**

```bash
git add bsu-registrar-queue/backend/app/db_models.py bsu-registrar-queue/backend/migrations/versions/b7c8d9e0f1a2_add_appointments.py
git commit -m "feat(appointments): add appointments table and queue booking-config columns"
```

---

### Task 2: Backend — Queue booking-settings schema, service, and endpoint

**Files:**
- Modify: `bsu-registrar-queue/backend/app/models/queue.py`
- Modify: `bsu-registrar-queue/backend/app/services/queue_service.py`
- Modify: `bsu-registrar-queue/backend/app/api/queues.py`

**Interfaces:**
- Consumes: `QueueDB` columns from Task 1 (`booking_enabled`, `operating_start_time`, `operating_end_time`, `slot_capacity`, `booking_window_days`).
- Produces: `Queue` response model now includes the 5 booking fields (Task 3's `AppointmentService` reads these off the `QueueDB` row directly, not through this Pydantic model, but the frontend Queue Management UI in Task 7 reads them from this response). New `QueueBookingSettings` request model and `PATCH /api/queues/{queue_id}/booking-settings` endpoint (admin/registrar only) for enabling/configuring booking on an existing queue.

- [ ] **Step 1: Extend `QueueBase` and add `QueueBookingSettings`**

In `bsu-registrar-queue/backend/app/models/queue.py`, change the import line:

```python
from datetime import datetime
```

to:

```python
from datetime import datetime, time
```

Replace the `QueueBase` class:

```python
class QueueBase(BaseModel):
    name: str
    queue_type: QueueType
    ticket_letter: str = Field(min_length=1, max_length=1)
    description: Optional[str] = None
    allow_priority: bool = True
    max_capacity: int = Field(default=50, ge=1, le=200)
    slot_duration_minutes: int = Field(default=30, ge=5, le=120)

    @field_validator('ticket_letter')
    @classmethod
    def validate_ticket_letter(cls, v: str) -> str:
        v = v.upper()
        if v not in string.ascii_uppercase:
            raise ValueError('Ticket letter must be a single letter A-Z')
        return v
```

with:

```python
class QueueBase(BaseModel):
    name: str
    queue_type: QueueType
    ticket_letter: str = Field(min_length=1, max_length=1)
    description: Optional[str] = None
    allow_priority: bool = True
    max_capacity: int = Field(default=50, ge=1, le=200)
    slot_duration_minutes: int = Field(default=30, ge=5, le=120)
    booking_enabled: bool = False
    operating_start_time: time = time(8, 0)
    operating_end_time: time = time(17, 0)
    slot_capacity: int = Field(default=3, ge=1, le=50)
    booking_window_days: int = Field(default=14, ge=1, le=90)

    @field_validator('ticket_letter')
    @classmethod
    def validate_ticket_letter(cls, v: str) -> str:
        v = v.upper()
        if v not in string.ascii_uppercase:
            raise ValueError('Ticket letter must be a single letter A-Z')
        return v
```

At the end of the file, after the `QueueInDB` class, append:

```python


class QueueBookingSettings(BaseModel):
    booking_enabled: bool
    operating_start_time: time
    operating_end_time: time
    slot_capacity: int = Field(ge=1, le=50)
    booking_window_days: int = Field(ge=1, le=90)
```

- [ ] **Step 2: Wire the new fields through `QueueService`**

In `bsu-registrar-queue/backend/app/services/queue_service.py`, replace the `create_queue` method:

```python
    def create_queue(self, queue_data: QueueCreate) -> Queue:
        """Create a new service queue"""
        # ticket_letter is already uppercased by QueueBase's validator, and
        # every existing row's letter is uppercase too (backfilled or
        # created through this same validated path) - a plain equality
        # check is enough, no case-folding needed here.
        existing = self.db.query(QueueDB).filter(
            QueueDB.ticket_letter == queue_data.ticket_letter
        ).first()
        if existing:
            raise ValueError(f"Ticket letter '{queue_data.ticket_letter}' is already used by another queue")

        db_queue = QueueDB(
            name=queue_data.name,
            queue_type=QueueDBType(queue_data.queue_type.value),
            ticket_letter=queue_data.ticket_letter,
            description=queue_data.description,
            allow_priority=queue_data.allow_priority,
            max_capacity=queue_data.max_capacity,
            slot_duration_minutes=queue_data.slot_duration_minutes,
            status=QueueDBStatus.ACTIVE,
            current_ticket_number=0,
        )
        self.db.add(db_queue)
        self.db.commit()
        self.db.refresh(db_queue)
        return self._to_queue(db_queue)
```

with:

```python
    def create_queue(self, queue_data: QueueCreate) -> Queue:
        """Create a new service queue"""
        # ticket_letter is already uppercased by QueueBase's validator, and
        # every existing row's letter is uppercase too (backfilled or
        # created through this same validated path) - a plain equality
        # check is enough, no case-folding needed here.
        existing = self.db.query(QueueDB).filter(
            QueueDB.ticket_letter == queue_data.ticket_letter
        ).first()
        if existing:
            raise ValueError(f"Ticket letter '{queue_data.ticket_letter}' is already used by another queue")

        db_queue = QueueDB(
            name=queue_data.name,
            queue_type=QueueDBType(queue_data.queue_type.value),
            ticket_letter=queue_data.ticket_letter,
            description=queue_data.description,
            allow_priority=queue_data.allow_priority,
            max_capacity=queue_data.max_capacity,
            slot_duration_minutes=queue_data.slot_duration_minutes,
            status=QueueDBStatus.ACTIVE,
            current_ticket_number=0,
            booking_enabled=queue_data.booking_enabled,
            operating_start_time=queue_data.operating_start_time,
            operating_end_time=queue_data.operating_end_time,
            slot_capacity=queue_data.slot_capacity,
            booking_window_days=queue_data.booking_window_days,
        )
        self.db.add(db_queue)
        self.db.commit()
        self.db.refresh(db_queue)
        return self._to_queue(db_queue)

    def update_booking_settings(self, queue_id: int, settings) -> Optional[Queue]:
        """Enable/configure appointment booking on an existing queue (admin/registrar only)"""
        queue = self.db.query(QueueDB).filter(QueueDB.id == queue_id).first()
        if not queue:
            return None

        if settings.operating_start_time >= settings.operating_end_time:
            raise ValueError("operating_start_time must be before operating_end_time")

        queue.booking_enabled = settings.booking_enabled
        queue.operating_start_time = settings.operating_start_time
        queue.operating_end_time = settings.operating_end_time
        queue.slot_capacity = settings.slot_capacity
        queue.booking_window_days = settings.booking_window_days
        queue.updated_at = datetime.now()
        self.db.commit()
        self.db.refresh(queue)
        return self._to_queue(queue)
```

Replace the `_to_queue` method:

```python
    def _to_queue(self, db_queue: QueueDB) -> Queue:
        """Convert DB model to Pydantic model"""
        return Queue(
            id=db_queue.id,
            name=db_queue.name,
            queue_type=QueueDBType(db_queue.queue_type.value),
            ticket_letter=db_queue.ticket_letter,
            description=db_queue.description,
            status=QueueDBStatus(db_queue.status.value),
            allow_priority=db_queue.allow_priority,
            max_capacity=db_queue.max_capacity,
            slot_duration_minutes=db_queue.slot_duration_minutes,
            current_ticket_number=db_queue.current_ticket_number,
            created_at=db_queue.created_at,
            updated_at=db_queue.updated_at,
        )
```

with:

```python
    def _to_queue(self, db_queue: QueueDB) -> Queue:
        """Convert DB model to Pydantic model"""
        return Queue(
            id=db_queue.id,
            name=db_queue.name,
            queue_type=QueueDBType(db_queue.queue_type.value),
            ticket_letter=db_queue.ticket_letter,
            description=db_queue.description,
            status=QueueDBStatus(db_queue.status.value),
            allow_priority=db_queue.allow_priority,
            max_capacity=db_queue.max_capacity,
            slot_duration_minutes=db_queue.slot_duration_minutes,
            current_ticket_number=db_queue.current_ticket_number,
            created_at=db_queue.created_at,
            updated_at=db_queue.updated_at,
            booking_enabled=db_queue.booking_enabled,
            operating_start_time=db_queue.operating_start_time,
            operating_end_time=db_queue.operating_end_time,
            slot_capacity=db_queue.slot_capacity,
            booking_window_days=db_queue.booking_window_days,
        )
```

- [ ] **Step 3: Add the `PATCH /api/queues/{queue_id}/booking-settings` endpoint**

In `bsu-registrar-queue/backend/app/api/queues.py`, change the import line:

```python
from ..models.queue import Queue, QueueCreate, QueueStatus, QueueInDB
```

to:

```python
from ..models.queue import Queue, QueueCreate, QueueStatus, QueueInDB, QueueBookingSettings
```

Add this endpoint right after `update_queue_status`:

```python
@router.patch("/{queue_id}/booking-settings", response_model=Queue)
def update_booking_settings(
    queue_id: int,
    settings: QueueBookingSettings,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.REGISTRAR))
):
    """Enable/configure appointment booking for a queue (admin/registrar only)"""
    service = QueueService(db)
    try:
        queue = service.update_booking_settings(queue_id, settings)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not queue:
        raise HTTPException(status_code=404, detail="Queue not found")
    return queue
```

- [ ] **Step 4: Start the backend and verify against the real database**

```bash
cd bsu-registrar-queue/backend
source .venv/Scripts/activate
uvicorn app.main:app --reload
```

Expected: starts with no import errors.

In a second terminal:

```bash
python -c "
import urllib.request, urllib.parse, json

BASE = 'http://localhost:8000/api'
login_data = urllib.parse.urlencode({'username': 'admin', 'password': 'admin123'}).encode()
req = urllib.request.Request(f'{BASE}/auth/login', data=login_data, headers={'Content-Type': 'application/x-www-form-urlencoded'})
token = json.loads(urllib.request.urlopen(req, timeout=5).read())['access_token']
auth_headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

req = urllib.request.Request(f'{BASE}/queues', headers=auth_headers)
queues = json.loads(urllib.request.urlopen(req, timeout=5).read())
assert len(queues) > 0, 'expected existing seeded queues'
first = queues[0]
assert first['booking_enabled'] is False, f\"expected booking_enabled False by default, got {first['booking_enabled']}\"
assert first['slot_capacity'] == 3, f\"expected default slot_capacity 3, got {first['slot_capacity']}\"
print('Default booking fields OK on queue', first['id'])

settings = {
    'booking_enabled': True,
    'operating_start_time': '08:00:00',
    'operating_end_time': '16:00:00',
    'slot_capacity': 2,
    'booking_window_days': 7,
}
req = urllib.request.Request(f\"{BASE}/queues/{first['id']}/booking-settings\", data=json.dumps(settings).encode(), headers=auth_headers, method='PATCH')
updated = json.loads(urllib.request.urlopen(req, timeout=5).read())
assert updated['booking_enabled'] is True
assert updated['slot_capacity'] == 2
assert updated['booking_window_days'] == 7
print('OK - booking settings updated on queue', updated['id'])

# Revert so later tasks start from a known state
revert = {'booking_enabled': False, 'operating_start_time': '08:00:00', 'operating_end_time': '17:00:00', 'slot_capacity': 3, 'booking_window_days': 14}
req = urllib.request.Request(f\"{BASE}/queues/{first['id']}/booking-settings\", data=json.dumps(revert).encode(), headers=auth_headers, method='PATCH')
urllib.request.urlopen(req, timeout=5)
print('Reverted booking settings back to defaults')
"
```

Expected: prints `Default booking fields OK on queue <id>`, then `OK - booking settings updated on queue <id>`, then `Reverted booking settings back to defaults`, no assertion errors.

- [ ] **Step 5: Commit**

```bash
git add bsu-registrar-queue/backend/app/models/queue.py bsu-registrar-queue/backend/app/services/queue_service.py bsu-registrar-queue/backend/app/api/queues.py
git commit -m "feat(queues): add booking-settings schema, service method, and PATCH endpoint"
```

---

### Task 3: Backend — Appointment schemas + booking-side service (availability, create, lookup, cancel)

**Files:**
- Create: `bsu-registrar-queue/backend/app/models/appointment.py`
- Create: `bsu-registrar-queue/backend/app/services/appointment_service.py`

**Interfaces:**
- Consumes: `AppointmentDB`/`AppointmentDBStatus` (Task 1), `QueueDB`/`StudentDB` (existing).
- Produces: `AppointmentStatus`, `AppointmentCreate`, `Appointment`, `AppointmentBooked` (adds `qr_token`, booking-response-only), `SlotAvailability`, `AppointmentCheckInRequest` in `app/models/appointment.py`. `AppointmentService.__init__(self, db)`, `.get_availability(queue_id: int, target_date: date) -> List[SlotAvailability]`, `.create_appointment(data: AppointmentCreate) -> AppointmentBooked`, `.lookup(student_id_str: str, reference_code: str) -> Optional[Appointment]`, `.cancel(appointment_id: int, student_id_str: str) -> Optional[Appointment]` (raises `ValueError` if not cancellable). Task 4 adds `.search()`, `.check_in()`, `.expire_stale_appointments()` to the same class.

- [ ] **Step 1: Write `app/models/appointment.py`**

```python
"""
Appointment model for QR-based queue booking
"""
from datetime import date, datetime, time
from typing import List, Optional
from pydantic import BaseModel, Field
from enum import Enum


class AppointmentStatus(str, Enum):
    BOOKED = "booked"
    CHECKED_IN = "checked_in"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class AppointmentCreate(BaseModel):
    student_id: int
    queue_id: int
    appointment_date: date
    slot_start_time: time
    purpose: Optional[str] = None


class Appointment(BaseModel):
    id: int
    reference_code: str
    student_id: int
    queue_id: int
    appointment_date: date
    slot_start_time: time
    slot_end_time: time
    purpose: Optional[str] = None
    status: AppointmentStatus
    checked_in_at: Optional[datetime] = None
    ticket_id: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    queue_name: Optional[str] = None

    class Config:
        from_attributes = True


class AppointmentBooked(Appointment):
    """Returned only from the booking endpoint - the one time qr_token is exposed."""
    qr_token: str


class SlotAvailability(BaseModel):
    slot_start_time: time
    slot_end_time: time
    booked: int
    capacity: int
    is_full: bool


class AppointmentCheckInRequest(BaseModel):
    token: Optional[str] = None
    reference_code: Optional[str] = None
    force: bool = False
```

- [ ] **Step 2: Write `app/services/appointment_service.py` (availability, create, lookup, cancel)**

```python
"""
Appointment service - QR-based booking that checks in to create a queue ticket
"""
import secrets
from datetime import date, datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from typing import List, Optional

from ..db_models import AppointmentDB, AppointmentDBStatus, QueueDB, StudentDB
from ..models.appointment import (
    Appointment, AppointmentBooked, AppointmentCreate, AppointmentStatus, SlotAvailability
)


class AppointmentWindowError(Exception):
    """Raised when a check-in is attempted outside the appointment's window and not forced."""
    pass


# How far before/after a slot's start/end time a check-in is accepted without
# staff explicitly overriding via force=True.
GRACE_MINUTES_BEFORE = 30
GRACE_MINUTES_AFTER = 30

# How long past a slot's end time a still-BOOKED appointment is left alone
# before expire_stale_appointments marks it EXPIRED - gives a late walk-in a
# buffer beyond the check-in grace window before losing the slot for good.
EXPIRE_BUFFER_MINUTES = 60


class AppointmentService:
    def __init__(self, db: Session):
        self.db = db

    def get_availability(self, queue_id: int, target_date: date) -> List[SlotAvailability]:
        """Compute bookable slots for a queue/date from the queue's own settings"""
        queue = self.db.query(QueueDB).filter(QueueDB.id == queue_id).first()
        if not queue or not queue.booking_enabled:
            return []

        slots: List[SlotAvailability] = []
        delta = timedelta(minutes=queue.slot_duration_minutes)
        current = datetime.combine(target_date, queue.operating_start_time)
        day_end = datetime.combine(target_date, queue.operating_end_time)

        while current + delta <= day_end:
            slot_start = current.time()
            slot_end = (current + delta).time()
            booked = self.db.query(func.count(AppointmentDB.id)).filter(
                AppointmentDB.queue_id == queue_id,
                AppointmentDB.appointment_date == target_date,
                AppointmentDB.slot_start_time == slot_start,
                AppointmentDB.status == AppointmentDBStatus.BOOKED,
            ).scalar() or 0
            slots.append(SlotAvailability(
                slot_start_time=slot_start,
                slot_end_time=slot_end,
                booked=booked,
                capacity=queue.slot_capacity,
                is_full=booked >= queue.slot_capacity,
            ))
            current += delta

        return slots

    def create_appointment(self, data: AppointmentCreate) -> AppointmentBooked:
        """Book an appointment for a student in a computed slot"""
        student = self.db.query(StudentDB).filter(StudentDB.id == data.student_id).first()
        if not student:
            raise ValueError("Student not found")

        queue = self.db.query(QueueDB).filter(QueueDB.id == data.queue_id).first()
        if not queue or not queue.booking_enabled:
            raise ValueError("This service is not open for appointment booking")

        today = date.today()
        if data.appointment_date < today:
            raise ValueError("Cannot book an appointment in the past")
        if data.appointment_date > today + timedelta(days=queue.booking_window_days):
            raise ValueError(f"Appointments can only be booked up to {queue.booking_window_days} days in advance")

        existing = self.db.query(AppointmentDB).filter(
            AppointmentDB.student_id == data.student_id,
            AppointmentDB.status == AppointmentDBStatus.BOOKED,
        ).first()
        if existing:
            raise ValueError(
                f"You already have an active appointment ({existing.reference_code}) on "
                f"{existing.appointment_date.isoformat()}. Cancel it before booking another."
            )

        slot_delta = timedelta(minutes=queue.slot_duration_minutes)
        slot_start_dt = datetime.combine(data.appointment_date, data.slot_start_time)
        day_start = datetime.combine(data.appointment_date, queue.operating_start_time)
        day_end = datetime.combine(data.appointment_date, queue.operating_end_time)
        is_valid_slot = (
            slot_start_dt >= day_start
            and slot_start_dt + slot_delta <= day_end
            and (slot_start_dt - day_start) % slot_delta == timedelta(0)
        )
        if not is_valid_slot:
            raise ValueError("That time is not a valid slot for this service")

        booked_count = self.db.query(func.count(AppointmentDB.id)).filter(
            AppointmentDB.queue_id == data.queue_id,
            AppointmentDB.appointment_date == data.appointment_date,
            AppointmentDB.slot_start_time == data.slot_start_time,
            AppointmentDB.status == AppointmentDBStatus.BOOKED,
        ).scalar() or 0
        if booked_count >= queue.slot_capacity:
            raise ValueError("That time slot is fully booked. Please choose another.")

        appointment = AppointmentDB(
            reference_code=self._generate_reference_code(),
            student_id=data.student_id,
            queue_id=data.queue_id,
            appointment_date=data.appointment_date,
            slot_start_time=data.slot_start_time,
            slot_end_time=(slot_start_dt + slot_delta).time(),
            purpose=data.purpose,
            qr_token=secrets.token_urlsafe(32),
            status=AppointmentDBStatus.BOOKED,
        )
        self.db.add(appointment)
        self.db.commit()
        self.db.refresh(appointment)
        return self._to_appointment(appointment, queue, include_token=True)

    def lookup(self, student_id_str: str, reference_code: str) -> Optional[Appointment]:
        """Student re-views a booking by student ID + reference code"""
        student = self.db.query(StudentDB).filter(StudentDB.student_id == student_id_str).first()
        if not student:
            return None
        appointment = self.db.query(AppointmentDB).filter(
            AppointmentDB.student_id == student.id,
            AppointmentDB.reference_code == reference_code.strip().upper(),
        ).first()
        if not appointment:
            return None
        queue = self.db.query(QueueDB).filter(QueueDB.id == appointment.queue_id).first()
        return self._to_appointment(appointment, queue)

    def cancel(self, appointment_id: int, student_id_str: str) -> Optional[Appointment]:
        """Student cancels their own still-booked appointment"""
        student = self.db.query(StudentDB).filter(StudentDB.student_id == student_id_str).first()
        if not student:
            return None
        appointment = self.db.query(AppointmentDB).filter(
            AppointmentDB.id == appointment_id,
            AppointmentDB.student_id == student.id,
        ).first()
        if not appointment:
            return None
        if appointment.status != AppointmentDBStatus.BOOKED:
            raise ValueError(f"This appointment cannot be cancelled (status: {appointment.status.value}).")

        appointment.status = AppointmentDBStatus.CANCELLED
        appointment.updated_at = datetime.now()
        self.db.commit()
        self.db.refresh(appointment)
        queue = self.db.query(QueueDB).filter(QueueDB.id == appointment.queue_id).first()
        return self._to_appointment(appointment, queue)

    def _generate_reference_code(self) -> str:
        for _ in range(10):
            candidate = f"APT-{secrets.randbelow(1_000_000):06d}"
            exists = self.db.query(AppointmentDB).filter(AppointmentDB.reference_code == candidate).first()
            if not exists:
                return candidate
        raise RuntimeError("Could not generate a unique appointment reference code")

    def _to_appointment(self, db_appt: AppointmentDB, queue: Optional[QueueDB] = None, include_token: bool = False):
        """Convert DB model to Pydantic model"""
        data = dict(
            id=db_appt.id,
            reference_code=db_appt.reference_code,
            student_id=db_appt.student_id,
            queue_id=db_appt.queue_id,
            appointment_date=db_appt.appointment_date,
            slot_start_time=db_appt.slot_start_time,
            slot_end_time=db_appt.slot_end_time,
            purpose=db_appt.purpose,
            status=AppointmentStatus(db_appt.status.value),
            checked_in_at=db_appt.checked_in_at,
            ticket_id=db_appt.ticket_id,
            created_at=db_appt.created_at,
            updated_at=db_appt.updated_at,
            queue_name=queue.name if queue else None,
        )
        if include_token:
            return AppointmentBooked(**data, qr_token=db_appt.qr_token)
        return Appointment(**data)
```

- [ ] **Step 3: Register `AppointmentService` in the services package**

Replace `bsu-registrar-queue/backend/app/services/__init__.py`:

```python
from .queue_service import QueueService
from .ticket_service import TicketService
from .student_service import StudentService
from .media_service import MediaService
from .announcement_service import AnnouncementService

__all__ = ["QueueService", "TicketService", "StudentService", "MediaService", "AnnouncementService"]
```

with:

```python
from .queue_service import QueueService
from .ticket_service import TicketService
from .student_service import StudentService
from .media_service import MediaService
from .announcement_service import AnnouncementService
from .appointment_service import AppointmentService, AppointmentWindowError

__all__ = [
    "QueueService", "TicketService", "StudentService", "MediaService", "AnnouncementService",
    "AppointmentService", "AppointmentWindowError",
]
```

- [ ] **Step 4: Verify availability/create/lookup/cancel directly against the real database**

With the backend NOT necessarily running (this test calls the service layer in-process against the real dev DB), run:

```bash
cd bsu-registrar-queue/backend
source .venv/Scripts/activate
python -c "
from datetime import date, timedelta
from app.core.database import SessionLocal
from app.db_models import QueueDB
from app.models.appointment import AppointmentCreate
from app.services.appointment_service import AppointmentService

db = SessionLocal()
try:
    queue = db.query(QueueDB).first()
    queue.booking_enabled = True
    queue.slot_capacity = 1
    db.commit()

    service = AppointmentService(db)
    target_date = date.today() + timedelta(days=1)

    slots = service.get_availability(queue.id, target_date)
    assert len(slots) > 0, 'expected computed slots for an enabled queue'
    assert all(s.booked == 0 for s in slots), 'expected no bookings yet'
    print('Availability OK:', len(slots), 'slots, first slot', slots[0].slot_start_time)

    from app.db_models import StudentDB
    student = db.query(StudentDB).first()

    booked = service.create_appointment(AppointmentCreate(
        student_id=student.id, queue_id=queue.id,
        appointment_date=target_date, slot_start_time=slots[0].slot_start_time,
    ))
    assert booked.qr_token, 'expected a qr_token on the booking response'
    assert booked.reference_code.startswith('APT-')
    print('Booked:', booked.reference_code, 'token length', len(booked.qr_token))

    slots_after = service.get_availability(queue.id, target_date)
    assert slots_after[0].booked == 1 and slots_after[0].is_full, 'slot should now be full (capacity=1)'
    print('Slot now full as expected')

    try:
        service.create_appointment(AppointmentCreate(
            student_id=student.id, queue_id=queue.id,
            appointment_date=target_date, slot_start_time=slots[1].slot_start_time,
        ))
        raise AssertionError('expected ValueError for a second active appointment')
    except ValueError as e:
        print('Correctly blocked second active appointment:', e)

    found = service.lookup(student.student_id, booked.reference_code)
    assert found is not None and found.id == booked.id
    assert not hasattr(found, 'qr_token'), 'lookup must not expose qr_token'
    print('Lookup OK, qr_token correctly absent from Appointment model')

    cancelled = service.cancel(booked.id, student.student_id)
    assert cancelled.status.value == 'cancelled'
    print('Cancel OK')

    slots_final = service.get_availability(queue.id, target_date)
    assert slots_final[0].booked == 0, 'slot should be free again after cancel'
    print('OK - slot freed after cancel')
finally:
    queue = db.query(QueueDB).filter(QueueDB.id == queue.id).first()
    queue.booking_enabled = False
    queue.slot_capacity = 3
    db.commit()
    db.close()
"
```

Expected: every assertion passes, ending with `OK - slot freed after cancel`, and the queue's `booking_enabled`/`slot_capacity` are reverted to defaults by the `finally` block so later tasks start clean.

- [ ] **Step 5: Commit**

```bash
git add bsu-registrar-queue/backend/app/models/appointment.py bsu-registrar-queue/backend/app/services/appointment_service.py bsu-registrar-queue/backend/app/services/__init__.py
git commit -m "feat(appointments): add booking schemas and availability/create/lookup/cancel service methods"
```

---

### Task 4: Backend — Check-in, staff search, and no-show expiry

**Files:**
- Modify: `bsu-registrar-queue/backend/app/services/appointment_service.py`

**Interfaces:**
- Consumes: `AppointmentService` from Task 3, `TicketService.create_ticket` (existing, unmodified) via `from .ticket_service import TicketService`, `TicketCreate` from `..models.ticket`.
- Produces: `AppointmentService.search(query: str) -> List[Appointment]`, `.check_in(token, reference_code, staff_user_id, force) -> Ticket` (raises `AppointmentWindowError` for an out-of-window attempt without `force`, `ValueError` for every other rejection), `.expire_stale_appointments(buffer_minutes=EXPIRE_BUFFER_MINUTES) -> int`. Task 5's API router and Celery task call these three directly.

- [ ] **Step 1: Add `search`, `check_in`, and `expire_stale_appointments` to `AppointmentService`**

In `bsu-registrar-queue/backend/app/services/appointment_service.py`, change the imports at the top:

```python
from ..db_models import AppointmentDB, AppointmentDBStatus, QueueDB, StudentDB
from ..models.appointment import (
    Appointment, AppointmentBooked, AppointmentCreate, AppointmentStatus, SlotAvailability
)
```

to:

```python
from ..db_models import AppointmentDB, AppointmentDBStatus, QueueDB, StudentDB
from ..models.appointment import (
    Appointment, AppointmentBooked, AppointmentCreate, AppointmentStatus, SlotAvailability
)
from ..models.ticket import Ticket, TicketCreate
from .ticket_service import TicketService
```

Add these three methods to the `AppointmentService` class, right after `cancel` and before `_generate_reference_code`:

```python
    def search(self, query: str) -> List[Appointment]:
        """Staff manual lookup fallback - matches student ID or reference code, booked appointments only"""
        rows = self.db.query(AppointmentDB).join(StudentDB, AppointmentDB.student_id == StudentDB.id).filter(
            AppointmentDB.status == AppointmentDBStatus.BOOKED,
            or_(
                StudentDB.student_id.ilike(f"%{query}%"),
                AppointmentDB.reference_code.ilike(f"%{query}%"),
            )
        ).order_by(AppointmentDB.appointment_date, AppointmentDB.slot_start_time).limit(20).all()

        result = []
        for appt in rows:
            queue = self.db.query(QueueDB).filter(QueueDB.id == appt.queue_id).first()
            result.append(self._to_appointment(appt, queue))
        return result

    def check_in(
        self,
        token: Optional[str] = None,
        reference_code: Optional[str] = None,
        staff_user_id: Optional[int] = None,
        force: bool = False,
    ) -> Ticket:
        """Scan or manually check in an appointment, creating a normal queue ticket"""
        if not token and not reference_code:
            raise ValueError("Provide a QR token or reference code")

        query = self.db.query(AppointmentDB)
        appointment = (
            query.filter(AppointmentDB.qr_token == token).first() if token
            else query.filter(AppointmentDB.reference_code == reference_code.strip().upper()).first()
        )
        if not appointment:
            raise ValueError("Appointment not found - invalid code")

        if appointment.status == AppointmentDBStatus.CHECKED_IN:
            when = appointment.checked_in_at.strftime('%I:%M %p') if appointment.checked_in_at else "an earlier time"
            raise ValueError(f"This appointment was already checked in at {when}.")
        if appointment.status == AppointmentDBStatus.CANCELLED:
            raise ValueError("This appointment was cancelled.")
        if appointment.status == AppointmentDBStatus.EXPIRED:
            raise ValueError("This appointment has expired. Use manual lookup or take a walk-in ticket.")

        now = datetime.now()
        slot_start = datetime.combine(appointment.appointment_date, appointment.slot_start_time)
        slot_end = datetime.combine(appointment.appointment_date, appointment.slot_end_time)
        window_start = slot_start - timedelta(minutes=GRACE_MINUTES_BEFORE)
        window_end = slot_end + timedelta(minutes=GRACE_MINUTES_AFTER)
        if not force and not (window_start <= now <= window_end):
            raise AppointmentWindowError(
                f"This appointment is scheduled for {appointment.slot_start_time.strftime('%I:%M %p')} "
                f"on {appointment.appointment_date.isoformat()}, outside the normal check-in window."
            )

        # Atomic status flip: guards against two counters checking in the same
        # appointment at once. Only the request that actually flips BOOKED ->
        # CHECKED_IN proceeds to create a ticket.
        rows_updated = self.db.query(AppointmentDB).filter(
            AppointmentDB.id == appointment.id,
            AppointmentDB.status == AppointmentDBStatus.BOOKED,
        ).update({
            "status": AppointmentDBStatus.CHECKED_IN,
            "checked_in_at": now,
            "checked_in_by": staff_user_id,
        })
        self.db.commit()
        if not rows_updated:
            raise ValueError("This appointment was already checked in by another counter.")

        ticket_service = TicketService(self.db)
        ticket_data = TicketCreate(
            student_id=appointment.student_id,
            queue_id=appointment.queue_id,
            purpose=appointment.purpose,
        )
        try:
            ticket = ticket_service.create_ticket(ticket_data)
        except ValueError:
            self._revert_check_in(appointment.id)
            raise

        if not ticket:
            self._revert_check_in(appointment.id)
            raise ValueError(
                "Could not create a ticket for this appointment. The queue may be full or inactive."
            )

        self.db.query(AppointmentDB).filter(AppointmentDB.id == appointment.id).update({"ticket_id": ticket.id})
        self.db.commit()
        return ticket

    def _revert_check_in(self, appointment_id: int) -> None:
        """Roll a check-in back to BOOKED so the appointment can be retried, e.g. when
        ticket creation fails after the status flip already succeeded."""
        self.db.query(AppointmentDB).filter(AppointmentDB.id == appointment_id).update({
            "status": AppointmentDBStatus.BOOKED,
            "checked_in_at": None,
            "checked_in_by": None,
        })
        self.db.commit()

    def expire_stale_appointments(self, buffer_minutes: int = EXPIRE_BUFFER_MINUTES) -> int:
        """Mark BOOKED appointments whose window has fully passed as EXPIRED. Returns count expired."""
        cutoff = datetime.now() - timedelta(minutes=buffer_minutes)
        stale = self.db.query(AppointmentDB).filter(AppointmentDB.status == AppointmentDBStatus.BOOKED).all()
        count = 0
        for appt in stale:
            slot_end = datetime.combine(appt.appointment_date, appt.slot_end_time)
            if slot_end < cutoff:
                appt.status = AppointmentDBStatus.EXPIRED
                appt.updated_at = datetime.now()
                count += 1
        if count:
            self.db.commit()
        return count
```

- [ ] **Step 2: Verify check-in, race behavior, and expiry against the real database**

```bash
cd bsu-registrar-queue/backend
source .venv/Scripts/activate
python -c "
from datetime import date, datetime, timedelta
from app.core.database import SessionLocal
from app.db_models import QueueDB, StudentDB, AppointmentDB, AppointmentDBStatus
from app.models.appointment import AppointmentCreate
from app.services.appointment_service import AppointmentService, AppointmentWindowError

db = SessionLocal()
try:
    queue = db.query(QueueDB).first()
    queue.booking_enabled = True
    db.commit()
    student = db.query(StudentDB).first()

    service = AppointmentService(db)
    target_date = date.today() + timedelta(days=1)
    slots = service.get_availability(queue.id, target_date)
    booked = service.create_appointment(AppointmentCreate(
        student_id=student.id, queue_id=queue.id,
        appointment_date=target_date, slot_start_time=slots[0].slot_start_time,
    ))

    # Future slot -> outside window without force
    try:
        service.check_in(token=booked.qr_token)
        raise AssertionError('expected AppointmentWindowError for a future slot')
    except AppointmentWindowError as e:
        print('Correctly rejected out-of-window check-in:', e)

    ticket = service.check_in(token=booked.qr_token, force=True)
    assert ticket.student_id == student.id and ticket.queue_id == queue.id
    print('Check-in OK, created ticket', ticket.ticket_code)

    appt_row = db.query(AppointmentDB).filter(AppointmentDB.id == booked.id).first()
    assert appt_row.status == AppointmentDBStatus.CHECKED_IN
    assert appt_row.ticket_id == ticket.id
    print('Appointment correctly linked to ticket', appt_row.ticket_id)

    # Reuse must fail
    try:
        service.check_in(token=booked.qr_token, force=True)
        raise AssertionError('expected ValueError for reusing a checked-in token')
    except ValueError as e:
        print('Correctly rejected reuse:', e)

    # Manual lookup fallback by reference code
    found = service.search(booked.reference_code[-4:])
    # already checked in, so search (BOOKED-only) should NOT find it
    assert all(r.id != booked.id for r in found), 'search should only return BOOKED appointments'
    print('Search correctly excludes checked-in appointments')

    # Clean up the ticket so it does not linger as WAITING in the queue.
    # Delete the appointment first - it FK-references the ticket via
    # ticket_id, so deleting the ticket while that reference still exists
    # violates the FK constraint.
    from app.db_models import TicketDB
    db.query(AppointmentDB).filter(AppointmentDB.id == booked.id).delete()
    db.query(TicketDB).filter(TicketDB.id == ticket.id).delete()
    db.commit()

    # Expiry: book a slot dated yesterday directly (bypassing the future-only
    # booking validation, since expiry only cares about DB state) and confirm
    # it gets marked EXPIRED.
    stale = AppointmentDB(
        reference_code='APT-999999',
        student_id=student.id,
        queue_id=queue.id,
        appointment_date=date.today() - timedelta(days=1),
        slot_start_time=slots[0].slot_start_time,
        slot_end_time=slots[0].slot_end_time,
        qr_token='test-stale-token',
        status=AppointmentDBStatus.BOOKED,
    )
    db.add(stale)
    db.commit()
    db.refresh(stale)

    expired_count = service.expire_stale_appointments()
    assert expired_count >= 1
    db.refresh(stale)
    assert stale.status == AppointmentDBStatus.EXPIRED
    print('OK - stale appointment correctly expired')

    db.query(AppointmentDB).filter(AppointmentDB.id == stale.id).delete()
    db.commit()
finally:
    queue = db.query(QueueDB).filter(QueueDB.id == queue.id).first()
    queue.booking_enabled = False
    db.commit()
    db.close()
"
```

Expected: every assertion passes, ending with `OK - stale appointment correctly expired`.

- [ ] **Step 3: Commit**

```bash
git add bsu-registrar-queue/backend/app/services/appointment_service.py
git commit -m "feat(appointments): add check-in, staff search, and no-show expiry to AppointmentService"
```

---

### Task 5: Backend — API router and Celery expiry task

**Files:**
- Create: `bsu-registrar-queue/backend/app/api/appointments.py`
- Modify: `bsu-registrar-queue/backend/app/api/router.py`
- Modify: `bsu-registrar-queue/backend/app/services/notifications.py`

**Interfaces:**
- Consumes: `AppointmentService`, `AppointmentWindowError` (Task 3/4), `Appointment`/`AppointmentBooked`/`AppointmentCreate`/`SlotAvailability`/`AppointmentCheckInRequest` (Task 3), existing `Ticket` model, `require_role`/`get_current_active_user`.
- Produces: 6 endpoints under `/api/appointments` (Global Constraints table in the spec) that Task 6's frontend store calls directly by these exact paths and payload shapes. Celery task `app.services.notifications.expire_stale_appointments` on a 5-minute beat schedule.

- [ ] **Step 1: Write `app/api/appointments.py`**

```python
"""
Appointment booking and check-in endpoints
"""
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from typing import List

from ..core.database import get_db
from ..core.limiter import limiter
from ..core.security import require_role
from ..db_models import UserRole
from ..models.appointment import (
    Appointment, AppointmentBooked, AppointmentCheckInRequest, AppointmentCreate, SlotAvailability
)
from ..models.ticket import Ticket
from ..models.user import User
from ..services.appointment_service import AppointmentService, AppointmentWindowError


router = APIRouter()


@router.get("/availability", response_model=List[SlotAvailability])
def get_availability(
    queue_id: int,
    appointment_date: date,
    db: Session = Depends(get_db)
):
    """List bookable slots and remaining capacity for a queue/date (public)"""
    service = AppointmentService(db)
    return service.get_availability(queue_id, appointment_date)


@router.post("", response_model=AppointmentBooked)
@limiter.limit("10/minute")
def create_appointment(
    request: Request,
    appointment: AppointmentCreate,
    db: Session = Depends(get_db)
):
    """Student books an appointment (public endpoint)"""
    service = AppointmentService(db)
    try:
        return service.create_appointment(appointment)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/lookup", response_model=Appointment)
def lookup_appointment(
    student_id: str = Query(..., description="10-digit student number"),
    reference_code: str = Query(...),
    db: Session = Depends(get_db)
):
    """Student re-views their booking (public endpoint)"""
    service = AppointmentService(db)
    appointment = service.lookup(student_id, reference_code)
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    return appointment


@router.post("/{appointment_id}/cancel", response_model=Appointment)
@limiter.limit("10/minute")
def cancel_appointment(
    request: Request,
    appointment_id: int,
    student_id: str = Query(..., description="10-digit student number"),
    db: Session = Depends(get_db)
):
    """Student cancels their own booked appointment (public endpoint)"""
    service = AppointmentService(db)
    try:
        appointment = service.cancel(appointment_id, student_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    return appointment


@router.get("/search", response_model=List[Appointment])
def search_appointments(
    query: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.REGISTRAR, UserRole.STAFF))
):
    """Manual lookup fallback for staff - matches student ID or reference code (staff only)"""
    service = AppointmentService(db)
    return service.search(query)


@router.post("/checkin", response_model=Ticket)
def check_in(
    payload: AppointmentCheckInRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.REGISTRAR, UserRole.STAFF))
):
    """Scan or manually check in an appointment, creating a queue ticket (staff only)"""
    service = AppointmentService(db)
    try:
        return service.check_in(
            token=payload.token,
            reference_code=payload.reference_code,
            staff_user_id=current_user.id,
            force=payload.force,
        )
    except AppointmentWindowError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

- [ ] **Step 2: Register the router**

Replace `bsu-registrar-queue/backend/app/api/router.py`:

```python
"""
Main API router combining all endpoints
"""
from fastapi import APIRouter
from .queues import router as queues_router
from .tickets import router as tickets_router
from .students import router as students_router
from .auth import router as auth_router
from .media import router as media_router
from .announcements import router as announcements_router

router = APIRouter()

router.include_router(auth_router, prefix="/auth", tags=["auth"])
router.include_router(queues_router, prefix="/queues", tags=["queues"])
router.include_router(tickets_router, prefix="/tickets", tags=["tickets"])
router.include_router(students_router, prefix="/students", tags=["students"])
router.include_router(media_router, prefix="/media", tags=["media"])
router.include_router(announcements_router, prefix="/announcements", tags=["announcements"])
```

with:

```python
"""
Main API router combining all endpoints
"""
from fastapi import APIRouter
from .queues import router as queues_router
from .tickets import router as tickets_router
from .students import router as students_router
from .auth import router as auth_router
from .media import router as media_router
from .announcements import router as announcements_router
from .appointments import router as appointments_router

router = APIRouter()

router.include_router(auth_router, prefix="/auth", tags=["auth"])
router.include_router(queues_router, prefix="/queues", tags=["queues"])
router.include_router(tickets_router, prefix="/tickets", tags=["tickets"])
router.include_router(students_router, prefix="/students", tags=["students"])
router.include_router(media_router, prefix="/media", tags=["media"])
router.include_router(announcements_router, prefix="/announcements", tags=["announcements"])
router.include_router(appointments_router, prefix="/appointments", tags=["appointments"])
```

- [ ] **Step 3: Add the Celery expiry task**

In `bsu-registrar-queue/backend/app/services/notifications.py`, replace the `beat_schedule` block:

```python
celery.conf.beat_schedule = {
    "update-wait-times-every-minute": {
        "task": "app.services.notifications.update_all_wait_times",
        "schedule": 60.0,  # every minute
    },
    "check-no-show-tickets-every-5-minutes": {
        "task": "app.services.notifications.check_no_show_tickets",
        "schedule": 300.0,  # every 5 minutes
    },
}
```

with:

```python
celery.conf.beat_schedule = {
    "update-wait-times-every-minute": {
        "task": "app.services.notifications.update_all_wait_times",
        "schedule": 60.0,  # every minute
    },
    "check-no-show-tickets-every-5-minutes": {
        "task": "app.services.notifications.check_no_show_tickets",
        "schedule": 300.0,  # every 5 minutes
    },
    "expire-stale-appointments-every-5-minutes": {
        "task": "app.services.notifications.expire_stale_appointments",
        "schedule": 300.0,  # every 5 minutes
    },
}
```

Add this task at the end of the file, after `send_queue_closed_notification`:

```python


@celery.task
def expire_stale_appointments():
    """Mark booked appointments whose window has fully passed as expired"""
    db = SessionLocal()
    try:
        from app.services.appointment_service import AppointmentService
        service = AppointmentService(db)
        count = service.expire_stale_appointments()
        if count:
            logger.info(f"Expired {count} stale appointment(s)")
    except Exception as exc:
        logger.error(f"Error expiring stale appointments: {exc}")
    finally:
        db.close()
```

- [ ] **Step 4: Verify the full endpoint surface end-to-end against the real running stack**

```bash
cd bsu-registrar-queue/backend
source .venv/Scripts/activate
uvicorn app.main:app --reload
```

In a second terminal:

```bash
python -c "
import urllib.request, urllib.parse, json
from datetime import date, timedelta

BASE = 'http://localhost:8000/api'

def post(url, data, headers=None, method='POST'):
    req = urllib.request.Request(url, data=json.dumps(data).encode() if data is not None else None, headers=headers or {'Content-Type': 'application/json'}, method=method)
    return json.loads(urllib.request.urlopen(req, timeout=5).read())

def get(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    return json.loads(urllib.request.urlopen(req, timeout=5).read())

login_data = urllib.parse.urlencode({'username': 'admin', 'password': 'admin123'}).encode()
req = urllib.request.Request(f'{BASE}/auth/login', data=login_data, headers={'Content-Type': 'application/x-www-form-urlencoded'})
token = json.loads(urllib.request.urlopen(req, timeout=5).read())['access_token']
auth_headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

queues = get(f'{BASE}/queues', auth_headers)
queue = queues[0]
post(f\"{BASE}/queues/{queue['id']}/booking-settings\", {
    'booking_enabled': True, 'operating_start_time': '08:00:00', 'operating_end_time': '17:00:00',
    'slot_capacity': 3, 'booking_window_days': 14,
}, auth_headers, method='PATCH')

target_date = (date.today() + timedelta(days=1)).isoformat()
slots = get(f\"{BASE}/appointments/availability?queue_id={queue['id']}&appointment_date={target_date}\")
assert len(slots) > 0
print('Availability OK:', len(slots), 'slots')

students = get(f'{BASE}/students?limit=1', auth_headers)
student = students['items'][0]

booked = post(f'{BASE}/appointments', {
    'student_id': student['id'], 'queue_id': queue['id'],
    'appointment_date': target_date, 'slot_start_time': slots[0]['slot_start_time'],
})
assert 'qr_token' in booked and booked['reference_code'].startswith('APT-')
print('Booked:', booked['reference_code'])

looked_up = get(f\"{BASE}/appointments/lookup?student_id={student['student_id']}&reference_code={booked['reference_code']}\")
assert 'qr_token' not in looked_up, 'lookup response must not include qr_token'
print('Lookup OK, no qr_token leaked')

found = get(f\"{BASE}/appointments/search?query={booked['reference_code']}\", auth_headers)
assert any(a['id'] == booked['id'] for a in found)
print('Staff search OK')

ticket = post(f'{BASE}/appointments/checkin', {'token': booked['qr_token'], 'force': True}, auth_headers)
assert ticket['queue_id'] == queue['id'] and ticket['student_id'] == student['id']
print('Check-in OK, created ticket', ticket['ticket_code'])

try:
    post(f'{BASE}/appointments/checkin', {'token': booked['qr_token'], 'force': True}, auth_headers)
    raise AssertionError('expected 400 for reuse')
except urllib.error.HTTPError as e:
    assert e.code == 400
    print('Correctly rejected reuse with 400')

# Clean up: revert queue booking settings, remove the ticket/appointment this
# script created so later tasks (and manual testing) start from a clean state.
post(f\"{BASE}/queues/{queue['id']}/booking-settings\", {
    'booking_enabled': False, 'operating_start_time': '08:00:00', 'operating_end_time': '17:00:00',
    'slot_capacity': 3, 'booking_window_days': 14,
}, auth_headers, method='PATCH')
post(f\"{BASE}/tickets/{ticket['id']}/complete\", None, auth_headers)
print('OK - full booking -> QR -> checkin -> ticket flow verified end-to-end')
"
```

Expected: every assertion passes, ending with `OK - full booking -> QR -> checkin -> ticket flow verified end-to-end`.

- [ ] **Step 5: Commit**

```bash
git add bsu-registrar-queue/backend/app/api/appointments.py bsu-registrar-queue/backend/app/api/router.py bsu-registrar-queue/backend/app/services/notifications.py
git commit -m "feat(appointments): add appointment API router and no-show expiry Celery task"
```

---

### Task 6: Frontend — QR/scanner dependencies + Pinia store actions

**Files:**
- Modify: `bsu-registrar-queue/frontend/package.json`
- Modify: `bsu-registrar-queue/frontend/src/stores/queue.js`

**Interfaces:**
- Consumes: the 6 endpoints from Task 5.
- Produces: `queueStore.appointmentAvailability`, `.myAppointment`, `.bookedAppointment`, `.appointmentSearchResults`, `.checkInResult` state; actions `fetchAppointmentAvailability(queueId, date)`, `bookAppointment(payload)`, `lookupAppointment(studentId, referenceCode)`, `cancelAppointment(appointmentId, studentId)`, `searchAppointments(query)`, `checkInAppointment({ token, referenceCode, force })`. Tasks 8 and 9 call these directly. `qrcode` (QR image generation) and `qr-scanner` (camera decode) become available as npm imports.

- [ ] **Step 1: Install the two new dependencies**

```bash
cd bsu-registrar-queue/frontend
npm install qrcode@^1.5.3 qr-scanner@^1.4.2
```

Expected: `package.json` gains both under `dependencies`, `package-lock.json` updates, no install errors.

- [ ] **Step 2: Add appointment state to the Pinia store**

In `bsu-registrar-queue/frontend/src/stores/queue.js`, replace the `state()` block's Students section:

```javascript
    // Students
    currentStudent: null,
    students: [],
    studentsTotal: 0,
    studentStats: null,
```

with:

```javascript
    // Students
    currentStudent: null,
    students: [],
    studentsTotal: 0,
    studentStats: null,

    // Appointments
    appointmentAvailability: [],
    myAppointment: null,
    bookedAppointment: null,
    appointmentSearchResults: [],
    checkInResult: null,
```

- [ ] **Step 3: Add appointment actions**

In the same file, add this new section right after the `// ============ TICKET ACTIONS ============` block ends and before `// ============ STUDENT ACTIONS ============` (i.e. right after the closing brace of `callTicket`):

```javascript

    // ============ APPOINTMENT ACTIONS ============

    async fetchAppointmentAvailability(queueId, appointmentDate) {
      this.loading = true
      this.error = null
      try {
        const response = await api.get('/appointments/availability', {
          params: { queue_id: queueId, appointment_date: appointmentDate },
        })
        this.appointmentAvailability = response.data
        return response.data
      } catch (err) {
        this.error = err.response?.data?.detail || 'Failed to fetch availability'
        throw err
      } finally {
        this.loading = false
      }
    },

    async bookAppointment(payload) {
      this.loading = true
      this.error = null
      try {
        const response = await api.post('/appointments', payload)
        this.bookedAppointment = response.data
        return response.data
      } catch (err) {
        this.error = err.response?.data?.detail || 'Failed to book appointment'
        throw err
      } finally {
        this.loading = false
      }
    },

    async lookupAppointment(studentId, referenceCode) {
      this.loading = true
      this.error = null
      try {
        const response = await api.get('/appointments/lookup', {
          params: { student_id: studentId, reference_code: referenceCode },
        })
        this.myAppointment = response.data
        return response.data
      } catch (err) {
        this.error = err.response?.data?.detail || 'Appointment not found'
        this.myAppointment = null
        throw err
      } finally {
        this.loading = false
      }
    },

    async cancelAppointment(appointmentId, studentId) {
      this.loading = true
      this.error = null
      try {
        const response = await api.post(`/appointments/${appointmentId}/cancel`, null, {
          params: { student_id: studentId },
        })
        this.myAppointment = response.data
        return response.data
      } catch (err) {
        this.error = err.response?.data?.detail || 'Failed to cancel appointment'
        throw err
      } finally {
        this.loading = false
      }
    },

    async searchAppointments(query) {
      this.loading = true
      this.error = null
      try {
        const response = await api.get('/appointments/search', { params: { query } })
        this.appointmentSearchResults = response.data
        return response.data
      } catch (err) {
        this.error = err.response?.data?.detail || 'Failed to search appointments'
        throw err
      } finally {
        this.loading = false
      }
    },

    async checkInAppointment({ token = null, referenceCode = null, force = false }) {
      this.loading = true
      this.error = null
      try {
        const response = await api.post('/appointments/checkin', {
          token,
          reference_code: referenceCode,
          force,
        })
        this.checkInResult = response.data
        return response.data
      } catch (err) {
        this.error = err.response?.data?.detail || 'Check-in failed'
        throw err
      } finally {
        this.loading = false
      }
    },
```

In the `reset()` action, replace:

```javascript
      this.students = []
      this.studentsTotal = 0
      this.studentStats = null
```

with:

```javascript
      this.students = []
      this.studentsTotal = 0
      this.studentStats = null
      this.appointmentAvailability = []
      this.myAppointment = null
      this.bookedAppointment = null
      this.appointmentSearchResults = []
      this.checkInResult = null
```

- [ ] **Step 4: Verify the build compiles**

```bash
cd bsu-registrar-queue/frontend
npm run build
```

Expected: succeeds with no errors.

- [ ] **Step 5: Commit**

```bash
git add bsu-registrar-queue/frontend/package.json bsu-registrar-queue/frontend/package-lock.json bsu-registrar-queue/frontend/src/stores/queue.js
git commit -m "feat(appointments): add qrcode/qr-scanner deps and appointment store actions"
```

---

### Task 7: Frontend — Queue Management booking-settings UI

**Files:**
- Modify: `bsu-registrar-queue/frontend/src/views/QueueManagementView.vue`

**Interfaces:**
- Consumes: `PATCH /api/queues/{id}/booking-settings` (Task 2), `queueStore.queues` (existing, now includes the 5 booking fields per queue).
- Produces: no new exports - this is a leaf UI change only.

- [ ] **Step 1: Add a "Manage Booking" button and modal**

In `bsu-registrar-queue/frontend/src/views/QueueManagementView.vue`, replace this block inside the `v-if="queue"` template section (right after the Capacity/Slot line, before the action buttons `<div class="flex space-x-2">`):

```html
              <div class="text-sm text-gray-500 mb-3">
                <p>Capacity: {{ queue.max_capacity }} | Slot: {{ queue.slot_duration_minutes }} min</p>
              </div>

              <div class="flex space-x-2">
```

with:

```html
              <div class="text-sm text-gray-500 mb-3">
                <p>Capacity: {{ queue.max_capacity }} | Slot: {{ queue.slot_duration_minutes }} min</p>
                <p class="mt-1">
                  Appointment booking:
                  <span :class="queue.booking_enabled ? 'text-green-700 font-medium' : 'text-gray-400'">
                    {{ queue.booking_enabled ? 'Enabled' : 'Disabled' }}
                  </span>
                </p>
              </div>

              <div class="flex space-x-2 mb-2">
                <button
                  @click="openBookingSettings(queue)"
                  class="btn-secondary btn-sm flex-1"
                >
                  Manage Booking
                </button>
              </div>

              <div class="flex space-x-2">
```

Add the booking-settings modal right after the closing `</Transition>` of the "Create New Queue" modal and before the `<ConfirmDialog` element near the bottom of the template. Replace this:

```html
    </Transition>

    <ConfirmDialog
```

with:

```html
    </Transition>

    <Transition
      enter-active-class="transition duration-150 ease-out"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="transition duration-100 ease-in"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
    <div v-if="showBookingSettingsModal" class="fixed inset-0 bg-bsu-ink/50 flex items-center justify-center z-50">
      <div class="bg-white rounded-2xl shadow-soft-lg max-w-md w-full mx-4">
        <div class="px-6 py-4 border-b border-gray-100">
          <h3 class="text-lg font-bold text-bsu-ink">Manage Booking - {{ bookingSettingsQueue?.name }}</h3>
        </div>
        <div class="px-6 py-4 space-y-4">
          <div class="flex items-center">
            <input
              id="booking_enabled"
              type="checkbox"
              v-model="bookingSettingsForm.booking_enabled"
              class="h-4 w-4 text-bsu-primary border-gray-300 rounded focus:ring-bsu-primary"
            />
            <label for="booking_enabled" class="ml-2 text-sm text-gray-700">
              Allow students to book appointments for this service
            </label>
          </div>

          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1.5">Operating Start</label>
              <input v-model="bookingSettingsForm.operating_start_time" type="time" class="field" />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1.5">Operating End</label>
              <input v-model="bookingSettingsForm.operating_end_time" type="time" class="field" />
            </div>
          </div>

          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1.5">Slot Capacity</label>
              <input v-model.number="bookingSettingsForm.slot_capacity" type="number" min="1" max="50" class="field" />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1.5">Booking Window (days)</label>
              <input v-model.number="bookingSettingsForm.booking_window_days" type="number" min="1" max="90" class="field" />
            </div>
          </div>

          <div v-if="bookingSettingsError" class="p-3 bg-red-50 border border-red-100 rounded-xl">
            <p class="text-sm text-red-700">{{ bookingSettingsError }}</p>
          </div>
        </div>
        <div class="px-6 py-4 border-t border-gray-100 flex justify-end space-x-3">
          <button @click="showBookingSettingsModal = false" class="btn-secondary btn-md">Cancel</button>
          <button @click="saveBookingSettings" :disabled="loading" class="btn-primary btn-md">Save</button>
        </div>
      </div>
    </div>
    </Transition>

    <ConfirmDialog
```

- [ ] **Step 2: Add the booking-settings script logic**

In the `<script setup>` block, add this state and these functions right after the `createQueueError`/`showCreateQueueModal` declarations:

```javascript
const showBookingSettingsModal = ref(false)
const bookingSettingsQueue = ref(null)
const bookingSettingsError = ref('')
const bookingSettingsForm = ref({
  booking_enabled: false,
  operating_start_time: '08:00',
  operating_end_time: '17:00',
  slot_capacity: 3,
  booking_window_days: 14,
})

const openBookingSettings = (queue) => {
  bookingSettingsQueue.value = queue
  bookingSettingsError.value = ''
  bookingSettingsForm.value = {
    booking_enabled: queue.booking_enabled,
    operating_start_time: (queue.operating_start_time || '08:00:00').slice(0, 5),
    operating_end_time: (queue.operating_end_time || '17:00:00').slice(0, 5),
    slot_capacity: queue.slot_capacity,
    booking_window_days: queue.booking_window_days,
  }
  showBookingSettingsModal.value = true
}

const saveBookingSettings = async () => {
  if (!bookingSettingsQueue.value) return
  loading.value = true
  bookingSettingsError.value = ''
  try {
    const payload = {
      ...bookingSettingsForm.value,
      operating_start_time: `${bookingSettingsForm.value.operating_start_time}:00`,
      operating_end_time: `${bookingSettingsForm.value.operating_end_time}:00`,
    }
    await api_patchBookingSettings(bookingSettingsQueue.value.id, payload)
    showBookingSettingsModal.value = false
    await loadQueues()
  } catch (err) {
    bookingSettingsError.value = err.response?.data?.detail || 'Failed to save booking settings'
  } finally {
    loading.value = false
  }
}
```

There's no dedicated store action for this PATCH (it's a one-off admin action, unlike the frequently-reused appointment actions in Task 6), so call the shared `api` axios instance directly. Add this import at the top of the `<script setup>` block, right after the existing `import { useQueueStore } from '@/stores/queue'` line:

```javascript
import axios from 'axios'
```

And add this helper function near the bottom of the script (right before `onMounted`):

```javascript
// Booking settings is a one-off admin action with no other frontend
// consumer, so it calls the API directly rather than adding a rarely-used
// store action - reuses the store's auth token the same way the store's own
// axios instance does.
const api_patchBookingSettings = (queueId, payload) => {
  const token = localStorage.getItem('registrar_token')
  return axios.patch(`/api/queues/${queueId}/booking-settings`, payload, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
}
```

- [ ] **Step 3: Verify the build compiles**

```bash
cd bsu-registrar-queue/frontend
npm run build
```

Expected: succeeds with no errors.

- [ ] **Step 4: Manually verify in the browser**

Start both servers if not already running (`uvicorn app.main:app --reload` in `backend`, `npm run dev` in `frontend`), log in as `admin`/`admin123`, go to Admin → Queue Management.

1. Click "Manage Booking" on any service card. Confirm the modal opens with `booking_enabled` unchecked and default times/capacity/window.
2. Check "Allow students to book appointments", set Operating Start `08:00`, Operating End `16:00`, Slot Capacity `2`, Booking Window `7`, click Save.
3. Confirm the modal closes and the card now shows "Appointment booking: Enabled" in green.
4. Re-open "Manage Booking" on the same card and confirm the saved values are reloaded correctly.
5. Uncheck "Allow students to book appointments" and Save; confirm the card reverts to "Disabled".

- [ ] **Step 5: Commit**

```bash
git add bsu-registrar-queue/frontend/src/views/QueueManagementView.vue
git commit -m "feat(appointments): add booking-settings management UI to Queue Management"
```

---

### Task 8: Frontend — Student booking flow, QR display, lookup, and cancel

**Files:**
- Create: `bsu-registrar-queue/frontend/src/views/AppointmentsView.vue`
- Modify: `bsu-registrar-queue/frontend/src/router/index.js`
- Modify: `bsu-registrar-queue/frontend/src/views/QueuesView.vue`

**Interfaces:**
- Consumes: `queueStore.searchStudent`, `.fetchActiveQueues`, `.fetchAppointmentAvailability`, `.bookAppointment`, `.lookupAppointment`, `.cancelAppointment` (Task 6), `qrcode` npm package (Task 6).
- Produces: public route `/appointments`. No other task depends on this view's internals.

- [ ] **Step 1: Add the `/appointments` route**

In `bsu-registrar-queue/frontend/src/router/index.js`, add this route right after the `/queues` route:

```javascript
    {
      path: '/queues',
      name: 'queues',
      component: () => import('../views/QueuesView.vue')
    },
```

becomes:

```javascript
    {
      path: '/queues',
      name: 'queues',
      component: () => import('../views/QueuesView.vue')
    },
    {
      path: '/appointments',
      name: 'appointments',
      component: () => import('../views/AppointmentsView.vue')
    },
```

- [ ] **Step 2: Add a link to the appointments flow from the ticket-taking page**

In `bsu-registrar-queue/frontend/src/views/QueuesView.vue`, find the STEP 1 service-selection heading:

```html
        <div v-else-if="currentStep === 1">
          <p class="text-center text-gray-500 mb-6">Choose a service you want to request.</p>
```

and replace it with:

```html
        <div v-else-if="currentStep === 1">
          <p class="text-center text-gray-500 mb-2">Choose a service you want to request.</p>
          <p class="text-center text-sm mb-6">
            Prefer to schedule ahead?
            <router-link to="/appointments" class="text-bsu-primary font-medium hover:underline">Book an appointment</router-link>
          </p>
```

- [ ] **Step 3: Write `AppointmentsView.vue`**

```vue
<template>
  <div class="relative min-h-screen bg-bsu-surface flex items-center justify-center px-4 py-10">
    <div class="relative z-10 w-full max-w-2xl bg-white rounded-2xl shadow-soft-lg border border-gray-100 overflow-hidden">
      <div class="p-6 sm:p-8">
        <div class="flex flex-col items-center text-center mb-6">
          <h1 class="text-2xl font-bold text-bsu-ink">Book an Appointment</h1>
          <p class="mt-1 text-sm text-gray-500">Reserve a time slot and get a QR code to check in with at the registrar.</p>
        </div>

        <div class="flex justify-center gap-2 mb-6">
          <button
            @click="mode = 'book'"
            class="btn-sm px-4 py-1.5 rounded-xl"
            :class="mode === 'book' ? 'btn-primary' : 'btn-secondary'"
          >
            New Appointment
          </button>
          <button
            @click="mode = 'lookup'"
            class="btn-sm px-4 py-1.5 rounded-xl"
            :class="mode === 'lookup' ? 'btn-primary' : 'btn-secondary'"
          >
            View / Cancel Existing
          </button>
        </div>

        <div v-if="error" class="mb-4 p-3 bg-red-50 border border-red-100 rounded-xl">
          <p class="text-sm text-red-700">{{ error }}</p>
        </div>

        <!-- ===================== BOOKING FLOW ===================== -->
        <template v-if="mode === 'book'">
          <div v-if="!bookedAppointment">
            <div class="space-y-4">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1.5">Student ID</label>
                <div class="flex gap-2">
                  <input v-model="studentIdInput" type="text" class="field" placeholder="e.g. 2021000001" />
                  <button @click="findStudent" :disabled="loading" class="btn-primary btn-md whitespace-nowrap">Find</button>
                </div>
                <p v-if="student" class="text-sm text-green-700 mt-1.5">{{ student.first_name }} {{ student.last_name }} found</p>
              </div>

              <div v-if="student">
                <label class="block text-sm font-medium text-gray-700 mb-1.5">Service</label>
                <select v-model="selectedQueueId" @change="onQueueChange" class="field">
                  <option :value="null">Select a service</option>
                  <option v-for="q in bookableQueues" :key="q.id" :value="q.id">{{ q.name }}</option>
                </select>
                <p v-if="selectedQueueId && bookableQueues.length === 0" class="text-sm text-gray-500 mt-1.5">
                  No services currently accept appointment bookings.
                </p>
              </div>

              <div v-if="selectedQueueId">
                <label class="block text-sm font-medium text-gray-700 mb-1.5">Date</label>
                <input v-model="selectedDate" @change="loadAvailability" type="date" :min="minDate" :max="maxDate" class="field" />
              </div>

              <div v-if="selectedDate && slots.length > 0">
                <label class="block text-sm font-medium text-gray-700 mb-1.5">Time Slot</label>
                <div class="grid grid-cols-3 gap-2">
                  <button
                    v-for="slot in slots"
                    :key="slot.slot_start_time"
                    @click="selectedSlot = slot"
                    :disabled="slot.is_full"
                    class="px-3 py-2 rounded-xl text-sm border"
                    :class="[
                      slot.is_full ? 'bg-gray-100 text-gray-400 cursor-not-allowed' : 'hover:border-bsu-primary',
                      selectedSlot === slot ? 'border-bsu-primary bg-bsu-primary/10 font-semibold' : 'border-gray-200',
                    ]"
                  >
                    {{ formatTime(slot.slot_start_time) }}
                    <span v-if="slot.is_full" class="block text-xs">Full</span>
                  </button>
                </div>
              </div>
              <div v-else-if="selectedDate" class="text-sm text-gray-500">No bookable slots for this date.</div>

              <div v-if="selectedSlot">
                <label class="block text-sm font-medium text-gray-700 mb-1.5">Purpose (optional)</label>
                <input v-model="purpose" type="text" class="field" placeholder="Briefly describe your purpose" />
              </div>

              <button
                v-if="selectedSlot"
                @click="submitBooking"
                :disabled="loading"
                class="btn-primary btn-md w-full py-2.5"
              >
                Confirm Booking
              </button>
            </div>
          </div>

          <!-- Booking confirmation + QR -->
          <div v-else class="text-center">
            <h3 class="text-lg font-bold text-bsu-ink mb-1">Appointment Booked</h3>
            <p class="text-sm text-gray-500 mb-4">{{ bookedAppointment.queue_name }} - {{ bookedAppointment.appointment_date }} at {{ formatTime(bookedAppointment.slot_start_time) }}</p>

            <img v-if="qrDataUrl" :src="qrDataUrl" alt="Appointment QR code" class="mx-auto mb-3 rounded-xl border border-gray-200" />
            <p class="text-2xl font-bold text-bsu-ink tracking-wide mb-1">{{ bookedAppointment.reference_code }}</p>
            <p class="text-xs text-gray-500 mb-4">Show this QR code (or the code above) at the registrar counter.</p>

            <a
              v-if="qrDataUrl"
              :href="qrDataUrl"
              download="appointment-qr.png"
              class="btn-secondary btn-md inline-block mb-3"
            >
              Download QR Code
            </a>
            <p class="text-xs text-gray-400">Keep your Student ID ({{ student.student_id }}) and reference code to view or cancel this booking later.</p>
          </div>
        </template>

        <!-- ===================== LOOKUP / CANCEL FLOW ===================== -->
        <template v-else>
          <div v-if="!myAppointment" class="space-y-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1.5">Student ID</label>
              <input v-model="lookupStudentId" type="text" class="field" placeholder="e.g. 2021000001" />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1.5">Reference Code</label>
              <input v-model="lookupReferenceCode" type="text" class="field uppercase" placeholder="APT-000482" />
            </div>
            <button @click="doLookup" :disabled="loading" class="btn-primary btn-md w-full py-2.5">Find Appointment</button>
          </div>

          <div v-else class="text-center">
            <h3 class="text-lg font-bold text-bsu-ink mb-1">{{ myAppointment.queue_name }}</h3>
            <p class="text-sm text-gray-500 mb-3">{{ myAppointment.appointment_date }} at {{ formatTime(myAppointment.slot_start_time) }}</p>
            <p class="text-sm mb-4">
              Status:
              <span class="font-semibold capitalize">{{ myAppointment.status.replace('_', ' ') }}</span>
            </p>

            <button
              v-if="myAppointment.status === 'booked'"
              @click="doCancel"
              :disabled="loading"
              class="btn-danger-solid btn-md w-full py-2.5"
            >
              Cancel Appointment
            </button>
            <button @click="myAppointment = null" class="btn-secondary btn-md w-full py-2.5 mt-3">Back</button>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import QRCode from 'qrcode'
import { useQueueStore } from '@/stores/queue'

const queueStore = useQueueStore()
const loading = computed(() => queueStore.loading)
const error = ref('')

const mode = ref('book')

// --- booking flow state ---
const studentIdInput = ref('')
const student = ref(null)
const bookableQueues = ref([])
const selectedQueueId = ref(null)
const selectedDate = ref('')
const slots = ref([])
const selectedSlot = ref(null)
const purpose = ref('')
const bookedAppointment = ref(null)
const qrDataUrl = ref('')

const today = new Date()
const minDate = today.toISOString().slice(0, 10)

const maxDate = computed(() => {
  const queue = bookableQueues.value.find((q) => q.id === selectedQueueId.value)
  const windowDays = queue?.booking_window_days ?? 14
  const max = new Date(today)
  max.setDate(max.getDate() + windowDays)
  return max.toISOString().slice(0, 10)
})

const formatTime = (t) => {
  const [h, m] = t.split(':').map(Number)
  const period = h >= 12 ? 'PM' : 'AM'
  const hour12 = h % 12 === 0 ? 12 : h % 12
  return `${hour12}:${String(m).padStart(2, '0')} ${period}`
}

const findStudent = async () => {
  error.value = ''
  try {
    student.value = await queueStore.searchStudent(studentIdInput.value.trim())
    const active = await queueStore.fetchActiveQueues()
    bookableQueues.value = active.filter((q) => q.booking_enabled)
  } catch (err) {
    error.value = err.response?.data?.detail || 'Student not found'
    student.value = null
  }
}

const onQueueChange = () => {
  selectedDate.value = ''
  slots.value = []
  selectedSlot.value = null
}

const loadAvailability = async () => {
  selectedSlot.value = null
  if (!selectedQueueId.value || !selectedDate.value) return
  error.value = ''
  try {
    slots.value = await queueStore.fetchAppointmentAvailability(selectedQueueId.value, selectedDate.value)
  } catch (err) {
    error.value = err.response?.data?.detail || 'Failed to load available slots'
    slots.value = []
  }
}

const submitBooking = async () => {
  error.value = ''
  try {
    const result = await queueStore.bookAppointment({
      student_id: student.value.id,
      queue_id: selectedQueueId.value,
      appointment_date: selectedDate.value,
      slot_start_time: selectedSlot.value.slot_start_time,
      purpose: purpose.value || null,
    })
    bookedAppointment.value = result
    qrDataUrl.value = await QRCode.toDataURL(result.qr_token, { width: 240, margin: 2 })
  } catch (err) {
    error.value = err.response?.data?.detail || 'Failed to book appointment'
  }
}

// --- lookup/cancel flow state ---
const lookupStudentId = ref('')
const lookupReferenceCode = ref('')
const myAppointment = ref(null)

const doLookup = async () => {
  error.value = ''
  try {
    myAppointment.value = await queueStore.lookupAppointment(
      lookupStudentId.value.trim(),
      lookupReferenceCode.value.trim().toUpperCase()
    )
  } catch (err) {
    error.value = err.response?.data?.detail || 'Appointment not found'
  }
}

const doCancel = async () => {
  error.value = ''
  try {
    myAppointment.value = await queueStore.cancelAppointment(myAppointment.value.id, lookupStudentId.value.trim())
  } catch (err) {
    error.value = err.response?.data?.detail || 'Failed to cancel appointment'
  }
}
</script>
```

- [ ] **Step 4: Verify the build compiles**

```bash
cd bsu-registrar-queue/frontend
npm run build
```

Expected: succeeds with no errors.

- [ ] **Step 5: Manually verify booking, lookup, and cancel in the browser**

With the backend running and at least one queue's booking enabled (via Task 7's UI or the Task 5 verification script), start the frontend dev server and open `/appointments`.

1. Enter a seeded student ID (e.g. `2021000001`), click Find - confirm the name appears and the Service dropdown lists only booking-enabled services.
2. Pick a service, pick tomorrow's date, confirm slots render with times and an available count; pick a slot, optionally add a purpose, click Confirm Booking.
3. Confirm a QR image renders, a reference code like `APT-######` is shown, and "Download QR Code" saves a PNG.
4. Switch to "View / Cancel Existing", enter the same student ID and the reference code from step 3, click Find Appointment - confirm it shows status "Booked".
5. Click Cancel Appointment - confirm the status updates to "Cancelled" and the Cancel button disappears.
6. From `/queues`, confirm the new "Book an appointment" link on Step 1 navigates to `/appointments`.

- [ ] **Step 6: Commit**

```bash
git add bsu-registrar-queue/frontend/src/views/AppointmentsView.vue bsu-registrar-queue/frontend/src/router/index.js bsu-registrar-queue/frontend/src/views/QueuesView.vue
git commit -m "feat(appointments): add student booking, QR display, and lookup/cancel flow"
```

---

### Task 9: Frontend — Admin check-in scan page

**Files:**
- Create: `bsu-registrar-queue/frontend/src/views/CheckInView.vue`
- Modify: `bsu-registrar-queue/frontend/src/router/index.js`
- Modify: `bsu-registrar-queue/frontend/src/components/AdminLayout.vue`

**Interfaces:**
- Consumes: `queueStore.searchAppointments`, `.checkInAppointment` (Task 6), `qr-scanner` npm package (Task 6).
- Produces: staff route `/admin/checkin`. No other task depends on this view's internals.

- [ ] **Step 1: Add the `/admin/checkin` route**

In `bsu-registrar-queue/frontend/src/router/index.js`, add this route inside the `/admin` children array, right after the `counter` route:

```javascript
        {
          path: 'counter',
          name: 'admin-counter',
          component: () => import('../views/CounterView.vue')
        },
```

becomes:

```javascript
        {
          path: 'counter',
          name: 'admin-counter',
          component: () => import('../views/CounterView.vue')
        },
        {
          path: 'checkin',
          name: 'admin-checkin',
          component: () => import('../views/CheckInView.vue')
        },
```

- [ ] **Step 2: Add a nav entry in `AdminLayout.vue`**

In `bsu-registrar-queue/frontend/src/components/AdminLayout.vue`, find the `router-link` for `/admin/counter` and add a new one for `/admin/checkin` right after it, following the exact same structure/classes as the existing links (read the file first to copy its exact link markup, since each nav link shares one class-binding pattern keyed off `$route.path`).

- [ ] **Step 3: Write `CheckInView.vue`**

```vue
<template>
  <div>
    <div class="mb-8">
      <h2 class="text-3xl font-bold text-bsu-ink">Appointment Check-In</h2>
      <p class="mt-2 text-gray-500">Scan a student's QR code or look them up manually to create their queue ticket</p>
    </div>

    <div v-if="error" class="bg-red-50 border border-red-100 rounded-2xl p-4 mb-6">
      <p class="text-sm text-red-700">{{ error }}</p>
    </div>

    <div v-if="pendingWindowConfirm" class="bg-amber-50 border border-amber-200 rounded-2xl p-4 mb-6">
      <p class="text-sm text-amber-800 mb-3">{{ pendingWindowConfirm.message }}</p>
      <div class="flex gap-3">
        <button @click="confirmOverride" class="btn-warning btn-sm">Check In Anyway</button>
        <button @click="pendingWindowConfirm = null" class="btn-secondary btn-sm">Cancel</button>
      </div>
    </div>

    <div v-if="lastTicket" class="bg-green-50 border border-green-200 rounded-2xl p-6 mb-6 text-center">
      <p class="text-sm text-green-700 mb-1">Checked in - ticket created</p>
      <p class="text-4xl font-extrabold text-bsu-ink">{{ lastTicket.ticket_code }}</p>
      <p class="text-sm text-gray-500 mt-1">{{ lastTicket.queue_name }}</p>
    </div>

    <div class="panel mb-6">
      <div class="panel-header flex items-center justify-between">
        <h3 class="text-xl font-bold text-bsu-ink">Scan QR Code</h3>
        <button @click="scanning ? stopScanning() : startScanning()" class="btn-primary btn-sm">
          {{ scanning ? 'Stop Camera' : 'Start Camera' }}
        </button>
      </div>
      <div class="p-6">
        <video ref="videoEl" class="w-full max-w-sm mx-auto rounded-xl bg-black" style="aspect-ratio: 1"></video>
        <p v-if="!scanning" class="text-center text-sm text-gray-500 mt-3">Click "Start Camera" to scan a student's QR code.</p>
      </div>
    </div>

    <div class="panel">
      <div class="panel-header">
        <h3 class="text-xl font-bold text-bsu-ink">Manual Lookup</h3>
      </div>
      <div class="p-6">
        <div class="flex gap-2 mb-4">
          <input
            v-model="manualQuery"
            @keyup.enter="doManualSearch"
            type="text"
            class="field"
            placeholder="Student ID or reference code (e.g. APT-000482)"
          />
          <button @click="doManualSearch" :disabled="loading" class="btn-primary btn-md whitespace-nowrap">Search</button>
        </div>

        <div v-if="searchResults.length > 0" class="space-y-2">
          <div
            v-for="appt in searchResults"
            :key="appt.id"
            class="flex items-center justify-between px-4 py-3 rounded-xl border border-gray-200"
          >
            <div>
              <p class="font-medium text-bsu-ink">{{ appt.reference_code }} - {{ appt.queue_name }}</p>
              <p class="text-sm text-gray-500">{{ appt.appointment_date }} at {{ formatTime(appt.slot_start_time) }}</p>
            </div>
            <button @click="checkIn({ referenceCode: appt.reference_code })" :disabled="loading" class="btn-success-solid btn-sm">
              Check In
            </button>
          </div>
        </div>
        <p v-else-if="searchedOnce" class="text-sm text-gray-500">No matching booked appointments found.</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onUnmounted, computed } from 'vue'
import QrScanner from 'qr-scanner'
import { useQueueStore } from '@/stores/queue'

const queueStore = useQueueStore()
const loading = computed(() => queueStore.loading)
const error = ref('')

const lastTicket = ref(null)
const pendingWindowConfirm = ref(null)

const formatTime = (t) => {
  const [h, m] = t.split(':').map(Number)
  const period = h >= 12 ? 'PM' : 'AM'
  const hour12 = h % 12 === 0 ? 12 : h % 12
  return `${hour12}:${String(m).padStart(2, '0')} ${period}`
}

// --- camera scanning ---
const videoEl = ref(null)
const scanning = ref(false)
let scanner = null

const startScanning = () => {
  if (!videoEl.value) return
  scanner = new QrScanner(
    videoEl.value,
    (result) => {
      stopScanning()
      checkIn({ token: result.data })
    },
    { highlightScanRegion: true, highlightCodeOutline: true }
  )
  scanner.start()
  scanning.value = true
}

const stopScanning = () => {
  scanner?.stop()
  scanner?.destroy()
  scanner = null
  scanning.value = false
}

onUnmounted(() => stopScanning())

// --- manual lookup ---
const manualQuery = ref('')
const searchResults = ref([])
const searchedOnce = ref(false)

const doManualSearch = async () => {
  if (!manualQuery.value.trim()) return
  error.value = ''
  searchedOnce.value = true
  try {
    searchResults.value = await queueStore.searchAppointments(manualQuery.value.trim())
  } catch (err) {
    error.value = err.response?.data?.detail || 'Search failed'
    searchResults.value = []
  }
}

// --- check-in ---
const checkIn = async ({ token = null, referenceCode = null, force = false }) => {
  error.value = ''
  pendingWindowConfirm.value = null
  try {
    const ticket = await queueStore.checkInAppointment({ token, referenceCode, force })
    lastTicket.value = ticket
    searchResults.value = searchResults.value.filter((a) => a.reference_code !== referenceCode)
    manualQuery.value = ''
  } catch (err) {
    if (err.response?.status === 409) {
      pendingWindowConfirm.value = {
        message: err.response.data.detail,
        retry: { token, referenceCode },
      }
    } else {
      error.value = err.response?.data?.detail || 'Check-in failed'
    }
  }
}

const confirmOverride = () => {
  const retry = pendingWindowConfirm.value.retry
  checkIn({ ...retry, force: true })
}
</script>
```

- [ ] **Step 4: Verify the build compiles**

```bash
cd bsu-registrar-queue/frontend
npm run build
```

Expected: succeeds with no errors.

- [ ] **Step 5: Manually verify check-in in the browser**

Log in as `staff`/`staff123` (or `admin`/`admin123`), go to Admin → Check-In (via the new nav entry).

1. Book a fresh appointment via `/appointments` for tomorrow (a future slot, so it's outside the check-in grace window).
2. On the Check-In page, search by the booked reference code in Manual Lookup, click Check In - confirm the amber "outside the normal check-in window" banner appears with "Check In Anyway" / "Cancel".
3. Click "Check In Anyway" - confirm the green "Checked in - ticket created" banner shows a ticket code, and that ticket appears in Admin → Counter for that queue.
4. Book a second appointment, search for it, click Check In, then immediately click Check In again on the (now already-checked-in) appointment - confirm the second attempt shows a clear "already checked in" error, not a second ticket.
5. Click "Start Camera" - confirm the browser prompts for camera permission and, once granted, the video preview renders (scanning a real QR against a phone screen is optional if no second device is available; the manual-lookup path above already exercises the full check-in logic).

- [ ] **Step 6: Commit**

```bash
git add bsu-registrar-queue/frontend/src/views/CheckInView.vue bsu-registrar-queue/frontend/src/router/index.js bsu-registrar-queue/frontend/src/components/AdminLayout.vue
git commit -m "feat(appointments): add admin check-in scan/manual-lookup page"
```

---

### Task 10: End-to-end verification and pilot rollout

**Files:** none (verification only)

**Interfaces:**
- Consumes: the entire feature built in Tasks 1-9.
- Produces: nothing new - confirms the feature works end-to-end on the real stack before being considered done.

- [ ] **Step 1: Full manual walkthrough with both servers and Celery running**

Start PostgreSQL, Redis, the backend (`uvicorn app.main:app --reload`), Celery worker + beat (`celery -A app.worker worker --beat --loglevel=info`, from `bsu-registrar-queue/backend`), and the frontend (`npm run dev`).

1. As admin, enable booking on one queue via Queue Management (Task 7).
2. As a student (new browser tab / incognito, no login), book an appointment via `/appointments` for today (choose a slot close to "now" if operating hours allow, so the check-in window test below doesn't need `force`).
3. Confirm the QR renders and downloads.
4. As staff, go to `/admin/checkin` and check in using the manual lookup path with the reference code. Confirm a ticket is created and appears correctly in Counter (`/admin/counter`) and the public Display Board (`/display/{queue_id}`) with the right priority/position, exactly like a normal walk-in ticket.
5. Confirm the checked-in appointment can no longer be found via `/appointments` lookup as "booked" (status now `checked_in`).
6. Book a second appointment for today at a slot at least 90+ minutes in the past (pick an early-morning slot if past `now`), then manually trigger the Celery beat task early instead of waiting 5 minutes:
   ```bash
   cd bsu-registrar-queue/backend
   source .venv/Scripts/activate
   celery -A app.worker call app.services.notifications.expire_stale_appointments
   ```
   Confirm the appointment's status becomes `expired` via `/appointments/lookup`, and that checking in its reference code now fails with "This appointment has expired."

- [ ] **Step 2: Confirm existing walk-in flow is unaffected**

Take a normal walk-in ticket via `/queues` (no appointment involved) end to end - take ticket, serve next, complete - exactly as before this feature existed. This confirms `TicketService` truly was left unmodified and there's no regression.

- [ ] **Step 3: Final commit (docs only, if any notes were added during verification)**

If everything passed with no code changes needed, there is nothing to commit for this task - the feature is complete as of Task 9's commit. If manual verification surfaced a bug, fix it as part of the relevant earlier task (re-open that task, fix, re-verify, commit there) rather than bolting a fix onto this task.
