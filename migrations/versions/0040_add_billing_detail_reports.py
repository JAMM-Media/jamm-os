# migrations/versions/0040_add_billing_detail_reports.py

"""add_billing_detail_reports

Revision ID: 0040_add_billing_detail_reports
Revises: 0039_add_complexity_flags_to_engagements
Create Date: 2026-06-05

"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = '0040_add_billing_detail_reports'
down_revision: Union[str, Sequence[str], None] = '0039_add_complexity_flags_to_engagements'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'billing_detail_reports',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('firm_id', sa.UUID(), nullable=False),
        sa.Column('client_id', sa.UUID(), nullable=False),
        sa.Column('created_by', sa.UUID(), nullable=False),
        sa.Column('date_from', sa.Date(), nullable=True),
        sa.Column('date_to', sa.Date(), nullable=True),
        sa.Column('engagement_id', sa.UUID(), nullable=True),
        sa.Column('entries', JSONB(), nullable=False, server_default='[]'),
        sa.Column('total_hours', sa.Numeric(10, 2), nullable=False),
        sa.Column('total_amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['firm_id'], ['firms.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['engagement_id'], ['engagements.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_billing_detail_reports_firm_id', 'billing_detail_reports', ['firm_id'])
    op.create_index('ix_billing_detail_reports_client_id', 'billing_detail_reports', ['client_id'])


def downgrade() -> None:
    op.drop_index('ix_billing_detail_reports_client_id', table_name='billing_detail_reports')
    op.drop_index('ix_billing_detail_reports_firm_id', table_name='billing_detail_reports')
    op.drop_table('billing_detail_reports')
