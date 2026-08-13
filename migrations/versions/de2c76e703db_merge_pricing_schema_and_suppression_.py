"""merge pricing schema and suppression branches

Revision ID: de2c76e703db
Revises: h2i3j4k5l6m7, h3i4j5k6l7m8
Create Date: 2026-08-13 16:06:52.197525

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'de2c76e703db'
down_revision: Union[str, Sequence[str], None] = ('h2i3j4k5l6m7', 'h3i4j5k6l7m8')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
