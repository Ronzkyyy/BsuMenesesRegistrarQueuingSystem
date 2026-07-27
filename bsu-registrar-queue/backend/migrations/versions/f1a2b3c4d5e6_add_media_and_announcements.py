"""add media_items and announcements tables

Revision ID: f1a2b3c4d5e6
Revises: e9008ead09e5
Create Date: 2026-07-27 00:00:00.000000

These two tables already exist in local dev databases but were never
captured by an Alembic migration - added here so `alembic upgrade head`
can create them from scratch (e.g. on a new environment like Supabase).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, None] = 'e9008ead09e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'media_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('media_type', sa.Enum('IMAGE', 'VIDEO', name='mediadbtype'), nullable=False),
        sa.Column('url', sa.String(), nullable=False),
        sa.Column('source', sa.Enum('UPLOAD', 'LINK', name='mediadbsource'), nullable=False, default='LINK'),
        sa.Column('display_duration_seconds', sa.Integer(), nullable=True, default=10),
        sa.Column('display_order', sa.Integer(), nullable=True, default=0),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_media_items_id'), 'media_items', ['id'], unique=False)

    op.create_table(
        'announcements',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('display_order', sa.Integer(), nullable=True, default=0),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_announcements_id'), 'announcements', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_announcements_id'), table_name='announcements')
    op.drop_table('announcements')

    op.drop_index(op.f('ix_media_items_id'), table_name='media_items')
    op.drop_table('media_items')
