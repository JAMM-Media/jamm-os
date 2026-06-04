"""add notes_client_visible to engagements

Revision ID: a1b2c3d4e5f6
Revises: 21c390d11250
Create Date: 2026-03-29

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '21c390d11250'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('engagements', sa.Column('notes_client_visible', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('engagements', 'notes_client_visible')
