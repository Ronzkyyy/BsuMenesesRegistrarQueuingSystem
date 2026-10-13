"""add document catalog and multi-document requests

Revision ID: b9c0d1e2f3a4
Revises: a8b9c0d1e2f3
Create Date: 2026-10-13 00:00:00.000000

A Request Documents ticket/appointment can now ask for several documents,
picked from an admin-managed `documents` catalog instead of the hardcoded
DocumentType enum. What was requested lives in `ticket_documents` /
`appointment_documents`, each row a snapshot (name, short name, fee) taken
at request time.

The seven documents the enum offered are seeded in their old order, with
`short_name` equal to the old stored value, and every existing
`document_type` is backfilled into the new tables. The legacy
`document_type` columns are left in place (no longer written) so old code
running against this schema keeps working; a later migration drops them.

Downgrade copies each transaction's first document back into
`document_type`. A request with several documents keeps only the first -
acceptable for a rollback.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b9c0d1e2f3a4'
down_revision: Union[str, None] = 'a8b9c0d1e2f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SEED_DOCUMENTS = [
    # (short_name - the old stored value, name - the old kiosk label)
    ("TOR", "Certified True Copy - Transcript of Records (TOR)"),
    ("COR", "Certified True Copy - Certificate of Registration (COR)"),
    ("COG", "Certified True Copy - Certificate of Grades (COG)"),
    ("Diploma", "Certified True Copy - Diploma"),
    ("Good Moral", "Certified True Copy - Good Moral Certificate"),
    ("Graduation Form", "Certified True Copy - Graduation Form"),
    ("Form 137", "Certified True Copy - Form 137"),
]

# Fixed SQL with no user values. Module-level so the backfill test can run
# exactly these statements against legacy rows.
BACKFILL_TICKETS = sa.text(
    "INSERT INTO ticket_documents (ticket_id, document_id, name, short_name, fee, position) "
    "SELECT t.id, d.id, d.name, d.short_name, NULL, d.display_order "
    "FROM tickets t JOIN documents d ON d.short_name = t.document_type "
    "WHERE NOT EXISTS (SELECT 1 FROM ticket_documents td WHERE td.ticket_id = t.id)"
)
BACKFILL_APPOINTMENTS = sa.text(
    "INSERT INTO appointment_documents (appointment_id, document_id, name, short_name, fee, position) "
    "SELECT a.id, d.id, d.name, d.short_name, NULL, d.display_order "
    "FROM appointments a JOIN documents d ON d.short_name = a.document_type "
    "WHERE NOT EXISTS (SELECT 1 FROM appointment_documents ad WHERE ad.appointment_id = a.id)"
)


def _association_table(name: str, owner_col: str, owner_table: str) -> None:
    op.create_table(
        name,
        sa.Column(owner_col, sa.Integer(), nullable=False),
        sa.Column('document_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('short_name', sa.String(length=30), nullable=False),
        sa.Column('fee', sa.Numeric(10, 2), nullable=True),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint([owner_col], [f'{owner_table}.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint(owner_col, 'document_id'),
    )
    op.create_index(op.f(f'ix_{name}_document_id'), name, ['document_id'])


def upgrade() -> None:
    documents = op.create_table(
        'documents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('short_name', sa.String(length=30), nullable=False),
        sa.Column('requirements', sa.String(length=500), nullable=True),
        sa.Column('processing_time', sa.String(length=50), nullable=True),
        sa.Column('fee', sa.Numeric(10, 2), nullable=True),
        sa.Column('display_order', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_documents_id'), 'documents', ['id'])
    op.create_index('uq_documents_name_lower', 'documents', [sa.text('lower(name)')], unique=True)
    op.create_index('uq_documents_short_name_lower', 'documents', [sa.text('lower(short_name)')], unique=True)

    _association_table('ticket_documents', 'ticket_id', 'tickets')
    _association_table('appointment_documents', 'appointment_id', 'appointments')

    op.bulk_insert(documents, [
        {"short_name": short, "name": name, "display_order": order, "is_active": True}
        for order, (short, name) in enumerate(SEED_DOCUMENTS, start=1)
    ])

    op.execute(BACKFILL_TICKETS)
    op.execute(BACKFILL_APPOINTMENTS)


def downgrade() -> None:
    op.execute(sa.text(
        "UPDATE tickets SET document_type = ("
        " SELECT td.short_name FROM ticket_documents td"
        " WHERE td.ticket_id = tickets.id ORDER BY td.position LIMIT 1)"
        " WHERE document_type IS NULL"
        " AND EXISTS (SELECT 1 FROM ticket_documents td WHERE td.ticket_id = tickets.id)"
    ))
    op.execute(sa.text(
        "UPDATE appointments SET document_type = ("
        " SELECT ad.short_name FROM appointment_documents ad"
        " WHERE ad.appointment_id = appointments.id ORDER BY ad.position LIMIT 1)"
        " WHERE document_type IS NULL"
        " AND EXISTS (SELECT 1 FROM appointment_documents ad WHERE ad.appointment_id = appointments.id)"
    ))

    op.drop_index(op.f('ix_appointment_documents_document_id'), table_name='appointment_documents')
    op.drop_table('appointment_documents')
    op.drop_index(op.f('ix_ticket_documents_document_id'), table_name='ticket_documents')
    op.drop_table('ticket_documents')
    op.drop_index('uq_documents_short_name_lower', table_name='documents')
    op.drop_index('uq_documents_name_lower', table_name='documents')
    op.drop_index(op.f('ix_documents_id'), table_name='documents')
    op.drop_table('documents')
