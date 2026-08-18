# migrations/versions/291581aa9ba0_merge_firm_timezone_and_option_price_.py

"""merge firm timezone and option price scope

Two heads, both descending from 1ed5f6118514:

    62e44a7fd8f1  scope firm_option_prices by service_catalog_entry
                  (per-engagement-type pricing overrides, Phase 2.5)
    b2321b6bb22a  add timezone to firm
                  (booking slot localization)

Neither touches the other's tables, so there is nothing to reconcile and both
upgrade() and downgrade() are deliberately empty. This revision exists only to
give the chain a single head again.

Merge rather than re-pointing 62e44a7fd8f1's down_revision at b2321b6bb22a,
which was the other option since 62e44a7fd8f1 had not been pushed. Merging
matches how this repo has resolved every previous divergence (eight merge
revisions already, including 0ab2e3586a9c_merge_andrew_and_ben_migrations.py)
and does not rewrite a migration that has already been applied to a database.

Revision ID: 291581aa9ba0
Revises: 62e44a7fd8f1, b2321b6bb22a
Create Date: 2026-08-17
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '291581aa9ba0'
down_revision: Union[str, Sequence[str], None] = ('62e44a7fd8f1', 'b2321b6bb22a')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
