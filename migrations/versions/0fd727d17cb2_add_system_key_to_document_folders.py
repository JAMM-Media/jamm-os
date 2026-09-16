# migrations/versions/0fd727d17cb2_add_system_key_to_document_folders.py
"""add system_key to document_folders

Revision ID: 0fd727d17cb2
Revises: 4f66ab6bde66
Create Date: 2026-09-16 08:35:48.276472

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0fd727d17cb2'
down_revision: Union[str, Sequence[str], None] = '4f66ab6bde66'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('document_folders', sa.Column('system_key', sa.String(length=50), nullable=True))
    op.create_index('ix_document_folders_system_key', 'document_folders', ['system_key'], unique=False)
    op.create_index(
        'ux_document_folders_engagement_system_key',
        'document_folders',
        ['engagement_id', 'system_key'],
        unique=True,
        postgresql_where=sa.text('system_key IS NOT NULL AND deleted_at IS NULL'),
    )

    # Backfill: set system_key='pbc' on the single earliest-created live
    # root-level engagement-scoped folder named 'Provided by Client (PBC)'
    # for each engagement. DISTINCT ON picks the earliest when duplicates
    # exist so the unique index cannot fail.
    op.execute(sa.text("""
        UPDATE document_folders
        SET system_key = 'pbc'
        WHERE id IN (
            SELECT DISTINCT ON (engagement_id) id
            FROM document_folders
            WHERE name = 'Provided by Client (PBC)'
              AND deleted_at IS NULL
              AND parent_folder_id IS NULL
              AND scope = 'engagement'
            ORDER BY engagement_id, created_at ASC
        )
    """))


def downgrade() -> None:
    op.drop_index('ux_document_folders_engagement_system_key', table_name='document_folders')
    op.drop_index('ix_document_folders_system_key', table_name='document_folders')
    op.drop_column('document_folders', 'system_key')
