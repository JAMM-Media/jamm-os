"""merge concierge notification index and cost_rate/financial intelligence migration branches

Revision ID: 5ed2eed1ea77
Revises: 0054_add_cost_rate_to_users, e7a179c6f2a1
Create Date: 2026-06-26 18:49:05.726166

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5ed2eed1ea77'
down_revision: Union[str, Sequence[str], None] = ('0054_add_cost_rate_to_users', 'e7a179c6f2a1')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
