"""replace college with course and major

Revision ID: 8de3c8b4f094
Revises: 001
Create Date: 2026-07-13 03:46:38.927068

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '8de3c8b4f094'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

course_enum = postgresql.ENUM('BSIT', 'BSHM', 'BSBA', 'BIT', name='course')
major_enum = postgresql.ENUM('COMPUTER_TECHNOLOGY', 'FOOD_PROCESSING_TECHNOLOGY', name='major')
college_enum = postgresql.ENUM('CAS', 'CBA', 'CEA', 'COE', 'CHS', 'CHT', 'OTHER', name='college')


def upgrade() -> None:
    # Meneses Campus only offers the courses below - the old multi-college
    # values don't map onto them, and only dev/seed data exists, so we clear
    # student/ticket rows instead of trying to migrate old values.
    op.execute('TRUNCATE TABLE tickets, students RESTART IDENTITY CASCADE')

    op.drop_column('students', 'college')
    op.execute('DROP TYPE IF EXISTS college')

    bind = op.get_bind()
    course_enum.create(bind, checkfirst=True)
    major_enum.create(bind, checkfirst=True)

    op.add_column('students', sa.Column('course', course_enum, nullable=False))
    op.add_column('students', sa.Column('major', major_enum, nullable=True))


def downgrade() -> None:
    op.execute('TRUNCATE TABLE tickets, students RESTART IDENTITY CASCADE')

    op.drop_column('students', 'major')
    op.drop_column('students', 'course')

    bind = op.get_bind()
    major_enum.drop(bind, checkfirst=True)
    course_enum.drop(bind, checkfirst=True)

    college_enum.create(bind, checkfirst=True)
    op.add_column('students', sa.Column('college', college_enum, nullable=False))
