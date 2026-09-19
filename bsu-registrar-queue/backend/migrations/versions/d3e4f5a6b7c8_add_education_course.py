"""add education course

Revision ID: d3e4f5a6b7c8
Revises: 9c1c2512b9e8
Create Date: 2026-09-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'd3e4f5a6b7c8'
down_revision: Union[str, None] = '9c1c2512b9e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# The `course` enum stores member *names* (SQLAlchemy's Enum default), so the
# value added here is 'BSED', matching db_models.Course.BSED.
_OLD_VALUES = "'BSIT', 'BSHM', 'BSBA', 'BSCPE', 'BIT'"
_NEW_VALUES = "'BSIT', 'BSHM', 'BSBA', 'BSCPE', 'BSED', 'BIT'"


def upgrade() -> None:
    # Postgres can't add an enum value and use it in the same transaction, so
    # follow the rename-swap-drop pattern already used in c1d2e3f4a5b6 - no
    # data loss, since real student/ticket history now exists.
    op.execute("ALTER TYPE course RENAME TO course_old")
    op.execute(f"CREATE TYPE course AS ENUM ({_NEW_VALUES})")
    op.execute(
        "ALTER TABLE students ALTER COLUMN course TYPE course "
        "USING course::text::course"
    )
    op.execute("DROP TYPE course_old")


def downgrade() -> None:
    # A Postgres enum value can't be removed while any row still uses it -
    # drop tickets and appointments belonging to BSED students (both hold a
    # foreign key to students.id), then those students.
    op.execute("""
        DELETE FROM tickets
        WHERE student_id IN (SELECT id FROM students WHERE course = 'BSED')
    """)
    op.execute("""
        DELETE FROM appointments
        WHERE student_id IN (SELECT id FROM students WHERE course = 'BSED')
    """)
    op.execute("DELETE FROM students WHERE course = 'BSED'")

    op.execute("ALTER TYPE course RENAME TO course_old")
    op.execute(f"CREATE TYPE course AS ENUM ({_OLD_VALUES})")
    op.execute(
        "ALTER TABLE students ALTER COLUMN course TYPE course "
        "USING course::text::course"
    )
    op.execute("DROP TYPE course_old")
