# migrations/versions/0014_add_firm_chat_tables.py

"""add firm chat tables

Revision ID: 0014_add_firm_chat_tables
Revises: 0013_add_client_messaging_tables
Create Date: 2026-04-14
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0014_add_firm_chat_tables"
down_revision = "0013_add_client_messaging_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -----------------------------------------------------------------------
    # channels
    # -----------------------------------------------------------------------
    op.create_table(
        "channels",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "firm_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("firms.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "is_deleted",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.UniqueConstraint("firm_id", "name", name="uq_channel_firm_name"),
    )
    op.create_index("ix_channels_firm_id", "channels", ["firm_id"])

    # -----------------------------------------------------------------------
    # firm_messages
    # -----------------------------------------------------------------------
    op.create_table(
        "firm_messages",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "firm_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("firms.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "channel_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("channels.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "sender_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("attachment_key", sa.String(500), nullable=True),
        sa.Column("mentions", sa.JSON, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "is_deleted",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.create_index("ix_firm_messages_firm_id", "firm_messages", ["firm_id"])
    op.create_index("ix_firm_messages_channel_id", "firm_messages", ["channel_id"])
    op.create_index(
        "ix_firm_messages_firm_channel",
        "firm_messages",
        ["firm_id", "channel_id"],
    )

    # -----------------------------------------------------------------------
    # firm_message_reads
    # -----------------------------------------------------------------------
    op.create_table(
        "firm_message_reads",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "message_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("firm_messages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "read_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("message_id", "user_id", name="uq_firm_message_read"),
    )


def downgrade() -> None:
    op.drop_table("firm_message_reads")
    op.drop_index("ix_firm_messages_firm_channel", table_name="firm_messages")
    op.drop_index("ix_firm_messages_channel_id", table_name="firm_messages")
    op.drop_index("ix_firm_messages_firm_id", table_name="firm_messages")
    op.drop_table("firm_messages")
    op.drop_index("ix_channels_firm_id", table_name="channels")
    op.drop_table("channels")
