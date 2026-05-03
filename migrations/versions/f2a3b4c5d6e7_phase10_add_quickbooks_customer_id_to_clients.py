"""phase10_add_quickbooks_customer_id_to_clients

Revision ID: f2a3b4c5d6e7
Revises: e9f1a2b3c4d5
Create Date: 2026-04-03 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'f2a3b4c5d6e7'
down_revision = 'e9f1a2b3c4d5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('clients', sa.Column('quickbooks_customer_id', sa.String(), nullable=True))
    op.create_index('ix_clients_quickbooks_customer_id', 'clients', ['quickbooks_customer_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_clients_quickbooks_customer_id', table_name='clients')
    op.drop_column('clients', 'quickbooks_customer_id')
