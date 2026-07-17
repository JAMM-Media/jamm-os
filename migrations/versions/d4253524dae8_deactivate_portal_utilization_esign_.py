"""deactivate portal_utilization_esign registry row

Revision ID: d4253524dae8
Revises: 87f61acace52
Create Date: 2026-07-15 19:18:15.068915

Data-only migration, approved deviation from this session's "no migration
expected" note. E-signature always flows through the external Dropbox Sign
hosted page (app/services/esign_service.py); there is no portal-native
signing flow and no event distinguishing portal-vs-other channel for
esign resolutions. The metric isn't unmeasurable, it's undefined in the
current product -- same precedent as portal_utilization_todos in
87f61acace52 (row kept, not deleted). Reactivate alongside the Dropbox
Sign Tier 2 session once a channel signal exists in the esign event
pipeline.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4253524dae8'
down_revision: Union[str, Sequence[str], None] = '87f61acace52'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("UPDATE metric_registry SET is_active = false WHERE key = 'portal_utilization_esign'")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("UPDATE metric_registry SET is_active = true WHERE key = 'portal_utilization_esign'")
