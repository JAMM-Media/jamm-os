"""0042_merge_heads

Revision ID: a72f5a2701c1
Revises: 0041_engagement_efiled_fields, eb7c0ebc37d3
Create Date: 2026-06-05 21:11:37.175775

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a72f5a2701c1'
down_revision: Union[str, Sequence[str], None] = ('0041_engagement_efiled_fields', 'eb7c0ebc37d3')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
