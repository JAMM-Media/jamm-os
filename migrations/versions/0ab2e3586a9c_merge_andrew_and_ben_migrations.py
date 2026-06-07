"""merge_andrew_and_ben_migrations

Revision ID: 0ab2e3586a9c
Revises: 0049_integration_firm_disabled, 0050_add_morning_briefing_preset
Create Date: 2026-06-07 15:45:07.947473

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0ab2e3586a9c'
down_revision: Union[str, Sequence[str], None] = ('0049_integration_firm_disabled', '0050_add_morning_briefing_preset')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
