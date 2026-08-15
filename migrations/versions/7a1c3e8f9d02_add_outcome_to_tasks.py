"""add outcome to tasks

Revision ID: 7a1c3e8f9d02
Revises: 40d05d01b360
Create Date: 2026-08-15 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '7a1c3e8f9d02'
down_revision: Union[str, Sequence[str], None] = '40d05d01b360'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('tasks', sa.Column('outcome', sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column('tasks', 'outcome')
