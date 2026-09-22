# migrations/versions/a4d91c7b3e28_add_lead_source_placement_and_client_since.py
"""add leads.source_placement and clients.client_since

Revision ID: a4d91c7b3e28
Revises: b2c3d4e5f6a7
Create Date: 2026-09-17 00:00:00.000000

Repointed Sep 22, 2026 from down_revision 27b043fa7aa2 to b2c3d4e5f6a7. Ben's
five-migration chain (22aa77d2697a through b2c3d4e5f6a7) forked from
the same parent while this branch was in flight, so both claimed 27b043fa7aa2
and alembic reported two heads. This revision only adds two nullable
columns to leads and clients and touches nothing in that chain, so it
rebases onto the end of it rather than merging.

Hand-written. Autogenerate was run first (revision 6263d8474d92) and
discarded: it proposed 56 operations, of which only these 4 were this
change. The other 52 are the repo's standing model-versus-database drift
(dashboard_layouts and firm_default_dashboard_layouts index churn, the
cooperative_* to peer_network_* rename leftovers, a notifications.tier type
change, two column comments) and include the one destructive item,
`op.drop_index('uq_enrollment_active_lead_sequence')`, which would silently
remove the rule stopping a lead being enrolled twice in one sequence.

No migration is needed for the two new MetricAxisKind members. The
metric_registry_axes.axis_kind column is sa.Enum(..., native_enum=False)
with no check constraint, so it is a plain VARCHAR in the database and the
set of permitted values is enforced in Python only. Autogenerate confirmed
this by proposing nothing for that column while this same run did detect an
unrelated enum type change on notifications.tier, so the comparison was
live and capable of firing.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a4d91c7b3e28"
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


CLIENT_SINCE_COMMENT = (
    "Firm-entered date this client has been with the firm; distinct from "
    "created_at, which records when the client entered JAMM. Read by nothing "
    "as of Sep 2026."
)


def upgrade() -> None:
    op.add_column(
        'leads',
        sa.Column(
            'source_placement',
            sa.Enum(
                'reels', 'feed', 'story', 'shorts', 'search', 'display',
                'video', 'explore', 'marketplace', 'in_stream', 'shopping',
                'messaging',
                name='sourceplacement',
                native_enum=False,
            ),
            nullable=True,
        ),
    )
    op.add_column(
        'clients',
        sa.Column(
            'client_since',
            sa.Date(),
            nullable=True,
            comment=CLIENT_SINCE_COMMENT,
        ),
    )


def downgrade() -> None:
    op.drop_column('clients', 'client_since')
    op.drop_column('leads', 'source_placement')
