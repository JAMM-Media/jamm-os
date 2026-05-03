# migrations/versions/0018_tax_organizer.py
"""tax_organizer_templates and tax_organizers tables

Revision ID: 0018_tax_organizer
Revises: 0017_extensions
Create Date: 2026-04-15
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0018_tax_organizer"
down_revision = "0017_extensions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tax_organizer_templates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "firm_id", UUID(as_uuid=True),
            sa.ForeignKey("firms.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("organizer_type", sa.String(50), nullable=False,
                  server_default="custom"),
        sa.Column("sections", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("is_default", sa.Boolean(), nullable=False,
                  server_default="false"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_tax_organizer_templates_firm_id",
        "tax_organizer_templates", ["firm_id"],
    )

    op.create_table(
        "tax_organizers",
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
        sa.Column(
            "template_id", UUID(as_uuid=True),
            sa.ForeignKey("tax_organizer_templates.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("tax_year", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="sent"),
        sa.Column("responses", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("client_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_tax_organizers_firm_id", "tax_organizers", ["firm_id"])
    op.create_index("ix_tax_organizers_client_id", "tax_organizers", ["client_id"])
    op.create_index(
        "ix_tax_organizers_engagement_id", "tax_organizers", ["engagement_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_tax_organizers_engagement_id", table_name="tax_organizers")
    op.drop_index("ix_tax_organizers_client_id", table_name="tax_organizers")
    op.drop_index("ix_tax_organizers_firm_id", table_name="tax_organizers")
    op.drop_table("tax_organizers")
    op.drop_index(
        "ix_tax_organizer_templates_firm_id",
        table_name="tax_organizer_templates",
    )
    op.drop_table("tax_organizer_templates")
