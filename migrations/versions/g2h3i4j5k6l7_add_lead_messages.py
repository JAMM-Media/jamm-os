# migrations/versions/g2h3i4j5k6l7_add_lead_messages.py

"""add lead_messages table

Revision ID: g2h3i4j5k6l7
Revises: f2g3h4i5j6k7
Create Date: 2026-08-12

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'g2h3i4j5k6l7'
down_revision: Union[str, Sequence, None] = 'f2g3h4i5j6k7'
branch_labels: Union[str, Sequence, None] = None
depends_on: Union[str, Sequence, None] = None


def upgrade() -> None:
    """Create lead_messages, matching ClientMessage's shape minus read receipts."""
    op.create_table(
        'lead_messages',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('firm_id', sa.Uuid(), nullable=False),
        sa.Column('lead_id', sa.Uuid(), nullable=False),
        sa.Column('sender_id', sa.Uuid(), nullable=True),
        sa.Column('sender_role', sa.String(length=30), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('source', sa.String(length=30), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['firm_id'], ['firms.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['sender_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_lead_messages_firm_id', 'lead_messages', ['firm_id'])
    op.create_index('ix_lead_messages_lead_id', 'lead_messages', ['lead_id'])
    op.create_index('ix_lead_messages_firm_lead', 'lead_messages', ['firm_id', 'lead_id'])


def downgrade() -> None:
    """Drop lead_messages table."""
    op.drop_index('ix_lead_messages_firm_lead', table_name='lead_messages')
    op.drop_index('ix_lead_messages_lead_id', table_name='lead_messages')
    op.drop_index('ix_lead_messages_firm_id', table_name='lead_messages')
    op.drop_table('lead_messages')
