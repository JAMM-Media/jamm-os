"""add source_item_id to document_template_statuses

Revision ID: cb70823479d3
Revises: eb8d785ffb8c
Create Date: 2026-09-23 10:47:19.336288

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'cb70823479d3'
down_revision: Union[str, Sequence[str], None] = 'eb8d785ffb8c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'document_template_statuses',
        sa.Column('source_item_id', sa.Uuid(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('document_template_statuses', 'source_item_id')