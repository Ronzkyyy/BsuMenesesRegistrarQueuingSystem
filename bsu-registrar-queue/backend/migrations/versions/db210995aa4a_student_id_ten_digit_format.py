"""student id ten digit format

Revision ID: db210995aa4a
Revises: 8de3c8b4f094
Create Date: 2026-07-13 14:40:02.812809

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'db210995aa4a'
down_revision: Union[str, None] = '8de3c8b4f094'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Old "YYYY-NNNNN" dash format -> new 10-digit "YYYYNNNNNN" format
_ID_MAP = {
    '2021-00001': '2021000001',
    '2022-00045': '2022000045',
    '2023-00123': '2023000123',
    '2024-00567': '2024000567',
}


_UPDATE = sa.text(
    "UPDATE students SET student_id = :new WHERE student_id = :old"
)


def upgrade() -> None:
    for old_id, new_id in _ID_MAP.items():
        op.execute(_UPDATE.bindparams(new=new_id, old=old_id))
    op.alter_column('students', 'student_id', existing_type=sa.String(length=20), type_=sa.String(length=10))


def downgrade() -> None:
    op.alter_column('students', 'student_id', existing_type=sa.String(length=10), type_=sa.String(length=20))
    for old_id, new_id in _ID_MAP.items():
        op.execute(_UPDATE.bindparams(new=old_id, old=new_id))
