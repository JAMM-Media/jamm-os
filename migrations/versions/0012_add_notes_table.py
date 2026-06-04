# migrations/versions/0012_add_notes_table.py

"""add notes table

Revision ID: 0012_add_notes_table
Revises: i1j2k3l4m5n6
Create Date: 2026-04-14
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0012_add_notes_table"
down_revision = "i1j2k3l4m5n6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "firm_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("firms.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "author_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("is_private", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # Individual indexes
    op.create_index("ix_notes_firm_id", "notes", ["firm_id"])
    op.create_index("ix_notes_entity_id", "notes", ["entity_id"])

    # Composite index — the primary query path
    op.create_index(
        "ix_notes_firm_entity_type_entity_id",
        "notes",
        ["firm_id", "entity_type", "entity_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_notes_firm_entity_type_entity_id", table_name="notes")
    op.drop_index("ix_notes_entity_id", table_name="notes")
    op.drop_index("ix_notes_firm_id", table_name="notes")
    op.drop_table("notes")
