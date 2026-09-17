"""add sidebar_expand_mode to users

Revision ID: 27b043fa7aa2
Revises: 375e6bdc8287
Create Date: 2026-09-17 09:55:04.519028

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '27b043fa7aa2'
down_revision: Union[str, Sequence[str], None] = '375e6bdc8287'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('sidebar_expand_mode', sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'sidebar_expand_mode')
