# migrations/versions/0015_phase13a_tax_engagement_fields.py

"""phase13a_tax_engagement_fields

Revision ID: 0015_phase13a_tax_engagement_fields
Revises: 0014_add_firm_chat_tables
Create Date: 2026-04-15

"""

from alembic import op
import sqlalchemy as sa

revision = "0015_tax_engagement_fields"
down_revision = "0014_add_firm_chat_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("engagements", sa.Column("engagement_type", sa.String(50), nullable=True))
    op.add_column("engagements", sa.Column("filing_deadline", sa.Date(), nullable=True))
    op.add_column("engagements", sa.Column("extended_deadline", sa.Date(), nullable=True))
    op.create_index("ix_engagements_engagement_type", "engagements", ["engagement_type"])
    op.create_index("ix_engagements_filing_deadline", "engagements", ["filing_deadline"])


def downgrade() -> None:
    op.drop_index("ix_engagements_filing_deadline", table_name="engagements")
    op.drop_index("ix_engagements_engagement_type", table_name="engagements")
    op.drop_column("engagements", "extended_deadline")
    op.drop_column("engagements", "filing_deadline")
    op.drop_column("engagements", "engagement_type")
