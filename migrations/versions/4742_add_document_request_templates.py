"""add document_request_templates table

Revision ID: 4742add_document_request_templates
Revises: f7e6d5c4b3a2
Create Date: 2026-09-14

"""
from alembic import op
import sqlalchemy as sa

revision = '4742add_document_request_templates'
down_revision = 'f7e6d5c4b3a2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'document_request_templates',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('firm_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('engagement_type', sa.String(length=100), nullable=False),
        sa.Column('title_default', sa.String(length=300), nullable=True),
        sa.Column('items', sa.JSON(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('use_count', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['firm_id'], ['firms.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint('true', name='ck_document_request_templates_items_is_list'),
    )
    op.create_index(
        'ix_document_request_templates_firm_id',
        'document_request_templates',
        ['firm_id'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_document_request_templates_firm_id', table_name='document_request_templates')
    op.drop_table('document_request_templates')
