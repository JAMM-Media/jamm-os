# migrations/versions/b6e2a94f7c18_sync_index_and_comment_drift.py
"""sync_index_and_comment_drift

Revision ID: b6e2a94f7c18
Revises: a3f7c1d29b44
Create Date: 2026-07-09

"""
from alembic import op
import sqlalchemy as sa

revision = "b6e2a94f7c18"
down_revision = "a3f7c1d29b44"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(op.f("ix_audit_logs_firm_id"), "audit_logs", ["firm_id"], unique=False)
    op.create_index(op.f("ix_integrations_user_id"), "integrations", ["user_id"], unique=False)
    op.alter_column(
        "clients",
        "entity_type",
        existing_type=sa.VARCHAR(length=20),
        comment="individual | business | trust | estate | non_profit",
        existing_comment="individual | business | trust | estate",
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "clients",
        "entity_type",
        existing_type=sa.VARCHAR(length=20),
        comment="individual | business | trust | estate",
        existing_comment="individual | business | trust | estate | non_profit",
        existing_nullable=True,
    )
    op.drop_index(op.f("ix_integrations_user_id"), table_name="integrations")
    op.drop_index(op.f("ix_audit_logs_firm_id"), table_name="audit_logs")
