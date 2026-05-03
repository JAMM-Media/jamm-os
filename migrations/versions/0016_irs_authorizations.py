# migrations/versions/0016_irs_authorizations.py
"""irs_authorizations table

Revision ID: 0016_irs_authorizations
Revises: 0015_tax_engagement_fields
Create Date: 2026-04-15
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0016_irs_authorizations"
down_revision = "0015_tax_engagement_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "irs_authorizations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "firm_id", UUID(as_uuid=True),
            sa.ForeignKey("firms.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "client_id", UUID(as_uuid=True),
            sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("form_type", sa.String(10), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending_signature"),
        sa.Column(
            "signature_envelope_id", UUID(as_uuid=True),
            sa.ForeignKey("signature_envelopes.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column(
            "signed_document_id", UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("tax_years", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column(
            "expiry_notification_sent", sa.Boolean(),
            nullable=False, server_default="false",
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_irs_authorizations_firm_id", "irs_authorizations", ["firm_id"])
    op.create_index("ix_irs_authorizations_client_id", "irs_authorizations", ["client_id"])
    op.create_index("ix_irs_authorizations_status", "irs_authorizations", ["status"])


def downgrade() -> None:
    op.drop_index("ix_irs_authorizations_status", table_name="irs_authorizations")
    op.drop_index("ix_irs_authorizations_client_id", table_name="irs_authorizations")
    op.drop_index("ix_irs_authorizations_firm_id", table_name="irs_authorizations")
    op.drop_table("irs_authorizations")
