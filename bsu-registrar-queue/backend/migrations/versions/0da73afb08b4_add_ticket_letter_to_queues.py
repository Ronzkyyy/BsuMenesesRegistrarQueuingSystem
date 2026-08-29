"""add ticket_letter to queues

Revision ID: 0da73afb08b4
Revises: db210995aa4a
Create Date: 2026-07-20 22:32:08.614762

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0da73afb08b4'
down_revision: Union[str, None] = 'db210995aa4a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Default letter per queue_type (the DB stores the enum MEMBER NAME, e.g.
# 'ENROLLMENT', not the lowercase Python value 'enrollment') - used to
# backfill existing queues before the column becomes NOT NULL.
_TYPE_TO_LETTER = {
    'ENROLLMENT': 'E',
    'DOCUMENT_REQUEST': 'D',
    'CLEARANCE': 'C',
    'SCHOLARSHIP': 'S',
    'OTHERS': 'O',
}


def upgrade() -> None:
    op.add_column('queues', sa.Column('ticket_letter', sa.String(length=1), nullable=True))

    backfill = sa.text(
        "UPDATE queues SET ticket_letter = :letter WHERE queue_type = :queue_type"
    )
    for queue_type, letter in _TYPE_TO_LETTER.items():
        op.execute(backfill.bindparams(letter=letter, queue_type=queue_type))

    op.alter_column('queues', 'ticket_letter', existing_type=sa.String(length=1), nullable=False)


def downgrade() -> None:
    op.drop_column('queues', 'ticket_letter')
