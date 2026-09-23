"""add document_template_status table

Revision ID: eb8d785ffb8c
Revises: b2c3d4e5f6a7
Create Date: 2026-09-22 20:25:47.202662

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'eb8d785ffb8c'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'document_template_statuses',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('firm_id', sa.Uuid(), nullable=False),
        sa.Column('item_type', sa.String(length=20), nullable=False),
        sa.Column('item_id', sa.Uuid(), nullable=False),
        sa.Column(
            'status',
            sa.Enum(
                'vendor_sample', 'firm_draft', 'firm_approved',
                name='templatestatus',
                native_enum=False,
                length=30,
            ),
            nullable=False,
        ),
        sa.Column('published_by', sa.Uuid(), nullable=True),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "item_type IN ('document', 'folder')",
            name='ck_document_template_statuses_item_type',
        ),
        sa.ForeignKeyConstraint(['firm_id'], ['firms.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['published_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'firm_id', 'item_type', 'item_id',
            name='uq_document_template_statuses_firm_item',
        ),
    )
    op.create_index(
        op.f('ix_document_template_statuses_firm_id'),
        'document_template_statuses', ['firm_id'], unique=False,
    )
    op.create_index(
        op.f('ix_document_template_statuses_published_by'),
        'document_template_statuses', ['published_by'], unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f('ix_document_template_statuses_published_by'),
        table_name='document_template_statuses',
    )
    op.drop_index(
        op.f('ix_document_template_statuses_firm_id'),
        table_name='document_template_statuses',
    )
    op.drop_table('document_template_statuses')