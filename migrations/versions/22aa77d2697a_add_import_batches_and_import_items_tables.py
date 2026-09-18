"""add import batches and import items tables

Revision ID: 22aa77d2697a
Revises: 27b043fa7aa2
Create Date: 2026-09-18 08:44:30.640547

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '22aa77d2697a'
down_revision: Union[str, Sequence[str], None] = '27b043fa7aa2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'import_batches',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('firm_id', sa.Uuid(), nullable=False),
        sa.Column('created_by_user_id', sa.Uuid(), nullable=True),
        sa.Column('scope', sa.String(length=20), nullable=False),
        sa.Column('client_id', sa.Uuid(), nullable=True),
        sa.Column('engagement_id', sa.Uuid(), nullable=True),
        sa.Column('destination_folder_id', sa.Uuid(), nullable=True),
        sa.Column('status', sa.Enum(
            'draft', 'confirmed', 'uploading', 'finalizing', 'completed',
            'completed_with_errors', 'canceled',
            name='importbatchstatus', native_enum=False, length=30,
        ), nullable=False),
        sa.Column('conflict_policy', sa.Enum(
            'skip', 'replace', 'keep_both',
            name='importconflictpolicy', native_enum=False, length=20,
        ), nullable=False),
        sa.Column('total_files', sa.Integer(), nullable=False),
        sa.Column('total_bytes', sa.Integer(), nullable=False),
        sa.Column('completed_files', sa.Integer(), nullable=False),
        sa.Column('failed_files', sa.Integer(), nullable=False),
        sa.Column('skipped_files', sa.Integer(), nullable=False),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "(scope = 'engagement' AND engagement_id IS NOT NULL AND client_id IS NOT NULL)"
            " OR (scope = 'client' AND client_id IS NOT NULL AND engagement_id IS NULL)"
            " OR (scope = 'firm_library' AND client_id IS NULL AND engagement_id IS NULL)",
            name='ck_import_batches_scope_fk_consistency',
        ),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['destination_folder_id'], ['document_folders.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['engagement_id'], ['engagements.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['firm_id'], ['firms.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_import_batches_firm_id'), 'import_batches', ['firm_id'], unique=False)
    op.create_index(op.f('ix_import_batches_client_id'), 'import_batches', ['client_id'], unique=False)
    op.create_index(op.f('ix_import_batches_engagement_id'), 'import_batches', ['engagement_id'], unique=False)
    op.create_index(op.f('ix_import_batches_created_by_user_id'), 'import_batches', ['created_by_user_id'], unique=False)

    op.create_table(
        'import_items',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('import_batch_id', sa.Uuid(), nullable=False),
        sa.Column('firm_id', sa.Uuid(), nullable=False),
        sa.Column('ordinal', sa.Integer(), nullable=False),
        sa.Column('relative_path', sa.Text(), nullable=False),
        sa.Column('normalized_relative_path', sa.Text(), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('expected_bytes', sa.Integer(), nullable=False),
        sa.Column('mime_type', sa.String(length=128), nullable=True),
        sa.Column('status', sa.Enum(
            'planned', 'uploaded', 'processing', 'completed', 'failed', 'skipped', 'retryable',
            name='importitemstatus', native_enum=False, length=20,
        ), nullable=False),
        sa.Column('conflict_override', sa.Enum(
            'skip', 'replace', 'keep_both',
            name='importconflictpolicy', native_enum=False, length=20,
        ), nullable=True),
        sa.Column('attempt_count', sa.Integer(), nullable=False),
        sa.Column('claimed_by', sa.String(length=255), nullable=True),
        sa.Column('lease_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('available_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('staging_s3_key', sa.String(length=512), nullable=True),
        sa.Column('final_document_id', sa.Uuid(), nullable=True),
        sa.Column('final_folder_id', sa.Uuid(), nullable=True),
        sa.Column('error_code', sa.String(length=64), nullable=True),
        sa.Column('error_detail', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['final_document_id'], ['documents.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['final_folder_id'], ['document_folders.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['firm_id'], ['firms.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['import_batch_id'], ['import_batches.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_import_items_import_batch_id'), 'import_items', ['import_batch_id'], unique=False)
    op.create_index(op.f('ix_import_items_firm_id'), 'import_items', ['firm_id'], unique=False)
    op.create_index(op.f('ix_import_items_status'), 'import_items', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_import_items_status'), table_name='import_items')
    op.drop_index(op.f('ix_import_items_firm_id'), table_name='import_items')
    op.drop_index(op.f('ix_import_items_import_batch_id'), table_name='import_items')
    op.drop_table('import_items')
    op.drop_index(op.f('ix_import_batches_created_by_user_id'), table_name='import_batches')
    op.drop_index(op.f('ix_import_batches_engagement_id'), table_name='import_batches')
    op.drop_index(op.f('ix_import_batches_client_id'), table_name='import_batches')
    op.drop_index(op.f('ix_import_batches_firm_id'), table_name='import_batches')
    op.drop_table('import_batches')
