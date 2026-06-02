# migrations/versions/0017_extensions.py
"""extensions table

Revision ID: 0017_extensions
Revises: 0016_irs_authorizations
Create Date: 2026-04-15
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0017_extensions"
down_revision = "0016_irs_authorizations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "extensions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "firm_id", UUID(as_uuid=True),
            sa.ForeignKey("firms.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "client_id", UUID(as_uuid=True),
            sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "engagement_id", UUID(as_uuid=True),
            sa.ForeignKey("engagements.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("form_type", sa.String(10), nullable=False),
        sa.Column("filed_at", sa.Date(), nullable=False),
        sa.Column("extended_deadline", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="filed"),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_extensions_firm_id", "extensions", ["firm_id"])
    op.create_index("ix_extensions_engagement_id", "extensions", ["engagement_id"])
    op.create_index("ix_extensions_client_id", "extensions", ["client_id"])


def downgrade() -> None:
    op.drop_index("ix_extensions_client_id", table_name="extensions")
    op.drop_index("ix_extensions_engagement_id", table_name="extensions")
    op.drop_index("ix_extensions_firm_id", table_name="extensions")
    op.drop_table("extensions")
