"""0033_add_document_expiries_table

Revision ID: 0033_add_document_expiries_table
Revises: 0032_add_is_superseded_to_documents
Create Date: 2026-05-23

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0033_add_document_expiries_table'
down_revision: Union[str, Sequence[str], None] = '0032_add_is_superseded_to_documents'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'document_expiries',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('firm_id', sa.UUID(), nullable=False),
        sa.Column('client_id', sa.UUID(), nullable=False),
        sa.Column('document_id', sa.UUID(), nullable=True),
        sa.Column('document_type', sa.String(100), nullable=False),
        sa.Column('description', sa.String(255), nullable=True),
        sa.Column('expires_on', sa.Date(), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='active'),
        sa.Column('expiry_notification_sent', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['firm_id'], ['firms.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_document_expiries_firm_id', 'document_expiries', ['firm_id'])
    op.create_index('ix_document_expiries_client_id', 'document_expiries', ['client_id'])
    op.create_index('ix_document_expiries_document_id', 'document_expiries', ['document_id'])


def downgrade() -> None:
    op.drop_index('ix_document_expiries_document_id', table_name='document_expiries')
    op.drop_index('ix_document_expiries_client_id', table_name='document_expiries')
    op.drop_index('ix_document_expiries_firm_id', table_name='document_expiries')
    op.drop_table('document_expiries')
