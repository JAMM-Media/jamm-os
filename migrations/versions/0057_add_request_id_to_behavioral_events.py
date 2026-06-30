# migrations/versions/0057_add_request_id_to_behavioral_events.py

"""add request_id to behavioral_events

Revision ID: 0057_add_request_id_to_behavioral_events
Revises: 0056_add_current_session_jti_to_users
Create Date: 2026-06-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0057_add_request_id_to_behavioral_events'
down_revision: Union[str, Sequence[str], None] = '0056_add_current_session_jti_to_users'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'behavioral_events',
        sa.Column('request_id', sa.UUID(), nullable=True),
    )
    op.create_index(
        'ix_behavioral_events_request_id',
        'behavioral_events',
        ['request_id'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_behavioral_events_request_id', table_name='behavioral_events')
    op.drop_column('behavioral_events', 'request_id')
