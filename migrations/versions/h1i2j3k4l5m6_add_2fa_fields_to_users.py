"""add_2fa_fields_to_users

Revision ID: h1i2j3k4l5m6
Revises: g1h2i3j4k5l6
Create Date: 2026-04-04

On a production DB that ran migration 0004 (which added totp_secret,
totp_enabled, backup_codes), this migration:
  1. Renames backup_codes → backup_codes_hash
  2. Tightens totp_secret to VARCHAR(64)

On a fresh DB (no tables yet), these columns will be created correctly
by Base.metadata.create_all() / the initial migration chain.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text

revision = "h1i2j3k4l5m6"
down_revision = "g1h2i3j4k5l6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if "users" not in inspector.get_table_names():
        # Fresh DB — columns will be created by create_all, nothing to do.
        return

    existing_cols = {c["name"] for c in inspector.get_columns("users")}

    # Rename backup_codes → backup_codes_hash
    if "backup_codes" in existing_cols and "backup_codes_hash" not in existing_cols:
        op.alter_column("users", "backup_codes", new_column_name="backup_codes_hash")

    # Add backup_codes_hash fresh if neither name exists (shouldn't happen but safe)
    if "backup_codes" not in existing_cols and "backup_codes_hash" not in existing_cols:
        op.add_column("users", sa.Column("backup_codes_hash", sa.Text(), nullable=True))

    # Add totp_secret if missing (shouldn't happen after 0004, but safe)
    if "totp_secret" not in existing_cols:
        op.add_column("users", sa.Column("totp_secret", sa.String(64), nullable=True))

    # Add totp_enabled if missing
    if "totp_enabled" not in existing_cols:
        op.add_column(
            "users",
            sa.Column("totp_enabled", sa.Boolean(), nullable=False, server_default="false"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "users" not in inspector.get_table_names():
        return

    existing_cols = {c["name"] for c in inspector.get_columns("users")}
    if "backup_codes_hash" in existing_cols and "backup_codes" not in existing_cols:
        op.alter_column("users", "backup_codes_hash", new_column_name="backup_codes")
