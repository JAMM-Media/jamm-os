"""merge_heads_note_reads_invoice_constraint

Revision ID: 5e549eb005ce
Revises: 0308036ee038, 1343fcca8203
Create Date: 2026-07-09 19:41:46.682379

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5e549eb005ce'
down_revision: Union[str, Sequence[str], None] = ('0308036ee038', '1343fcca8203')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
