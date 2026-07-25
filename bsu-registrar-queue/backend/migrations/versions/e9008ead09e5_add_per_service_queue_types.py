"""add per-service queue types

Revision ID: e9008ead09e5
Revises: 0da73afb08b4
Create Date: 2026-07-26 01:06:51.345106

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e9008ead09e5'
down_revision: Union[str, None] = '0da73afb08b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Postgres can't safely add enum values and use them in the same
    # transaction, so follow the same rename-swap-drop pattern already used
    # in 8de3c8b4f094 (course/major migration) - but without truncating any
    # data, since real ticket/queue history now exists and must be kept.
    op.execute("ALTER TYPE queuedbtype RENAME TO queuedbtype_old")
    op.execute(
        "CREATE TYPE queuedbtype AS ENUM ("
        "'ENROLLMENT', 'DOCUMENT_REQUEST', 'CLEARANCE', 'SCHOLARSHIP', 'OTHERS', "
        "'ADDING_DROPPING', 'PETITION_CLASS', 'OTHER_CONCERNS'"
        ")"
    )
    op.execute(
        "ALTER TABLE queues ALTER COLUMN queue_type TYPE queuedbtype "
        "USING queue_type::text::queuedbtype"
    )
    op.execute("DROP TYPE queuedbtype_old")

    # Python-level Column defaults (status, allow_priority, max_capacity,
    # slot_duration_minutes, current_ticket_number) only apply through the
    # ORM, not raw SQL - every column is spelled out explicitly here.
    op.execute("""
        INSERT INTO queues
            (name, queue_type, ticket_letter, description, status, allow_priority, max_capacity, slot_duration_minutes, current_ticket_number)
        VALUES
            ('Adding & Dropping', 'ADDING_DROPPING', 'A', 'Process for adding or dropping subjects.', 'ACTIVE', true, 50, 15, 0),
            ('Petition Class', 'PETITION_CLASS', 'P', 'File a petition for class consideration.', 'ACTIVE', true, 30, 20, 0),
            ('Others', 'OTHER_CONCERNS', 'X', 'Other concerns not listed.', 'ACTIVE', false, 30, 15, 0)
    """)


def downgrade() -> None:
    # A Postgres enum value can't be removed while any row still uses it -
    # delete tickets against the 3 new queue types first (only those
    # tickets, not the whole table), then the 3 new queues themselves.
    op.execute("""
        DELETE FROM tickets
        WHERE queue_id IN (
            SELECT id FROM queues WHERE queue_type IN ('ADDING_DROPPING', 'PETITION_CLASS', 'OTHER_CONCERNS')
        )
    """)
    op.execute("""
        DELETE FROM queues WHERE queue_type IN ('ADDING_DROPPING', 'PETITION_CLASS', 'OTHER_CONCERNS')
    """)

    op.execute("ALTER TYPE queuedbtype RENAME TO queuedbtype_old")
    op.execute(
        "CREATE TYPE queuedbtype AS ENUM ("
        "'ENROLLMENT', 'DOCUMENT_REQUEST', 'CLEARANCE', 'SCHOLARSHIP', 'OTHERS'"
        ")"
    )
    op.execute(
        "ALTER TABLE queues ALTER COLUMN queue_type TYPE queuedbtype "
        "USING queue_type::text::queuedbtype"
    )
    op.execute("DROP TYPE queuedbtype_old")
