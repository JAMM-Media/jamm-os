"""add_dismissed_at_to_concierge_notifications

Revision ID: 974b9b98dce6
Revises: 6554befeb11b
Create Date: 2026-06-03 15:46:40.375399

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '974b9b98dce6'
down_revision: Union[str, Sequence[str], None] = '6554befeb11b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'concierge_notifications',
        sa.Column('dismissed_at', sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('concierge_notifications', 'dismissed_at')
