"""add audit log table

Revision ID: g1h2i3j4k5l6
Revises: f2a3b4c5d6e7
Create Date: 2026-04-03

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import inspect

revision = "g1h2i3j4k5l6"
down_revision = "f2a3b4c5d6e7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_tables = inspector.get_table_names()

    # If the old document-specific audit_logs table exists (from migration 0007),
    # rename it to document_audit_logs. On fresh DBs it won't exist.
    if "audit_logs" in existing_tables:
        op.rename_table("audit_logs", "document_audit_logs")
        # Re-create indexes under the new table name
        op.create_index("ix_document_audit_logs_firm_id", "document_audit_logs", ["firm_id"])
        op.create_index("ix_document_audit_logs_document_id", "document_audit_logs", ["document_id"])
        op.create_index("ix_document_audit_logs_user_id", "document_audit_logs", ["user_id"])
    elif "document_audit_logs" not in existing_tables:
        # Fresh DB: create document_audit_logs from scratch
        op.create_table(
            "document_audit_logs",
            sa.Column("id", UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "firm_id",
                UUID(as_uuid=True),
                sa.ForeignKey("firms.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "document_id",
                UUID(as_uuid=True),
                sa.ForeignKey("documents.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "user_id",
                UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
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
        op.create_index("ix_document_audit_logs_firm_id", "document_audit_logs", ["firm_id"])
        op.create_index("ix_document_audit_logs_document_id", "document_audit_logs", ["document_id"])
        op.create_index("ix_document_audit_logs_user_id", "document_audit_logs", ["user_id"])

    # Create the new centralized audit log table
    if "audit_logs" not in existing_tables:
        op.create_table(
            "audit_logs",
            sa.Column("id", UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "firm_id",
                UUID(as_uuid=True),
                sa.ForeignKey("firms.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "actor_id",
                UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("actor_type", sa.String(50), nullable=False, server_default="system"),
            sa.Column("action", sa.String(200), nullable=False),
            sa.Column("entity_type", sa.String(100), nullable=True),
            sa.Column("entity_id", UUID(as_uuid=True), nullable=True),
            sa.Column("ip_address", sa.String(45), nullable=True),
            sa.Column("user_agent", sa.String(500), nullable=True),
            sa.Column("metadata", sa.JSON(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
        )
        op.create_index("ix_audit_logs_firm_id", "audit_logs", ["firm_id"])
        op.create_index("ix_audit_logs_actor_id", "audit_logs", ["actor_id"])
        op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
        op.create_index("ix_audit_logs_entity_type", "audit_logs", ["entity_type"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_tables = inspector.get_table_names()

    if "audit_logs" in existing_tables:
        op.drop_index("ix_audit_logs_entity_type", table_name="audit_logs")
        op.drop_index("ix_audit_logs_action", table_name="audit_logs")
        op.drop_index("ix_audit_logs_actor_id", table_name="audit_logs")
        op.drop_index("ix_audit_logs_firm_id", table_name="audit_logs")
        op.drop_table("audit_logs")

    if "document_audit_logs" in existing_tables:
        op.rename_table("document_audit_logs", "audit_logs")
