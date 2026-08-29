"""
Shared pytest fixtures.

Points the app at a disposable `bsu_queue_test` database (same Postgres
instance/credentials as .env, different dbname) *before* any `app.*` module
is imported, since app.core.database builds its engine at import time from
settings.DATABASE_URL - overriding the env var after that point would be
too late.
"""
import os
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from dotenv import dotenv_values

BACKEND_DIR = Path(__file__).resolve().parent.parent
_env_values = dotenv_values(BACKEND_DIR / ".env")
_base_url = _env_values.get("DATABASE_URL") or os.environ["DATABASE_URL"]
_parsed = urlparse(_base_url)
TEST_DB_NAME = "bsu_queue_test"
TEST_DATABASE_URL = urlunparse(_parsed._replace(path=f"/{TEST_DB_NAME}"))
os.environ["DATABASE_URL"] = TEST_DATABASE_URL


def _ensure_test_database_exists():
    """Create the disposable test database if it doesn't exist yet.

    True on a fresh CI Postgres container every run (only the default
    `postgres` maintenance database exists), and was true locally the first
    time this suite was ever set up - so this makes the suite
    self-provisioning everywhere instead of relying on a one-off manual step.
    """
    import psycopg2

    maintenance_url = urlunparse(_parsed._replace(path="/postgres"))
    conn = psycopg2.connect(maintenance_url)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (TEST_DB_NAME,))
            if not cur.fetchone():
                # A database name is a SQL identifier, not a value, so it cannot
                # be a bind parameter. TEST_DB_NAME is a hardcoded constant in
                # this file (never user input), so interpolating it is safe.
                cur.execute(f'CREATE DATABASE "{TEST_DB_NAME}"')
    finally:
        conn.close()

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _apply_migrations():
    """Build the test database's schema by running the real Alembic
    migrations against it once per test session - same schema-build path
    as production, so a broken migration fails tests too.

    Also truncates every table first: bsu_queue_test turned out to already
    contain a handful of leftover rows (its origin is unclear - possibly
    inherited via Postgres's CREATE DATABASE template on this Supabase
    project), so an empty-database assumption isn't safe. Truncating here
    guarantees a byte-for-byte clean slate every run regardless of cause.
    """
    _ensure_test_database_exists()

    alembic_cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    command.upgrade(alembic_cfg, "head")

    import app.db_models as db_models  # noqa: F401  (registers all tables on Base.metadata)
    from app.core.database import Base

    engine = create_engine(TEST_DATABASE_URL)
    with engine.begin() as connection:
        # Table names are SQL identifiers (not bindable values) and come from
        # SQLAlchemy's own schema metadata, not from any request/user input, so
        # interpolating them into this teardown DDL is safe.
        table_names = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
        if table_names:
            connection.exec_driver_sql(f"TRUNCATE TABLE {table_names} RESTART IDENTITY CASCADE")
    engine.dispose()

    yield


@pytest.fixture(scope="session")
def _engine():
    """One shared engine/connection pool for the whole test run - the test
    DB is on a remote Supabase pooler, so opening a fresh TCP/TLS connection
    per test (as a per-test create_engine() would) dominates runtime."""
    engine = create_engine(TEST_DATABASE_URL)
    yield engine
    engine.dispose()


@pytest.fixture()
def db_session(_engine):
    """One transactional DB session per test.

    The session is bound to a connection with an outer transaction already
    started; join_transaction_mode="create_savepoint" makes the service
    layer's own db.commit() calls create/release SAVEPOINTs instead of
    committing the outer transaction, so the final rollback still discards
    everything the test did, keeping tests isolated and fast without
    rebuilding the schema each time.
    """
    connection = _engine.connect()
    transaction = connection.begin()
    SessionLocal = sessionmaker(bind=connection, join_transaction_mode="create_savepoint")
    session = SessionLocal()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


import itertools  # noqa: E402
import string  # noqa: E402

# Module-level so letters/ids stay unique across every test in the run, not
# just within one test - cheap insurance against uniqueness-constraint
# collisions when a test creates more than one queue/student.
_letter_cycle = itertools.cycle(string.ascii_uppercase)
_student_id_counter = itertools.count(3000000001)


@pytest.fixture()
def make_queue(db_session):
    """Factory for a persisted test Queue via the real QueueService."""
    from app.services.queue_service import QueueService
    from app.models.queue import QueueCreate, QueueType

    service = QueueService(db_session)

    def _make(**overrides):
        letter = overrides.pop("ticket_letter", next(_letter_cycle))
        defaults = dict(
            name=f"Test Queue {letter}",
            queue_type=QueueType.OTHERS,
            ticket_letter=letter,
        )
        defaults.update(overrides)
        return service.create_queue(QueueCreate(**defaults))

    return _make


@pytest.fixture()
def make_student(db_session):
    """Factory for a persisted test Student via the real StudentService."""
    from app.services.student_service import StudentService
    from app.models.student import StudentCreate, StudentType, Course, YearLevel

    service = StudentService(db_session)

    def _make(**overrides):
        sid = overrides.pop("student_id", str(next(_student_id_counter)))
        defaults = dict(
            student_id=sid,
            first_name="Test",
            last_name="Student",
            email=f"{sid}@example.com",
            student_type=StudentType.UNDERGRADUATE,
            course=Course.BSIT,
            year_level=YearLevel.FIRST,
        )
        defaults.update(overrides)
        return service.create_student(StudentCreate(**defaults))

    return _make


_username_counter = itertools.count(1)


@pytest.fixture()
def make_user(db_session):
    """Factory for a persisted staff UserDB with a known plaintext password."""
    from app.db_models import UserDB, UserRole
    from app.core.security import get_password_hash

    def _make(password="secret-pass-123", role=UserRole.STAFF, **overrides):
        defaults = dict(
            username=overrides.pop("username", f"user{next(_username_counter)}"),
            full_name="Test User",
            role=role,
            hashed_password=get_password_hash(password),
            is_active=True,
        )
        defaults.update(overrides)
        user = UserDB(**defaults)
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        user._plain_password = password
        return user

    return _make


@pytest.fixture()
def client(db_session):
    """FastAPI TestClient wired to the per-test transactional session, with
    the per-IP rate limiter disabled so tests can exercise the app's own
    logic (e.g. account lockout) without tripping slowapi first."""
    from fastapi.testclient import TestClient
    from app.main import app
    from app.core.database import get_db as db_get_db
    from app.core.security import get_db as security_get_db
    from app.core.limiter import limiter

    # Two get_db callables exist (app.core.database and a duplicate in
    # app.core.security used by get_current_user) - override both so every
    # request in a test shares the one transactional session.
    for dep in (db_get_db, security_get_db):
        app.dependency_overrides[dep] = lambda: db_session
    limiter_was_enabled = limiter.enabled
    limiter.enabled = False
    try:
        with TestClient(app) as c:
            yield c
    finally:
        limiter.enabled = limiter_was_enabled
        for dep in (db_get_db, security_get_db):
            app.dependency_overrides.pop(dep, None)
