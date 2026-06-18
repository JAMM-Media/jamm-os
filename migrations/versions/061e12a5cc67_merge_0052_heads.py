"""merge_0052_heads

Revision ID: 061e12a5cc67
Revises: 0052_add_esign_reminder_state_columns, 0052_set_concierge_active_default_true
Create Date: 2026-06-18 18:07:39.253835

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '061e12a5cc67'
down_revision: Union[str, Sequence[str], None] = ('0052_add_esign_reminder_state_columns', '0052_set_concierge_active_default_true')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
