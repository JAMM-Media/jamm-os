"""add index_consent to firms

Revision ID: 0025_add_index_consent_to_firms
Revises: 7d35737819be
Create Date: 2026-05-17 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0025_add_index_consent_to_firms'
down_revision: Union[str, Sequence[str], None] = 'ca840abe6306'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'firms',
        sa.Column(
            'index_consent',
            sa.Boolean(),
            nullable=False,
            server_default=sa.text('true'),
            comment='Firm has consented to contribute anonymized data to the JAMM Intelligence Index.',
        ),
    )


def downgrade() -> None:
    op.drop_column('firms', 'index_consent')
