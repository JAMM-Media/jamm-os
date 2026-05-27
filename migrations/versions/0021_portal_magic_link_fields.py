# migrations/versions/0021_portal_magic_link_fields.py

"""Add magic_link_token_hash and magic_link_expires_at to portal_sessions.

Revision ID: 0021_portal_magic_link_fields
Revises: 0020_client_import_and_categories
Create Date: 2026-04-22
"""

import sqlalchemy as sa
from alembic import op

revision = "0021_portal_magic_link_fields"
down_revision = "0020_client_import_cats"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "portal_sessions",
        sa.Column("magic_link_token_hash", sa.String(64), nullable=True),
    )
    op.add_column(
        "portal_sessions",
        sa.Column("magic_link_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_unique_constraint(
        "uq_portal_sessions_magic_link_token_hash",
        "portal_sessions",
        ["magic_link_token_hash"],
    )
    op.create_index(
        "ix_portal_sessions_magic_link_token_hash",
        "portal_sessions",
        ["magic_link_token_hash"],
    )


def downgrade() -> None:
    op.drop_index("ix_portal_sessions_magic_link_token_hash", table_name="portal_sessions")
    op.drop_constraint(
        "uq_portal_sessions_magic_link_token_hash",
        "portal_sessions",
        type_="unique",
    )
    op.drop_column("portal_sessions", "magic_link_expires_at")
    op.drop_column("portal_sessions", "magic_link_token_hash")
