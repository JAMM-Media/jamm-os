# migrations/versions/a2b3c4d5e6f7_add_engagement_finalized.py
"""add finalized_at and finalized_by to engagements

Revision ID: a2b3c4d5e6f7
Revises: 664cbed6bbd2
Create Date: 2026-09-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f7e6d5c4b3a2"
down_revision: Union[str, Sequence[str], None] = '664cbed6bbd2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'engagements',
        sa.Column(
            'finalized_at',
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        'engagements',
        sa.Column(
            'finalized_by',
            sa.UUID(),
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column('engagements', 'finalized_by')
    op.drop_column('engagements', 'finalized_at')
