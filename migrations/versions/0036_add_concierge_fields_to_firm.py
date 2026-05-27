# migrations/versions/0036_add_concierge_fields_to_firm.py

"""add_concierge_fields_to_firm

Revision ID: 0036_add_concierge_fields_to_firm
Revises: 0035_recurring_engagements
Create Date: 2026-05-27

"""
from alembic import op
import sqlalchemy as sa

revision = '0036_add_concierge_fields_to_firm'
down_revision = '0035_recurring_engagements'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('firms', sa.Column('concierge_active', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('firms', sa.Column('firm_type', sa.String(30), nullable=True))
    op.add_column('firms', sa.Column('concierge_onboarded', sa.Boolean(), nullable=False, server_default='false'))


def downgrade():
    op.drop_column('firms', 'concierge_onboarded')
    op.drop_column('firms', 'firm_type')
    op.drop_column('firms', 'concierge_active')
