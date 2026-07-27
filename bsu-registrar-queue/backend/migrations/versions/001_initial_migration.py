"""Initial migration - create all tables

Revision ID: 001
Revises:
Create Date: 2024-01-15 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(length=50), nullable=False),
        sa.Column('full_name', sa.String(length=100), nullable=False),
        sa.Column('role', sa.Enum('ADMIN', 'REGISTRAR', 'STAFF', name='userrole'), nullable=False),
        sa.Column('hashed_password', sa.String(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('username')
    )
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)

    # Create queues table
    op.create_table(
        'queues',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('queue_type', sa.Enum('ENROLLMENT', 'DOCUMENT_REQUEST', 'CLEARANCE', 'SCHOLARSHIP', 'OTHERS', name='queuedbtype'), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.Enum('ACTIVE', 'PAUSED', 'CLOSED', name='queuedbstatus'), nullable=False, default='ACTIVE'),
        sa.Column('allow_priority', sa.Boolean(), nullable=False, default=True),
        sa.Column('max_capacity', sa.Integer(), nullable=False, default=50),
        sa.Column('slot_duration_minutes', sa.Integer(), nullable=False, default=30),
        sa.Column('current_ticket_number', sa.Integer(), nullable=False, default=0),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_queues_id'), 'queues', ['id'], unique=False)

    # Create students table
    op.create_table(
        'students',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('student_id', sa.String(length=20), nullable=False),
        sa.Column('first_name', sa.String(length=50), nullable=False),
        sa.Column('last_name', sa.String(length=50), nullable=False),
        sa.Column('email', sa.String(length=100), nullable=True),
        sa.Column('student_type', sa.Enum('UNDERGRADUATE', 'GRADUATE', 'ALUMNI', name='studentdbtype'), nullable=False),
        sa.Column('college', sa.Enum('CAS', 'CBA', 'CEA', 'COE', 'CHS', 'CHT', 'OTHER', name='college'), nullable=False),
        sa.Column('year_level', sa.Enum('FIRST', 'SECOND', 'THIRD', 'FOURTH', 'FIFTH', 'GRADUATE', name='yearlevel'), nullable=False),
        sa.Column('is_scholar', sa.Boolean(), nullable=False, default=False),
        sa.Column('is_varsity', sa.Boolean(), nullable=False, default=False),
        sa.Column('is_graduating', sa.Boolean(), nullable=False, default=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('student_id')
    )
    op.create_index(op.f('ix_students_id'), 'students', ['id'], unique=False)
    op.create_index(op.f('ix_students_student_id'), 'students', ['student_id'], unique=True)

    # Create tickets table
    op.create_table(
        'tickets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('ticket_number', sa.Integer(), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('queue_id', sa.Integer(), nullable=False),
        sa.Column('priority', sa.Enum('NORMAL', 'PRIORITY', 'URGENT', name='prioritylevel'), nullable=False, default='NORMAL'),
        sa.Column('purpose', sa.Text(), nullable=True),
        sa.Column('status', sa.Enum('WAITING', 'SERVING', 'COMPLETED', 'CANCELLED', 'NO_SHOW', name='ticketdbstatus'), nullable=False, default='WAITING'),
        sa.Column('position', sa.Integer(), nullable=True),
        sa.Column('estimated_wait_time_minutes', sa.Integer(), nullable=True),
        sa.Column('served_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['queue_id'], ['queues.id'], ),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_tickets_id'), 'tickets', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_tickets_id'), table_name='tickets')
    op.drop_table('tickets')

    op.drop_index(op.f('ix_students_student_id'), table_name='students')
    op.drop_index(op.f('ix_students_id'), table_name='students')
    op.drop_table('students')

    op.drop_index(op.f('ix_queues_id'), table_name='queues')
    op.drop_table('queues')

    op.drop_index(op.f('ix_users_username'), table_name='users')
    op.drop_index(op.f('ix_users_id'), table_name='users')
    op.drop_table('users')