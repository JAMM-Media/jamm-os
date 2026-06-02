"""add qc checklist tables

Revision ID: 0034_add_qc_checklist_tables
Revises: 0033_add_document_expiries_table
Create Date: 2026-05-23

"""
from alembic import op
import sqlalchemy as sa

revision = '0034_add_qc_checklist_tables'
down_revision = '0033_add_document_expiries_table'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'qc_checklist_templates',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('firm_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('engagement_type', sa.String(50), nullable=True),
        sa.Column('items', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['firm_id'], ['firms.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_qc_checklist_templates_firm_id',
        'qc_checklist_templates', ['firm_id']
    )

    op.create_table(
        'qc_checklist_items',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('firm_id', sa.UUID(), nullable=False),
        sa.Column('engagement_id', sa.UUID(), nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('is_checked', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('checked_by_id', sa.UUID(), nullable=True),
        sa.Column('checked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_from_template', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['firm_id'], ['firms.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['engagement_id'], ['engagements.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['checked_by_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_qc_checklist_items_firm_id',
        'qc_checklist_items', ['firm_id']
    )
    op.create_index(
        'ix_qc_checklist_items_engagement_id',
        'qc_checklist_items', ['engagement_id']
    )


def downgrade():
    op.drop_index('ix_qc_checklist_items_engagement_id',
                  table_name='qc_checklist_items')
    op.drop_index('ix_qc_checklist_items_firm_id',
                  table_name='qc_checklist_items')
    op.drop_table('qc_checklist_items')
    op.drop_index('ix_qc_checklist_templates_firm_id',
                  table_name='qc_checklist_templates')
    op.drop_table('qc_checklist_templates')
