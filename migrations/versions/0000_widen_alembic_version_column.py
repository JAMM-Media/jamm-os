# migrations/versions/0000_widen_alembic_version_column.py
"""widen alembic_version version_num to varchar(255)

Revision ID: 0000_widen_alembic_version
Revises:
Create Date: 2026-05-27

"""
from alembic import op

revision = "0000_widen_alembic_version"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE alembic_version ALTER COLUMN version_num TYPE varchar(255)"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE alembic_version ALTER COLUMN version_num TYPE varchar(32)"
    )
