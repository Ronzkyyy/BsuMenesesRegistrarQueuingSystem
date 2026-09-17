"""add document_type to tickets and appointments

Revision ID: 9c1c2512b9e8
Revises: 3d0ac8c02e4a
Create Date: 2026-09-17 10:00:00.000000

Adds a scoped `document_type` column - not a reintroduction of the generic
`purpose` field dropped in 3d0ac8c02e4a. It only ever has a value for the
Request Documents service (enforced in the service layer, not here); every
other queue type leaves it NULL, so it doesn't reintroduce the redundancy
with queue_name that motivated dropping `purpose`.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9c1c2512b9e8'
down_revision: Union[str, None] = '3d0ac8c02e4a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('tickets', sa.Column('document_type', sa.String(length=30), nullable=True))
    op.add_column('appointments', sa.Column('document_type', sa.String(length=30), nullable=True))


def downgrade() -> None:
    op.drop_column('appointments', 'document_type')
    op.drop_column('tickets', 'document_type')
