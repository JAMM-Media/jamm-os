# migrations/versions/0039_add_complexity_flags_to_engagements.py

"""add_complexity_flags_to_engagements

Revision ID: 0039_add_complexity_flags_to_engagements
Revises: 974b9b98dce6
Create Date: 2026-06-04

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '0039_add_complexity_flags_to_engagements'
down_revision = '974b9b98dce6'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'engagements',
        sa.Column(
            'complexity_flags',
            JSONB(),
            nullable=True,
            comment="Complexity flags selected at engagement letter send. Keys are flag names, values are selected tier label or True for fixed flags.",
        ),
    )


def downgrade():
    op.drop_column('engagements', 'complexity_flags')
