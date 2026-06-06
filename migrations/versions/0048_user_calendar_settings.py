# migrations/versions/0048_user_calendar_settings.py

"""user calendar settings

Revision ID: 0048_user_calendar_settings
Revises: 0047_per_staff_integrations
Create Date: 2026-06-06
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0048_user_calendar_settings'
down_revision: Union[str, Sequence[str], None] = '0047_per_staff_integrations'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('calendar_settings', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        'firms',
        sa.Column('staff_calendar_colors', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('firms', 'staff_calendar_colors')
    op.drop_column('users', 'calendar_settings')
