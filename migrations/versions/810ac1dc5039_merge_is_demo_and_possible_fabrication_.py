"""merge is_demo and possible_fabrication branches

Revision ID: 810ac1dc5039
Revises: 880cc433906e, k1l2m3n4o5p6
Create Date: 2026-07-22 19:14:19.570878

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '810ac1dc5039'
down_revision: Union[str, Sequence[str], None] = ('880cc433906e', 'k1l2m3n4o5p6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
