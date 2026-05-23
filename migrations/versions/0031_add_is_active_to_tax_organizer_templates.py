"""add is_active to tax_organizer_templates

Revision ID: 0031_add_is_active_to_tax_organizer_templates
Revises: 0030_add_engagement_templates
Create Date: 2026-05-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0031_add_is_active_to_tax_organizer_templates'
down_revision: Union[str, None] = '0030_add_engagement_templates'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'tax_organizer_templates',
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
    )


def downgrade() -> None:
    op.drop_column('tax_organizer_templates', 'is_active')
