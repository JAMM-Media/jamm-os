"""add business_description to clients

Revision ID: l1m2n3o4p5q6
Revises: 810ac1dc5039
Create Date: 2026-07-23

"""

from alembic import op
import sqlalchemy as sa

revision = "l1m2n3o4p5q6"
down_revision = "810ac1dc5039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("clients", sa.Column("business_description", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("clients", "business_description")
