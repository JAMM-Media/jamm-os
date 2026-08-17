# migrations/versions/1ed5f6118514_add_service_catalog_entry_id_scope_to_.py

"""add service_catalog_entry_id scope to firm_dimension_configs

Per-engagement-type pricing overrides, ruled August 17, 2026. A firm may
configure the same catalog dimension differently per engagement type, so a
config row now carries a scope:

    service_catalog_entry_id IS NULL      -> BLANKET. Applies to every
                                             engagement type the system catalog
                                             maps the dimension's flag to.
    service_catalog_entry_id IS NOT NULL  -> SCOPED. Applies ONLY when pricing
                                             that engagement type.

Precedence is wholesale replacement, never a field-level merge. Existing rows
all become blanket configs, which is the correct reading of what they meant
before scopes existed, so the column is nullable with no backfill and no
server_default.

WRITTEN BY HAND, deliberately, per Section 2 step 3 of the session procedure.
Autogenerate against this repo emits 23 known drift items that have nothing to
do with this session, including a DROP of uq_enrollment_active_lead_sequence
which must never be applied. Nothing generated was kept.

WHY THE UNIQUE CONSTRAINT IS REBUILT RATHER THAN LEFT ALONE.
uq_firm_dimension_configs_firm_dimension_branch previously read
(firm_id, dimension_id, parent_tier_id, parent_option_id). Without the scope
column in it, a firm could not configure the same dimension at the same branch
position once as a blanket config and again scoped to an engagement type: the
second insert would collide with the first, which is exactly the arrangement
this feature exists to allow. Adding the column to the constraint is therefore
not cosmetic, it is the feature.

NULLS NOT DISTINCT IS CARRIED FORWARD, AND NOW COVERS THREE NULLABLE COLUMNS
RATHER THAN TWO. The reasoning is the same one documented on the original
constraint and on the model. Under Postgres default NULLS DISTINCT, two flat
blanket configs for the same dimension both read as
(firm, dim, NULL, NULL, NULL) and BOTH insert cleanly, because NULL never
equals NULL, which silently un-enforces the constraint for the flat blanket
case. That is the common case, so losing the property here would un-enforce
the rule for most real rows while the constraint still appeared to exist.
Postgres 16.10 is live on dev and supports NULLS NOT DISTINCT; the floor for
this repo is 15 for exactly this reason.

The ADD CONSTRAINT compiler path was checked before this file was written
rather than assumed. The original constraint was emitted INLINE inside
op.create_table, and instance eleven in How_We_Work_Process_Rules.md is a case
of one compiler path rendering a construct while another silently discarded it.
The DDL for this constraint was compiled directly and read: it renders
"UNIQUE NULLS NOT DISTINCT (...)". It is verified again against the live
database catalog after the upgrade, not by this file exiting green.

Revision ID: 1ed5f6118514
Revises: 7a1c3e8f9d02
Create Date: 2026-08-17
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "1ed5f6118514"
down_revision: Union[str, Sequence[str], None] = "7a1c3e8f9d02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLE = "firm_dimension_configs"
COLUMN = "service_catalog_entry_id"
INDEX_NAME = "ix_firm_dimension_configs_service_catalog_entry_id"
FK_NAME = "fk_firm_dimension_configs_service_catalog_entry"
UQ_NAME = "uq_firm_dimension_configs_firm_dimension_branch"

# The constraint as it stood before this revision, so downgrade() restores the
# exact shape rather than an approximation of it.
UQ_COLUMNS_BEFORE = [
    "firm_id",
    "dimension_id",
    "parent_tier_id",
    "parent_option_id",
]

UQ_COLUMNS_AFTER = [
    "firm_id",
    "dimension_id",
    COLUMN,
    "parent_tier_id",
    "parent_option_id",
]


def upgrade() -> None:
    """Upgrade schema."""
    # 1. The scope column. Nullable, no server_default: NULL is a meaningful
    # value here (blanket), not a placeholder for one, so every existing row
    # becoming NULL is the intended outcome rather than a gap to backfill.
    op.add_column(
        TABLE,
        sa.Column(COLUMN, sa.Uuid(), nullable=True),
    )

    op.create_index(INDEX_NAME, TABLE, [COLUMN])

    # 2. The foreign key, created explicitly and named explicitly rather than
    # inline on the column above. Explicit naming is what lets downgrade() emit
    # DROP CONSTRAINT for it; the repo already carries one live defect from an
    # unnamed constraint (app/models/sequence.py) and is not reproducing it.
    #
    # CASCADE, deliberately. Deleting a firm's catalog entry deletes the thing
    # these configs exist to price. SET NULL would silently demote a scoped
    # override to a blanket one, widening a per-engagement price to every
    # engagement type, which is a mispricing rather than a cleanup.
    op.create_foreign_key(
        FK_NAME,
        TABLE,
        "service_catalog_entries",
        [COLUMN],
        ["id"],
        ondelete="CASCADE",
    )

    # 3. Rebuild the branch-uniqueness constraint with the scope column in it.
    # Drop first: Postgres will not accept two constraints of the same name, and
    # the replacement deliberately reuses the name because it is the same rule,
    # now stated per scope.
    op.drop_constraint(UQ_NAME, TABLE, type_="unique")
    op.create_unique_constraint(
        UQ_NAME,
        TABLE,
        UQ_COLUMNS_AFTER,
        postgresql_nulls_not_distinct=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Reverse order. The unique constraint goes first because it references the
    # scope column; dropping the column out from under it is not something to
    # rely on the database to sort out.
    op.drop_constraint(UQ_NAME, TABLE, type_="unique")
    op.create_unique_constraint(
        UQ_NAME,
        TABLE,
        UQ_COLUMNS_BEFORE,
        postgresql_nulls_not_distinct=True,
    )

    # Then the foreign key, then the index, then the column itself. Dropping
    # the column would take the last two with it, but naming them keeps the
    # downgrade readable and keeps it honest if the column drop is ever
    # reordered.
    op.drop_constraint(FK_NAME, TABLE, type_="foreignkey")
    op.drop_index(INDEX_NAME, table_name=TABLE)
    op.drop_column(TABLE, COLUMN)
