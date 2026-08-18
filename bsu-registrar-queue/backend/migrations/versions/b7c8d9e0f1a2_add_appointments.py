"""add appointments table and queue booking settings

Revision ID: b7c8d9e0f1a2
Revises: a1b2c3d4e5f6
Create Date: 2026-08-18 00:00:00.000000

Adds the appointments table (QR-based booking, checked in at the registrar
counter to auto-create a queue ticket) and five new booking-config columns
on queues, all additive and defaulted so existing queues/rows are unaffected
until an admin explicitly enables booking on a given queue.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7c8d9e0f1a2'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('queues', sa.Column('booking_enabled', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    op.add_column('queues', sa.Column('operating_start_time', sa.Time(), nullable=False, server_default='08:00:00'))
    op.add_column('queues', sa.Column('operating_end_time', sa.Time(), nullable=False, server_default='17:00:00'))
    op.add_column('queues', sa.Column('slot_capacity', sa.Integer(), nullable=False, server_default='3'))
    op.add_column('queues', sa.Column('booking_window_days', sa.Integer(), nullable=False, server_default='14'))

    op.create_table(
        'appointments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('reference_code', sa.String(length=20), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('queue_id', sa.Integer(), nullable=False),
        sa.Column('appointment_date', sa.Date(), nullable=False),
        sa.Column('slot_start_time', sa.Time(), nullable=False),
        sa.Column('slot_end_time', sa.Time(), nullable=False),
        sa.Column('purpose', sa.Text(), nullable=True),
        sa.Column('qr_token', sa.String(length=64), nullable=False),
        sa.Column('status', sa.Enum('BOOKED', 'CHECKED_IN', 'CANCELLED', 'EXPIRED', name='appointmentdbstatus'), nullable=False),
        sa.Column('checked_in_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('checked_in_by', sa.Integer(), nullable=True),
        sa.Column('ticket_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['student_id'], ['students.id']),
        sa.ForeignKeyConstraint(['queue_id'], ['queues.id']),
        sa.ForeignKeyConstraint(['checked_in_by'], ['users.id']),
        sa.ForeignKeyConstraint(['ticket_id'], ['tickets.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('reference_code'),
        sa.UniqueConstraint('qr_token'),
    )
    op.create_index(op.f('ix_appointments_id'), 'appointments', ['id'], unique=False)
    op.create_index(op.f('ix_appointments_reference_code'), 'appointments', ['reference_code'], unique=True)
    op.create_index(op.f('ix_appointments_qr_token'), 'appointments', ['qr_token'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_appointments_qr_token'), table_name='appointments')
    op.drop_index(op.f('ix_appointments_reference_code'), table_name='appointments')
    op.drop_index(op.f('ix_appointments_id'), table_name='appointments')
    op.drop_table('appointments')
    op.execute('DROP TYPE IF EXISTS appointmentdbstatus')

    op.drop_column('queues', 'booking_window_days')
    op.drop_column('queues', 'slot_capacity')
    op.drop_column('queues', 'operating_end_time')
    op.drop_column('queues', 'operating_start_time')
    op.drop_column('queues', 'booking_enabled')
