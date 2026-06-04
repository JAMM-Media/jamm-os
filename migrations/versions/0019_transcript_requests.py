# migrations/versions/0019_transcript_requests.py
"""transcript_requests table

Revision ID: 0019_transcript_requests
Revises: 0018_tax_organizer
Create Date: 2026-04-15
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0019_transcript_requests"
down_revision = "0018_tax_organizer"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "transcript_requests",
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
            "irs_authorization_id", UUID(as_uuid=True),
            sa.ForeignKey("irs_authorizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("transcript_type", sa.String(30), nullable=False),
        sa.Column("tax_year", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "document_id", UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("error_message", sa.String(500), nullable=True),
        sa.Column("provider_reference_id", sa.String(200), nullable=True),
        sa.Column(
            "requested_by", UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False,
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
    op.create_index("ix_transcript_requests_firm_id", "transcript_requests", ["firm_id"])
    op.create_index("ix_transcript_requests_client_id", "transcript_requests", ["client_id"])
    op.create_index("ix_transcript_requests_status", "transcript_requests", ["status"])


def downgrade() -> None:
    op.drop_index("ix_transcript_requests_status", table_name="transcript_requests")
    op.drop_index("ix_transcript_requests_client_id", table_name="transcript_requests")
    op.drop_index("ix_transcript_requests_firm_id", table_name="transcript_requests")
    op.drop_table("transcript_requests")
