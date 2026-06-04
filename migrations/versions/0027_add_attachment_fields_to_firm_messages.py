"""add attachment fields to firm_messages

Revision ID: 0027_add_attachment_fields_to_firm_messages
Revises: 0026_add_default_actions_to_automation_rules
Create Date: 2026-05-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0027_add_attachment_fields_to_firm_messages'
down_revision: Union[str, Sequence[str], None] = '0026_add_default_actions_to_automation_rules'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('firm_messages', sa.Column('attachment_name', sa.String(length=255), nullable=True))
    op.add_column('firm_messages', sa.Column('attachment_size', sa.Integer(), nullable=True))
    op.add_column('firm_messages', sa.Column('attachment_type', sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column('firm_messages', 'attachment_type')
    op.drop_column('firm_messages', 'attachment_size')
    op.drop_column('firm_messages', 'attachment_name')
