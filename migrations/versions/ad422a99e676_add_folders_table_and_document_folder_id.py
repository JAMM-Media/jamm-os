"""add_folders_table_and_document_folder_id

Revision ID: ad422a99e676
Revises: c3a8c478ba34
Create Date: 2026-08-21 12:47:54.718316

Adds the folders table (firm-controlled named containers for client documents)
and a nullable folder_id FK on documents. Documents with folder_id = NULL live
at root level. Deleting a folder sets folder_id to NULL on contained documents
and parent_folder_id to NULL on child folders via ondelete="SET NULL" at the DB
level -- no documents or child folders are ever deleted when a folder is removed.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'ad422a99e676'
down_revision: Union[str, Sequence[str], None] = 'c3a8c478ba34'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'folders',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('firm_id', sa.Uuid(), nullable=False),
        sa.Column('client_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('parent_folder_id', sa.Uuid(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['firm_id'], ['firms.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(
            ['parent_folder_id'], ['folders.id'],
            name='fk_folders_parent_folder_id',
            ondelete='SET NULL',
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_folders_client_id', 'folders', ['client_id'], unique=False)
    op.create_index('ix_folders_firm_id', 'folders', ['firm_id'], unique=False)
    op.create_index('ix_folders_parent_folder_id', 'folders', ['parent_folder_id'], unique=False)

    op.add_column('documents', sa.Column('folder_id', sa.Uuid(), nullable=True))
    op.create_index('ix_documents_folder_id', 'documents', ['folder_id'], unique=False)
    op.create_foreign_key(
        'fk_documents_folder_id',
        'documents', 'folders',
        ['folder_id'], ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint('fk_documents_folder_id', 'documents', type_='foreignkey')
    op.drop_index('ix_documents_folder_id', table_name='documents')
    op.drop_column('documents', 'folder_id')

    op.drop_index('ix_folders_parent_folder_id', table_name='folders')
    op.drop_index('ix_folders_firm_id', table_name='folders')
    op.drop_index('ix_folders_client_id', table_name='folders')
    op.drop_table('folders')
