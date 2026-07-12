# migrations/versions/a3f7c1d29b44_drop_orphaned_accepted_at_from_users.py
"""drop_orphaned_accepted_at_from_users

Revision ID: a3f7c1d29b44
Revises: 5e549eb005ce
Create Date: 2026-07-09

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "a3f7c1d29b44"
down_revision = "5e549eb005ce"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("users", "accepted_at")


def downgrade() -> None:
    op.add_column(
        "users",
        sa.Column("accepted_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
    )
