"""remove purpose from tickets and appointments

Revision ID: 3d0ac8c02e4a
Revises: c1d2e3f4a5b6
Create Date: 2026-09-16 20:43:38.631976

Drops the free-text `purpose` column from tickets and appointments. The
field let a student describe what they were queueing for, but for every
queue except Document Request it just duplicated the queue name, and for
Document Request the document-type picker fed it too - removing it means
the picker (and the field itself) is gone from both the kiosk and the
booking flow.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3d0ac8c02e4a'
down_revision: Union[str, None] = 'c1d2e3f4a5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column('tickets', 'purpose')
    op.drop_column('appointments', 'purpose')


def downgrade() -> None:
    op.add_column('appointments', sa.Column('purpose', sa.TEXT(), autoincrement=False, nullable=True))
    op.add_column('tickets', sa.Column('purpose', sa.TEXT(), autoincrement=False, nullable=True))
