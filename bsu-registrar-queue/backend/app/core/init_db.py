"""
Database initialization script - creates tables and seeds initial data
"""
try:
    from sqlalchemy.orm import Session
except Exception:  # pragma: no cover - fallback for editors or missing deps
    # Provide a minimal stub for editors/type checkers when SQLAlchemy isn't installed
    class Session:  # type: ignore
        def query(self, *args, **kwargs):
            raise RuntimeError("SQLAlchemy not available in this environment")
from ..db_models import Base, QueueDB, QueueDBType, QueueDBStatus, UserDB, UserRole, StudentDB, StudentDBType, Course, Major, YearLevel
from ..core.config import settings
from ..core.database import engine, SessionLocal
from ..core.security import get_password_hash


def init_db() -> None:
    """Initialize database tables"""
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully")


def seed_initial_data(db: Session) -> None:
    """Seed initial queues and admin user"""

    # Check if already seeded
    if db.query(QueueDB).first():
        print("Database already seeded, skipping...")
        return

    # Create default queues
    queues = [
        QueueDB(
            name="Enrollment",
            queue_type=QueueDBType.ENROLLMENT,
            ticket_letter="E",
            description="Course enrollment and registration services",
            allow_priority=True,
            max_capacity=100,
            slot_duration_minutes=30,
        ),
        QueueDB(
            name="Document Request",
            queue_type=QueueDBType.DOCUMENT_REQUEST,
            ticket_letter="D",
            description="Transcript, diploma, and certificate requests",
            allow_priority=True,
            max_capacity=50,
            slot_duration_minutes=20,
        ),
        QueueDB(
            name="Clearance",
            queue_type=QueueDBType.CLEARANCE,
            ticket_letter="C",
            description="Academic clearance processing",
            allow_priority=True,
            max_capacity=50,
            slot_duration_minutes=15,
        ),
        QueueDB(
            name="Scholarship",
            queue_type=QueueDBType.SCHOLARSHIP,
            ticket_letter="S",
            description="Scholarship applications and inquiries",
            allow_priority=True,
            max_capacity=30,
            slot_duration_minutes=30,
        ),
        QueueDB(
            name="General Inquiry",
            queue_type=QueueDBType.OTHERS,
            ticket_letter="O",
            description="General registrar inquiries and assistance",
            allow_priority=False,
            max_capacity=30,
            slot_duration_minutes=15,
        ),
        QueueDB(
            name="Adding & Dropping",
            queue_type=QueueDBType.ADDING_DROPPING,
            ticket_letter="A",
            description="Process for adding or dropping subjects",
            allow_priority=True,
            max_capacity=50,
            slot_duration_minutes=15,
        ),
        QueueDB(
            name="Petition Class",
            queue_type=QueueDBType.PETITION_CLASS,
            ticket_letter="P",
            description="File a petition for class consideration",
            allow_priority=True,
            max_capacity=30,
            slot_duration_minutes=20,
        ),
        QueueDB(
            name="Others",
            queue_type=QueueDBType.OTHER_CONCERNS,
            ticket_letter="X",
            description="Other concerns not listed",
            allow_priority=False,
            max_capacity=30,
            slot_duration_minutes=15,
        ),
    ]

    for queue in queues:
        db.add(queue)

    # Demo accounts with well-known passwords are for local/dev use only -
    # start.sh runs this seeder on every production boot too, and a
    # publicly-documented admin/admin123 would be a standing backdoor into
    # any real deployment. Only ever create them when DEBUG=True.
    if settings.DEBUG:
        db.add(UserDB(
            username="admin",
            full_name="System Administrator",
            role=UserRole.ADMIN,
            hashed_password=get_password_hash("admin123"),
            is_active=True,
        ))
        db.add(UserDB(
            username="registrar",
            full_name="Registrar Staff",
            role=UserRole.REGISTRAR,
            hashed_password=get_password_hash("registrar123"),
            is_active=True,
        ))
        db.add(UserDB(
            username="staff",
            full_name="Front Desk Staff",
            role=UserRole.STAFF,
            hashed_password=get_password_hash("staff123"),
            is_active=True,
        ))
    elif settings.INITIAL_ADMIN_USERNAME and settings.INITIAL_ADMIN_PASSWORD:
        # Explicit, deliberate bootstrap for a real deployment's first admin -
        # set once via env vars, never a guessable built-in default.
        if len(settings.INITIAL_ADMIN_PASSWORD) < 8:
            print("INITIAL_ADMIN_PASSWORD is too short (min 8 chars) - skipping admin bootstrap")
        else:
            db.add(UserDB(
                username=settings.INITIAL_ADMIN_USERNAME,
                full_name="System Administrator",
                role=UserRole.ADMIN,
                hashed_password=get_password_hash(settings.INITIAL_ADMIN_PASSWORD),
                is_active=True,
            ))
            print(f"Created initial admin account '{settings.INITIAL_ADMIN_USERNAME}' from INITIAL_ADMIN_* env vars")
    else:
        print(
            "No admin account created (DEBUG=False and INITIAL_ADMIN_USERNAME/"
            "INITIAL_ADMIN_PASSWORD not set) - create one manually or set those "
            "env vars and redeploy."
        )

    # Create sample students
    students = [
        StudentDB(
            student_id="2021000001",
            first_name="Juan",
            last_name="Dela Cruz",
            email="juan.delacruz@bsu.edu.ph",
            student_type=StudentDBType.UNDERGRADUATE,
            course=Course.BIT,
            major=Major.COMPUTER_TECHNOLOGY,
            year_level=YearLevel.FOURTH,
            is_graduating=True,
        ),
        StudentDB(
            student_id="2022000045",
            first_name="Maria",
            last_name="Santos",
            email="maria.santos@bsu.edu.ph",
            student_type=StudentDBType.UNDERGRADUATE,
            course=Course.BSBA,
            year_level=YearLevel.THIRD,
            is_scholar=True,
        ),
        StudentDB(
            student_id="2023000123",
            first_name="Pedro",
            last_name="Garcia",
            email="pedro.garcia@bsu.edu.ph",
            student_type=StudentDBType.UNDERGRADUATE,
            course=Course.BSIT,
            year_level=YearLevel.SECOND,
            is_varsity=True,
        ),
        StudentDB(
            student_id="2024000567",
            first_name="Ana",
            last_name="Reyes",
            email="ana.reyes@bsu.edu.ph",
            student_type=StudentDBType.UNDERGRADUATE,
            course=Course.BSHM,
            year_level=YearLevel.FIRST,
        ),
    ]

    for student in students:
        db.add(student)

    db.commit()
    print("Initial data seeded successfully")


if __name__ == "__main__":
    init_db()
    db = SessionLocal()
    try:
        seed_initial_data(db)
    finally:
        db.close()