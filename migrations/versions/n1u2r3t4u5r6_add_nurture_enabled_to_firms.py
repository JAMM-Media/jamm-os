"""add_nurture_enabled_to_firms

Revision ID: n1u2r3t4u5r6
Revises: f8e2a9b7c4d1
Create Date: 2026-09-04 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'n1u2r3t4u5r6'
down_revision = 'f8e2a9b7c4d1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'firms',
        sa.Column(
            'nurture_enabled',
            sa.Boolean(),
            nullable=False,
            server_default='false',
        ),
    )


def downgrade() -> None:
    op.drop_column('firms', 'nurture_enabled')
