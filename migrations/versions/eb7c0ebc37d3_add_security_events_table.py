"""add_security_events_table

Revision ID: eb7c0ebc37d3
Revises: 0039_add_complexity_flags_to_engagements
Create Date: 2026-06-05 14:06:25.001886

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'eb7c0ebc37d3'
down_revision: Union[str, Sequence[str], None] = '0039_add_complexity_flags_to_engagements'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'security_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('firm_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('event_type', sa.String(100), nullable=False),
        sa.Column('pattern_matched', sa.String(500), nullable=True),
        sa.Column('content_preview', sa.Text(), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    op.create_index('ix_security_events_firm_id', 'security_events', ['firm_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_security_events_firm_id', table_name='security_events')
    op.drop_table('security_events')
