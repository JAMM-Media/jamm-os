"""add_accepted_at_to_users

Revision ID: j1k2l3m4n5o6
Revises: 4e5c69ee809d
Create Date: 2026-05-30

"""

from alembic import op
import sqlalchemy as sa

revision = "j1k2l3m4n5o6"
down_revision = "4e5c69ee809d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        "UPDATE users SET accepted_at = created_at WHERE is_active = true AND accepted_at IS NULL"
    )


def downgrade() -> None:
    op.drop_column("users", "accepted_at")
