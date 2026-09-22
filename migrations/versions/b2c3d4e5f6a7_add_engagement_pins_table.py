"""add engagement_pins table

Revision ID: b2c3d4e5f6a7
Revises: a1f2d3e4b5c6
Create Date: 2026-09-22

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a1f2d3e4b5c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "engagement_pins",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("firm_id", sa.UUID(), sa.ForeignKey("firms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("engagement_id", sa.UUID(), sa.ForeignKey("engagements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("item_type", sa.String(20), nullable=False),
        sa.Column("item_id", sa.UUID(), nullable=False),
        sa.Column("pinned_by", sa.UUID(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("item_type IN ('document', 'folder')", name="ck_engagement_pins_item_type"),
        sa.UniqueConstraint("engagement_id", "item_type", "item_id", name="uq_engagement_pins_engagement_item"),
    )
    op.create_index("ix_engagement_pins_firm_id", "engagement_pins", ["firm_id"])
    op.create_index("ix_engagement_pins_engagement_id", "engagement_pins", ["engagement_id"])
    op.create_index("ix_engagement_pins_pinned_by", "engagement_pins", ["pinned_by"])


def downgrade() -> None:
    op.drop_index("ix_engagement_pins_pinned_by", table_name="engagement_pins")
    op.drop_index("ix_engagement_pins_engagement_id", table_name="engagement_pins")
    op.drop_index("ix_engagement_pins_firm_id", table_name="engagement_pins")
    op.drop_table("engagement_pins")
