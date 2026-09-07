"""filesystem phase1: document schema changes and document_folders table

Revision ID: f1e2s3y4s5t6
Revises: a9b8c7d6e5f4
Create Date: 2026-09-07

Changes:
  documents:
    - client_id becomes nullable (firm_library scope has no client)
    - scope column: engagement | client | firm_library (NOT NULL, CHECK constraint)
    - source column: staff | client | system (NOT NULL, server_default='staff')
    - source_client_id column: nullable FK to clients (who performed a portal upload)
    - triage_status column: pending | filed (NOT NULL, server_default='filed')
    - deleted_at column: nullable timestamp (Phase 3 soft-delete, not yet wired)
    - deleted_by column: nullable FK to users (Phase 3 soft-delete, not yet wired)

  document_folders:
    New table superseding the portal-specific 'folders' table.
    Old 'folders' table is unchanged and remains in service.
    Seeded with a data copy from 'folders' (all rows get scope='client').

Backfill reasoning:
  scope:         'engagement' where engagement_id IS NOT NULL; 'client' otherwise.
                 No existing row can be firm_library-scoped (client_id was NOT NULL before).
  source:        'staff' where uploaded_by IS NOT NULL; 'system' where IS NULL.
                 Rows with uploaded_by IS NULL are system-generated (e-sign signed PDFs).
                 Portal uploads post-D1-fix will need explicit source='client' wiring
                 in a later phase; they currently use uploaded_by IS NULL with no
                 source_client_id populated.
  triage_status: 'filed' for all existing rows -- they predate the triage concept.
                 New uploads also default to 'filed' (server_default) until the
                 Phase 5 triage tray is built. Do NOT change this default before
                 Phase 5 ships or client-uploaded files will become invisible to staff.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers
revision = 'f1e2s3y4s5t6'
down_revision = 'a9b8c7d6e5f4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------ #
    # 1. Create document_folders table (no self-ref FK yet -- added after) #
    # ------------------------------------------------------------------ #
    op.create_table(
        'document_folders',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('firm_id', UUID(as_uuid=True),
                  sa.ForeignKey('firms.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('scope', sa.String(20), nullable=False),
        sa.Column('client_id', UUID(as_uuid=True),
                  sa.ForeignKey('clients.id', ondelete='CASCADE'),
                  nullable=True),
        sa.Column('engagement_id', UUID(as_uuid=True),
                  sa.ForeignKey('engagements.id', ondelete='SET NULL'),
                  nullable=True),
        sa.Column('parent_folder_id', UUID(as_uuid=True), nullable=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_document_folders_firm_id', 'document_folders', ['firm_id'])
    op.create_index('ix_document_folders_client_id', 'document_folders', ['client_id'])
    op.create_index('ix_document_folders_engagement_id', 'document_folders', ['engagement_id'])
    op.create_index('ix_document_folders_parent_folder_id', 'document_folders', ['parent_folder_id'])

    # Self-referential FK added after table exists (per standing migration discipline).
    op.create_foreign_key(
        'fk_document_folders_parent_folder_id',
        'document_folders', 'document_folders',
        ['parent_folder_id'], ['id'],
        ondelete='SET NULL',
    )

    # CHECK constraint: scope determines which FKs must be present.
    op.create_check_constraint(
        'ck_document_folders_scope_fk_consistency',
        'document_folders',
        "(scope = 'engagement' AND engagement_id IS NOT NULL AND client_id IS NOT NULL)"
        " OR (scope = 'client' AND client_id IS NOT NULL AND engagement_id IS NULL)"
        " OR (scope = 'firm_library' AND client_id IS NULL AND engagement_id IS NULL)",
    )

    # ------------------------------------------------------------------ #
    # 2. Seed document_folders from folders (scope='client' data copy)    #
    # ------------------------------------------------------------------ #
    op.execute(sa.text(
        "INSERT INTO document_folders"
        " (id, firm_id, scope, client_id, engagement_id, parent_folder_id, name, created_at, updated_at)"
        " SELECT id, firm_id, 'client', client_id, NULL, parent_folder_id, name, created_at, updated_at"
        " FROM folders"
    ))

    # ------------------------------------------------------------------ #
    # 3. documents.client_id becomes nullable                             #
    # ------------------------------------------------------------------ #
    op.alter_column('documents', 'client_id', nullable=True)

    # ------------------------------------------------------------------ #
    # 4. documents.scope: add nullable, backfill, set NOT NULL, CHECK     #
    # ------------------------------------------------------------------ #
    op.add_column('documents', sa.Column('scope', sa.String(20), nullable=True))
    op.execute(sa.text(
        "UPDATE documents SET scope='engagement' WHERE engagement_id IS NOT NULL"
    ))
    op.execute(sa.text(
        "UPDATE documents SET scope='client'"
        " WHERE engagement_id IS NULL AND client_id IS NOT NULL"
    ))
    # firm_library rows cannot exist yet (client_id was NOT NULL before this migration)
    op.alter_column('documents', 'scope', nullable=False)
    op.create_check_constraint(
        'ck_documents_scope_fk_consistency',
        'documents',
        "(scope = 'engagement' AND engagement_id IS NOT NULL AND client_id IS NOT NULL)"
        " OR (scope = 'client' AND client_id IS NOT NULL AND engagement_id IS NULL)"
        " OR (scope = 'firm_library' AND client_id IS NULL AND engagement_id IS NULL)",
    )

    # ------------------------------------------------------------------ #
    # 5. documents.source: add nullable, backfill, set NOT NULL           #
    # ------------------------------------------------------------------ #
    op.add_column('documents', sa.Column('source', sa.String(20), nullable=True))
    op.execute(sa.text(
        "UPDATE documents SET source='staff' WHERE uploaded_by IS NOT NULL"
    ))
    op.execute(sa.text(
        "UPDATE documents SET source='system' WHERE uploaded_by IS NULL"
    ))
    op.alter_column('documents', 'source', nullable=False,
                    server_default='staff')

    # ------------------------------------------------------------------ #
    # 6. documents.source_client_id: nullable FK to clients               #
    # ------------------------------------------------------------------ #
    op.add_column(
        'documents',
        sa.Column('source_client_id', UUID(as_uuid=True), nullable=True),
    )
    op.create_index('ix_documents_source_client_id', 'documents', ['source_client_id'])
    op.create_foreign_key(
        'fk_documents_source_client_id',
        'documents', 'clients',
        ['source_client_id'], ['id'],
        ondelete='SET NULL',
    )

    # ------------------------------------------------------------------ #
    # 7. documents.triage_status: add nullable, backfill, set NOT NULL    #
    # ------------------------------------------------------------------ #
    op.add_column('documents', sa.Column('triage_status', sa.String(20), nullable=True))
    op.execute(sa.text("UPDATE documents SET triage_status='filed'"))
    op.alter_column('documents', 'triage_status', nullable=False,
                    server_default='filed')

    # ------------------------------------------------------------------ #
    # 8. documents soft-delete columns (Phase 3; no behavior wired yet)   #
    # ------------------------------------------------------------------ #
    op.add_column(
        'documents',
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        'documents',
        sa.Column('deleted_by', UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        'fk_documents_deleted_by',
        'documents', 'users',
        ['deleted_by'], ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    # Soft-delete columns
    op.drop_constraint('fk_documents_deleted_by', 'documents', type_='foreignkey')
    op.drop_column('documents', 'deleted_by')
    op.drop_column('documents', 'deleted_at')

    # triage_status
    op.drop_column('documents', 'triage_status')

    # source_client_id
    op.drop_constraint('fk_documents_source_client_id', 'documents', type_='foreignkey')
    op.drop_index('ix_documents_source_client_id', 'documents')
    op.drop_column('documents', 'source_client_id')

    # source
    op.drop_column('documents', 'source')

    # scope
    op.drop_constraint('ck_documents_scope_fk_consistency', 'documents', type_='check')
    op.drop_column('documents', 'scope')

    # client_id back to NOT NULL
    op.alter_column('documents', 'client_id', nullable=False)

    # document_folders
    op.drop_index('ix_document_folders_parent_folder_id', 'document_folders')
    op.drop_index('ix_document_folders_engagement_id', 'document_folders')
    op.drop_index('ix_document_folders_client_id', 'document_folders')
    op.drop_index('ix_document_folders_firm_id', 'document_folders')
    op.drop_table('document_folders')
