# migrations/versions/0049_add_briefing_sent_at_to_firms.py

"""add_briefing_sent_at_to_firms

Revision ID: 0049_add_briefing_sent_at_to_firms
Revises: 0048_user_calendar_settings
Create Date: 2026-06-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0049_add_briefing_sent_at_to_firms'
down_revision: Union[str, Sequence[str], None] = '0048_user_calendar_settings'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('firms', sa.Column('briefing_sent_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('firms', 'briefing_sent_at')
