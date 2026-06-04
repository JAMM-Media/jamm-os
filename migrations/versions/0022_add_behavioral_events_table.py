"""add behavioral_events table

Revision ID: 0022_add_behavioral_events_table
Revises: 0021_portal_magic_link_fields
Create Date: 2026-04-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0022_add_behavioral_events_table'
down_revision: Union[str, Sequence[str], None] = '0021_portal_magic_link_fields'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'behavioral_events',
        sa.Column('event_id', sa.Uuid(), nullable=False),
        sa.Column('firm_id', sa.Uuid(), nullable=False),
        sa.Column('event_type', sa.String(length=100), nullable=False),
        sa.Column('entity_type', sa.String(length=50), nullable=True),
        sa.Column('entity_id', sa.Uuid(), nullable=True),
        sa.Column('actor_type', sa.String(length=20), nullable=True),
        sa.Column('actor_id', sa.Uuid(), nullable=True),
        sa.Column(
            'occurred_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('session_id', sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(['firm_id'], ['firms.id']),
        sa.PrimaryKeyConstraint('event_id'),
    )
    op.create_index(
        op.f('ix_behavioral_events_event_type'),
        'behavioral_events',
        ['event_type'],
        unique=False,
    )
    op.create_index(
        op.f('ix_behavioral_events_firm_id'),
        'behavioral_events',
        ['firm_id'],
        unique=False,
    )
    op.create_index(
        'ix_behavioral_events_firm_type_time',
        'behavioral_events',
        ['firm_id', 'event_type', 'occurred_at'],
        unique=False,
    )
    op.create_index(
        op.f('ix_behavioral_events_occurred_at'),
        'behavioral_events',
        ['occurred_at'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_behavioral_events_firm_type_time', table_name='behavioral_events')
    op.drop_index(op.f('ix_behavioral_events_occurred_at'), table_name='behavioral_events')
    op.drop_index(op.f('ix_behavioral_events_firm_id'), table_name='behavioral_events')
    op.drop_index(op.f('ix_behavioral_events_event_type'), table_name='behavioral_events')
    op.drop_table('behavioral_events')
