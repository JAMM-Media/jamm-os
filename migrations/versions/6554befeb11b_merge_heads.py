"""merge_heads

Revision ID: 6554befeb11b
Revises: 0038_update_concierge_notifications_schema, j1k2l3m4n5o6
Create Date: 2026-06-03 15:46:05.214501

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6554befeb11b'
down_revision: Union[str, Sequence[str], None] = ('0038_update_concierge_notifications_schema', 'j1k2l3m4n5o6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
