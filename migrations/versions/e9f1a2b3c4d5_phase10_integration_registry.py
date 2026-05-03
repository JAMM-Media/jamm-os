"""phase10_integration_registry

Revision ID: e9f1a2b3c4d5
Revises: d1e2f3a4b5c6
Create Date: 2026-04-03 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'e9f1a2b3c4d5'
down_revision = 'd1e2f3a4b5c6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'integrations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('firm_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('provider', sa.String(length=100), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='disconnected'),
        sa.Column('encrypted_access_token', sa.Text(), nullable=True),
        sa.Column('encrypted_refresh_token', sa.Text(), nullable=True),
        sa.Column('token_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('scopes', sa.Text(), nullable=True),
        sa.Column('external_account_id', sa.String(length=255), nullable=True),
        sa.Column('connected_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['firm_id'], ['firms.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('firm_id', 'provider', name='uq_integration_firm_provider'),
    )
    op.create_index('ix_integrations_firm_id', 'integrations', ['firm_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_integrations_firm_id', table_name='integrations')
    op.drop_table('integrations')
