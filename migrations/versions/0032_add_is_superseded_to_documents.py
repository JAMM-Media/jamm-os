"""add is_superseded to documents

Revision ID: 0032_add_is_superseded_to_documents
Revises: 0031_add_is_active_to_tax_organizer_templates
Create Date: 2026-05-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0032_add_is_superseded_to_documents'
down_revision: Union[str, None] = '0031_add_is_active_to_tax_organizer_templates'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'documents',
        sa.Column('is_superseded', sa.Boolean(), nullable=False, server_default='false'),
    )


def downgrade() -> None:
    op.drop_column('documents', 'is_superseded')
