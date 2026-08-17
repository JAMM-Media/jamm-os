# migrations/versions/62e44a7fd8f1_scope_firm_option_prices_by_service_.py

"""scope firm_option_prices by service_catalog_entry

Phase 2.5 of the per-engagement-type pricing overrides session, ruled during
the session rather than planned into it.

WHY THIS EXISTS. Phase 1 scoped firm_dimension_configs, which was enough to
make per-engagement-type overrides work for NUMERIC dimensions: tiers hang off
firm_tiers.config_id, so a scoped config tree owns its own tiers and its own
prices automatically. Categorical dimensions did not follow, because an option
price was keyed (firm_id, option_id) alone. Prices attach to the system
vocabulary option, not to any one config of its dimension, so a scoped tree and
the blanket tree both read the same row and a firm could not say "staking is
300 on a 1040 and 500 on an 1120". The override feature was half present:
structural for categoricals, real only for numerics.

    service_catalog_entry_id IS NULL      -> BLANKET price for that option.
    service_catalog_entry_id IS NOT NULL  -> applies ONLY when pricing that
                                             engagement type.

Existing rows all become blanket prices, which is exactly what they meant
before scopes existed, so the column is nullable with no backfill and no
server_default.

WRITTEN BY HAND, per Section 2 step 3, for the same reason as 1ed5f6118514:
autogenerate against this repo emits 23 known drift items including a DROP of
uq_enrollment_active_lead_sequence which must never be applied. Nothing
generated was kept.

THE UNIQUE CONSTRAINT IS REBUILT, AND THAT IS THE FEATURE RATHER THAN TIDYING.
uq_firm_option_prices_firm_option previously read (firm_id, option_id). Leaving
it would refuse the second price the moment a firm added a scoped one, since
both rows carry the same firm and option. The scope column has to join it.

NULLS NOT DISTINCT IS NEW ON THIS CONSTRAINT, not carried forward, because the
constraint had no nullable member until now. It is required for the same reason
documented on firm_dimension_configs: service_catalog_entry_id is NULL for
blanket prices, which is the common case, and under Postgres default
NULLS DISTINCT two blanket prices for one option would both read as
(firm, option, NULL) and BOTH insert cleanly, because NULL never equals NULL.
That would silently un-enforce one-price-per-option exactly where nearly every
row lives, while the constraint still appeared to exist. Postgres 16.10 is live
on dev; the repo floor is 15 for precisely this feature.

The ADD CONSTRAINT compiler path was verified rather than assumed before this
file was written, per instance eleven, and the result is checked again against
the live database catalog after the upgrade rather than inferred from this
migration exiting green.

Revision ID: 62e44a7fd8f1
Revises: 1ed5f6118514
Create Date: 2026-08-17
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "62e44a7fd8f1"
down_revision: Union[str, Sequence[str], None] = "1ed5f6118514"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLE = "firm_option_prices"
COLUMN = "service_catalog_entry_id"
INDEX_NAME = "ix_firm_option_prices_service_catalog_entry_id"
FK_NAME = "fk_firm_option_prices_service_catalog_entry"
UQ_NAME = "uq_firm_option_prices_firm_option"

# The constraint as it stood before this revision. Note the absence of
# NULLS NOT DISTINCT: it had no nullable member, so the property would have
# been meaningless. downgrade() restores it exactly as it was rather than
# carrying the new property backwards into a shape that never had it.
UQ_COLUMNS_BEFORE = ["firm_id", "option_id"]

UQ_COLUMNS_AFTER = ["firm_id", "option_id", COLUMN]


def upgrade() -> None:
    """Upgrade schema."""
    # 1. The scope column. Nullable, no server_default: NULL is a meaningful
    # value (blanket), not a placeholder for a missing one.
    op.add_column(
        TABLE,
        sa.Column(COLUMN, sa.Uuid(), nullable=True),
    )

    op.create_index(INDEX_NAME, TABLE, [COLUMN])

    # 2. The foreign key, explicit and explicitly named so downgrade() can emit
    # DROP CONSTRAINT for it.
    #
    # CASCADE, matching firm_dimension_configs. SET NULL would promote a
    # per-engagement price into the blanket price for every engagement type when
    # a catalog entry is deleted, which is a mispricing rather than a cleanup,
    # and it could collide with an existing blanket row for the same option.
    op.create_foreign_key(
        FK_NAME,
        TABLE,
        "service_catalog_entries",
        [COLUMN],
        ["id"],
        ondelete="CASCADE",
    )

    # 3. Rebuild the uniqueness rule with the scope column in it. Drop first:
    # the name is reused deliberately because it is the same rule, now stated
    # per scope.
    op.drop_constraint(UQ_NAME, TABLE, type_="unique")
    op.create_unique_constraint(
        UQ_NAME,
        TABLE,
        UQ_COLUMNS_AFTER,
        postgresql_nulls_not_distinct=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Reverse order. Constraint first, since it references the scope column.
    #
    # NOT LOSSLESS, AND DELIBERATELY LOUD ABOUT IT. If any scoped prices exist,
    # dropping the column collapses them onto their blanket counterparts and the
    # restored two-column constraint will reject the duplicates rather than
    # silently keep an arbitrary one. That is the correct failure: a downgrade
    # that quietly discarded a firm's per-engagement prices, or picked one at
    # random, would be worse than one that stops. Clear the scoped rows first if
    # this downgrade is ever run against a database that has them.
    op.drop_constraint(UQ_NAME, TABLE, type_="unique")
    op.create_unique_constraint(UQ_NAME, TABLE, UQ_COLUMNS_BEFORE)

    op.drop_constraint(FK_NAME, TABLE, type_="foreignkey")
    op.drop_index(INDEX_NAME, table_name=TABLE)
    op.drop_column(TABLE, COLUMN)
