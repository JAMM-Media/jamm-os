# migrations/versions/0310a1b5d296_add_calendar_categories_and_calendar_events.py
"""add calendar categories and calendar events

Revision ID: 0310a1b5d296
Revises: 1dbec4aebadd
Create Date: 2026-10-02 09:16:03.113161

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0310a1b5d296'
down_revision: Union[str, Sequence[str], None] = '1dbec4aebadd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'calendar_categories',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('firm_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('color', sa.String(length=7), nullable=False),
        sa.Column('sort_order', sa.Integer(), server_default='0', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['firm_id'], ['firms.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('firm_id', 'name', name='uq_calendar_categories_firm_name'),
    )
    op.create_index(
        op.f('ix_calendar_categories_firm_id'),
        'calendar_categories', ['firm_id'], unique=False,
    )
    op.create_table(
        'calendar_events',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('firm_id', sa.Uuid(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('start_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('end_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('event_timezone', sa.String(length=100), nullable=False),
        sa.Column('category_id', sa.Uuid(), nullable=True),
        sa.Column('client_id', sa.Uuid(), nullable=True),
        sa.Column('owner_user_id', sa.Uuid(), nullable=True),
        sa.Column('created_by', sa.Uuid(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('end_at > start_at', name='ck_calendar_events_end_after_start'),
        sa.ForeignKeyConstraint(['category_id'], ['calendar_categories.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['firm_id'], ['firms.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['owner_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_calendar_events_firm_id'),
        'calendar_events', ['firm_id'], unique=False,
    )
    op.create_index(
        'ix_calendar_events_firm_start',
        'calendar_events', ['firm_id', 'start_at'], unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_calendar_events_firm_start', table_name='calendar_events')
    op.drop_index(op.f('ix_calendar_events_firm_id'), table_name='calendar_events')
    op.drop_table('calendar_events')
    op.drop_index(op.f('ix_calendar_categories_firm_id'), table_name='calendar_categories')
    op.drop_table('calendar_categories')
