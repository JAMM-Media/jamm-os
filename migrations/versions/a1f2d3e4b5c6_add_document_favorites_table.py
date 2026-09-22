"""add document_favorites table

Revision ID: a1f2d3e4b5c6
Revises: cbb333e2cedc
Create Date: 2026-09-22

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1f2d3e4b5c6"
down_revision: Union[str, Sequence[str], None] = "cbb333e2cedc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "document_favorites",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("firm_id", sa.UUID(), sa.ForeignKey("firms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("item_type", sa.String(20), nullable=False),
        sa.Column("item_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("item_type IN ('document', 'folder')", name="ck_document_favorites_item_type"),
        sa.UniqueConstraint("user_id", "item_type", "item_id", name="uq_document_favorites_user_item"),
    )
    op.create_index("ix_document_favorites_firm_id", "document_favorites", ["firm_id"])
    op.create_index("ix_document_favorites_user_id", "document_favorites", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_document_favorites_user_id", table_name="document_favorites")
    op.drop_index("ix_document_favorites_firm_id", table_name="document_favorites")
    op.drop_table("document_favorites")
