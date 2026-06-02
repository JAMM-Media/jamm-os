# migrations/versions/0013_add_client_messaging_tables.py

"""add client messaging tables

Revision ID: 0013_add_client_messaging_tables
Revises: 0012_add_notes_table
Create Date: 2026-04-14
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0013_add_client_messaging_tables"
down_revision = "0012_add_notes_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "client_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "firm_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("firms.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "client_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("clients.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "sender_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("sender_role", sa.String(30), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_index("ix_client_messages_firm_id", "client_messages", ["firm_id"])
    op.create_index("ix_client_messages_client_id", "client_messages", ["client_id"])
    op.create_index(
        "ix_client_messages_firm_client",
        "client_messages",
        ["firm_id", "client_id"],
    )

    op.create_table(
        "client_message_reads",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "message_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("client_messages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "reader_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("reader_role", sa.String(30), nullable=False),
        sa.Column(
            "read_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("message_id", "reader_id", "reader_role", name="uq_message_read"),
    )


def downgrade() -> None:
    op.drop_table("client_message_reads")
    op.drop_index("ix_client_messages_firm_client", table_name="client_messages")
    op.drop_index("ix_client_messages_client_id", table_name="client_messages")
    op.drop_index("ix_client_messages_firm_id", table_name="client_messages")
    op.drop_table("client_messages")
