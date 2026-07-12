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
    # This migration reconciles index/comment drift that exists in some
    # environments and not others (e.g. an index already created manually
    # in production), so it must tolerate either starting state.
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_logs_firm_id ON audit_logs (firm_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_integrations_user_id ON integrations (user_id)")
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
    op.execute("DROP INDEX IF EXISTS ix_integrations_user_id")
    op.execute("DROP INDEX IF EXISTS ix_audit_logs_firm_id")
