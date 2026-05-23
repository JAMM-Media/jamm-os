"""add engagement_templates table

Revision ID: 0030_add_engagement_templates
Revises: 0029_add_timesheet_approval_to_firms
Create Date: 2026-05-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0030_add_engagement_templates'
down_revision: Union[str, Sequence[str], None] = '0029_add_timesheet_approval_to_firms'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'engagement_templates',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('firm_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('engagement_type', sa.String(100), nullable=True),
        sa.Column('estimated_hours', sa.Numeric(6, 2), nullable=True),
        sa.Column('task_templates', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('document_checklist', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('use_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['firm_id'], ['firms.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_engagement_templates_firm_id', 'engagement_templates', ['firm_id'])


def downgrade() -> None:
    op.drop_index('ix_engagement_templates_firm_id', table_name='engagement_templates')
    op.drop_table('engagement_templates')
