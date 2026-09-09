# migrations/versions/n2o3p4q5r6s7_drop_fk_on_documents_folder_id.py
"""Drop FK constraint on documents.folder_id

Revision ID: n2o3p4q5r6s7
Revises: c1d2e3f4a5b6
Create Date: 2026-09-09

TODO(filesystem-phase-4): documents.folder_id currently has no database-level
FK constraint. It holds a document_folders.id when set by staff-side move/copy
(Phase 4 Task 2) or a folders.id (old portal-era table) when set by the portal
move endpoint. Two different tables, one column, no way to tell which from the
value alone.

This is a deliberate, temporary state. The real fix is migrating the portal's
GET /portal/folders endpoint and PortalDocuments.tsx off the old 'folders' table
and onto 'document_folders' entirely, then dropping 'folders' for good. That
is scoped as its own separate, upcoming task (supersede old folders, D4 decision
made 2026-09-09) and is NOT solved here.

Until that task ships, application-layer checks enforce which table a write
targets:
  - portal move (app/api/portal.py): validates Folder.id == body.folder_id
  - Phase 4 move/copy (app/services/document_service.py): validates
    DocumentFolder.id == target_folder_id

The column remains indexed. The ondelete=SET NULL cascade is no longer
enforced at DB level; portal folder deletion no longer auto-nulls contained
documents' folder_id. This is an accepted limitation until the full migration.
"""

from alembic import op

revision = 'n2o3p4q5r6s7'
down_revision = 'c1d2e3f4a5b6'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint('fk_documents_folder_id', 'documents', type_='foreignkey')


def downgrade():
    op.create_foreign_key(
        'fk_documents_folder_id',
        'documents', 'document_folders',
        ['folder_id'], ['id'],
        ondelete='SET NULL',
    )
