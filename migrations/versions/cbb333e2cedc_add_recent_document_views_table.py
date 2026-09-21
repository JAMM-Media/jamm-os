"""add recent_document_views table

Revision ID: cbb333e2cedc
Revises: 4e1768d22b34
Create Date: 2026-09-21 15:04:00.000000

Per-user, per-document fast-read projection for the recent files UI.
One row per (user_id, document_id) pair, upserted on each qualifying
interaction (preview or download). Scoped to a single engagement.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'cbb333e2cedc'
down_revision: Union[str, Sequence[str], None] = '4e1768d22b34'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'recent_document_views',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('firm_id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('engagement_id', sa.Uuid(), nullable=False),
        sa.Column('document_id', sa.Uuid(), nullable=False),
        sa.Column('last_viewed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['engagement_id'], ['engagements.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['firm_id'], ['firms.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'document_id', name='uq_recent_view_user_document'),
    )
    op.create_index(
        op.f('ix_recent_document_views_document_id'),
        'recent_document_views', ['document_id'], unique=False,
    )
    op.create_index(
        op.f('ix_recent_document_views_engagement_id'),
        'recent_document_views', ['engagement_id'], unique=False,
    )
    op.create_index(
        op.f('ix_recent_document_views_firm_id'),
        'recent_document_views', ['firm_id'], unique=False,
    )
    op.create_index(
        'ix_recent_document_views_firm_user_eng_ts',
        'recent_document_views',
        ['firm_id', 'user_id', 'engagement_id', 'last_viewed_at'],
        unique=False,
    )
    op.create_index(
        op.f('ix_recent_document_views_user_id'),
        'recent_document_views', ['user_id'], unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_recent_document_views_firm_user_eng_ts', table_name='recent_document_views')
    op.drop_index(op.f('ix_recent_document_views_user_id'), table_name='recent_document_views')
    op.drop_index(op.f('ix_recent_document_views_firm_id'), table_name='recent_document_views')
    op.drop_index(op.f('ix_recent_document_views_engagement_id'), table_name='recent_document_views')
    op.drop_index(op.f('ix_recent_document_views_document_id'), table_name='recent_document_views')
    op.drop_table('recent_document_views')
