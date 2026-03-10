"""Create documents and audit_logs tables

Revision ID: 0007
Revises: 0006
Create Date: 2026-03-10
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "firm_id",
            UUID(as_uuid=True),
            sa.ForeignKey("firms.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "client_id",
            UUID(as_uuid=True),
            sa.ForeignKey("clients.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "engagement_id",
            UUID(as_uuid=True),
            sa.ForeignKey("engagements.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "uploaded_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("s3_key", sa.String(512), nullable=False, unique=True),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.Integer, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "firm_id",
            UUID(as_uuid=True),
            sa.ForeignKey("firms.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "document_id",
            UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("documents")
