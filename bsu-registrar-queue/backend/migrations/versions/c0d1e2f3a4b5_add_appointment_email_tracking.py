"""add appointment email tracking

Revision ID: c0d1e2f3a4b5
Revises: b9c0d1e2f3a4
Create Date: 2026-10-13 00:00:00.000000

Students who book an appointment are now emailed a confirmation and a
same-day morning reminder. These columns record what went out so the
reminder is never sent twice and staff can see its status. Additive only -
old code running against this schema ignores them.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c0d1e2f3a4b5'
down_revision: Union[str, None] = 'b9c0d1e2f3a4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('appointments', sa.Column('confirmation_sent_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('appointments', sa.Column('reminder_sent_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('appointments', sa.Column('reminder_attempts', sa.Integer(), server_default='0', nullable=False))


def downgrade() -> None:
    op.drop_column('appointments', 'reminder_attempts')
    op.drop_column('appointments', 'reminder_sent_at')
    op.drop_column('appointments', 'confirmation_sent_at')
