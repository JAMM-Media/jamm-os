"""add_notification_tier

Revision ID: a9b8c7d6e5f4
Revises: n1u2r3t4u5r6
Create Date: 2026-09-04 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'a9b8c7d6e5f4'
down_revision = 'n1u2r3t4u5r6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add the column with a temporary server_default so existing rows are
    # populated (they get 'quiet'). Then drop the server default so the DB
    # enforces that every new row must supply a value explicitly.
    op.add_column(
        'notifications',
        sa.Column(
            'tier',
            sa.String(length=20),
            nullable=False,
            server_default='quiet',
        ),
    )
    op.alter_column('notifications', 'tier', server_default=None)


def downgrade() -> None:
    op.drop_column('notifications', 'tier')
