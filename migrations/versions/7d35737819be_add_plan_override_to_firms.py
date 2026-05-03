"""add_plan_override_to_firms

Revision ID: 7d35737819be
Revises: 0024_auth_overhaul
Create Date: 2026-04-27 11:05:30.789585

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7d35737819be'
down_revision: Union[str, Sequence[str], None] = '0024_auth_overhaul'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('firms', sa.Column('plan_override', sa.Boolean(), nullable=False, server_default=sa.text('false')))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('firms', 'plan_override')
