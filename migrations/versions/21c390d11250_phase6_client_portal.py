"""phase6_client_portal

Revision ID: 21c390d11250
Revises: 5c84a38f17ce
Create Date: 2026-03-29

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '21c390d11250'
down_revision: Union[str, Sequence[str], None] = '5c84a38f17ce'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- New columns on clients table ---
    op.add_column('clients', sa.Column('portal_password_hash', sa.String(), nullable=True))
    op.add_column('clients', sa.Column('portal_invite_token', sa.String(), nullable=True))
    op.add_column('clients', sa.Column('portal_invite_sent_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('clients', sa.Column('portal_access_enabled', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('clients', sa.Column('portal_last_login_at', sa.DateTime(timezone=True), nullable=True))

    # --- portal_sessions table ---
    op.create_table(
        'portal_sessions',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('firm_id', sa.Uuid(), nullable=False),
        sa.Column('client_id', sa.Uuid(), nullable=False),
        sa.Column('refresh_token_hash', sa.String(), nullable=False),
        sa.Column('access_jti', sa.String(), nullable=False),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_active_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('is_revoked', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoked_by', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['firm_id'], ['firms.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_portal_sessions_firm_id'), 'portal_sessions', ['firm_id'], unique=False)
    op.create_index(op.f('ix_portal_sessions_client_id'), 'portal_sessions', ['client_id'], unique=False)

    # --- portal_notifications table ---
    op.create_table(
        'portal_notifications',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('firm_id', sa.Uuid(), nullable=False),
        sa.Column('client_id', sa.Uuid(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('body', sa.Text(), nullable=True),
        sa.Column('notification_type', sa.String(length=50), nullable=False),
        sa.Column('is_read', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('related_entity_type', sa.String(length=50), nullable=True),
        sa.Column('related_entity_id', sa.Uuid(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['firm_id'], ['firms.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_portal_notifications_firm_id'), 'portal_notifications', ['firm_id'], unique=False)
    op.create_index(op.f('ix_portal_notifications_client_id'), 'portal_notifications', ['client_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_portal_notifications_client_id'), table_name='portal_notifications')
    op.drop_index(op.f('ix_portal_notifications_firm_id'), table_name='portal_notifications')
    op.drop_table('portal_notifications')

    op.drop_index(op.f('ix_portal_sessions_client_id'), table_name='portal_sessions')
    op.drop_index(op.f('ix_portal_sessions_firm_id'), table_name='portal_sessions')
    op.drop_table('portal_sessions')

    op.drop_column('clients', 'portal_last_login_at')
    op.drop_column('clients', 'portal_access_enabled')
    op.drop_column('clients', 'portal_invite_sent_at')
    op.drop_column('clients', 'portal_invite_token')
    op.drop_column('clients', 'portal_password_hash')
