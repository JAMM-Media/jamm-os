# migrations/versions/c0d1e2f3a4b5_add_copied_from_to_documents.py
"""Add copied_from_document_id to documents

Revision ID: c0d1e2f3a4b5
Revises: aa1b2c3d4e5f
Create Date: 2026-09-09

Adds a nullable UUID column to track document copy provenance.
Not a FK -- the source may be deleted or in a different scope.
"""

from alembic import op
import sqlalchemy as sa

revision = 'c0d1e2f3a4b5'
down_revision = 'aa1b2c3d4e5f'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'documents',
        sa.Column(
            'copied_from_document_id', sa.UUID(), nullable=True,
            comment='Populated when this document was created by copying another. '
                    'Not a FK -- the source may be purged after the copy is made.',
        ),
    )


def downgrade():
    op.drop_column('documents', 'copied_from_document_id')
