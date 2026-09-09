# migrations/versions/c1d2e3f4a5b6_reroute_documents_folder_id_to_document_folders.py
"""Reroute documents.folder_id FK to document_folders

Revision ID: c1d2e3f4a5b6
Revises: c0d1e2f3a4b5
Create Date: 2026-09-09

The fk_documents_folder_id constraint on documents.folder_id was originally
created pointing to the old portal folders table. Phase 1 introduced
document_folders as the authoritative filing table. Phase 4 Task 2 (move, copy)
requires setting folder_id to document_folders.id. This migration re-points
the FK from folders to document_folders so writes succeed.

The old folders table is NOT dropped; it remains in service for the portal.
The documents table no longer writes new folder assignments to it.
"""

from alembic import op

revision = 'c1d2e3f4a5b6'
down_revision = 'c0d1e2f3a4b5'
branch_labels = None
depends_on = None


def upgrade():
    # Null out any existing folder_id values that reference folders (not document_folders).
    # This is a REAL safety net, not a hypothetical one: a direct query of the dev database
    # found two documents with folder_id set (the demo portal client's W-2 and bank statement
    # PDFs). Those two rows were NOT nulled because Phase 1's migration copied folder rows
    # from 'folders' into 'document_folders' with the same UUIDs, so the UUIDs already
    # existed in document_folders. However, a database that ran Phase 1 before any portal
    # folders were created (or that added new portal folders after Phase 1) would have
    # folder_id values that exist only in 'folders' and NOT in 'document_folders' -- those
    # rows WOULD be nulled here, silently losing their folder assignment. This UUID
    # coincidence is not a guarantee; it is an accident of migration order.
    op.execute(
        "UPDATE documents SET folder_id = NULL "
        "WHERE folder_id IS NOT NULL "
        "AND folder_id NOT IN (SELECT id FROM document_folders)"
    )
    op.drop_constraint('fk_documents_folder_id', 'documents', type_='foreignkey')
    op.create_foreign_key(
        'fk_documents_folder_id',
        'documents', 'document_folders',
        ['folder_id'], ['id'],
        ondelete='SET NULL',
    )


def downgrade():
    op.drop_constraint('fk_documents_folder_id', 'documents', type_='foreignkey')
    op.create_foreign_key(
        'fk_documents_folder_id',
        'documents', 'folders',
        ['folder_id'], ['id'],
        ondelete='SET NULL',
    )
