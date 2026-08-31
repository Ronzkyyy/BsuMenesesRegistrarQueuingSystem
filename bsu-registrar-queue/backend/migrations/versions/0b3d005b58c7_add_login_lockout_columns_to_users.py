"""add login lockout columns to users

Revision ID: 0b3d005b58c7
Revises: b7c8d9e0f1a2
Create Date: 2026-08-29 21:38:04.938119

Additive brute-force protection for staff login: failed_login_attempts
counts consecutive bad passwords (reset to 0 on any success) and locked_until
blocks all logins for an account once the threshold is hit. Both default so
existing rows are unaffected.

(Only the two add_column statements are kept - `alembic revision
--autogenerate` also emits spurious nullable/unique-constraint drift for this
project's schema, which is why migrations here are hand-trimmed.)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0b3d005b58c7'
down_revision: Union[str, None] = 'b7c8d9e0f1a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('failed_login_attempts', sa.Integer(), server_default='0', nullable=False),
    )
    op.add_column(
        'users',
        sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('users', 'locked_until')
    op.drop_column('users', 'failed_login_attempts')
