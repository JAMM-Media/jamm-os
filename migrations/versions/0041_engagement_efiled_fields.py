# migrations/versions/0041_engagement_efiled_fields.py

"""0041_engagement_efiled_fields

Revision ID: 0041_engagement_efiled_fields
Revises: 0040_add_billing_detail_reports
Create Date: 2026-06-05

"""

from alembic import op
import sqlalchemy as sa

revision = "0041_engagement_efiled_fields"
down_revision = "0040_add_billing_detail_reports"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "engagements",
        sa.Column("efiled_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "engagements",
        sa.Column("irs_confirmation_number", sa.String(100), nullable=True),
    )


def downgrade():
    op.drop_column("engagements", "irs_confirmation_number")
    op.drop_column("engagements", "efiled_at")
