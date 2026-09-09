"""add soft delete to document_folders

Revision ID: aa1b2c3d4e5f
Revises: f1e2s3y4s5t6
Create Date: 2026-09-09

Changes:
  document_folders:
    - deleted_at: nullable TIMESTAMPTZ for soft-delete
    - deleted_by: nullable UUID FK to users.id (SET NULL on user deletion)
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "aa1b2c3d4e5f"
down_revision = "f1e2s3y4s5t6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "document_folders",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "document_folders",
        sa.Column(
            "deleted_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_document_folders_deleted_at",
        "document_folders",
        ["deleted_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_document_folders_deleted_at", table_name="document_folders")
    op.drop_column("document_folders", "deleted_by")
    op.drop_column("document_folders", "deleted_at")
