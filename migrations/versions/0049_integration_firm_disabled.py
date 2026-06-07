# migrations/versions/0049_integration_firm_disabled.py

"""integration firm disabled

Revision ID: 0049_integration_firm_disabled
Revises: 0048_user_calendar_settings
Create Date: 2026-06-07
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0049_integration_firm_disabled'
down_revision: Union[str, Sequence[str], None] = '0048_user_calendar_settings'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'integrations',
        sa.Column('firm_disabled', sa.Boolean(), nullable=False, server_default='false'),
    )


def downgrade() -> None:
    op.drop_column('integrations', 'firm_disabled')
