# migrations/versions/h3i4j5k6l7m8_add_service_catalog_and_pricing_tables.py

"""add service catalog, system complexity catalog, and firm pricing tables

Build 1 Session 2. Nine tables in one migration:

System-owned catalog (no firm_id, per the August 13, 2026 carve-out):
    complexity_flags
    complexity_flag_engagement_types
    complexity_dimensions
    complexity_dimension_units
    complexity_vocabulary_options

Firm-scoped pricing attachment:
    service_catalog_entries
    firm_dimension_configs
    firm_tiers
    firm_option_prices

WRITTEN BY HAND, deliberately. Autogenerate was run first, as the procedure
requires, and its output contained a large amount of pre-existing drift that
has nothing to do with this session: dashboard_layouts and
firm_default_dashboard_layouts unique/index churn, the peer_network index
renames left over from the cooperative rename, a leads.entity_type column
comment, and -- most importantly -- a DROP of
uq_enrollment_active_lead_sequence, the partial unique index that enforces the
no-duplicate-active-enrollment rule from the previous session. None of that
belongs in this migration, so the generated file was deleted per Section 2
step 3 and replaced with this.

The parent-tier foreign key is added by an explicit create_foreign_key at the
end rather than inline in create_table. This is not a style choice. The
sequences/sequence_versions circularity is repeated here between
firm_dimension_configs and firm_tiers, and a use_alter=True ForeignKeyConstraint
passed to op.create_table is skipped by the CREATE TABLE compiler and then
never emitted by anything else, so the constraint would simply not exist in the
database while the model insisted it did. Creating it explicitly after both
tables exist is what actually puts it there. It is named explicitly for the
same reason the model names it: an unnamed use_alter FK cannot have DROP
CONSTRAINT emitted for it, which is the live defect behind the pytest teardown
error today.

Revision ID: h3i4j5k6l7m8
Revises: g2h3i4j5k6l7
Create Date: 2026-08-13
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "h3i4j5k6l7m8"
down_revision: Union[str, Sequence[str], None] = "g2h3i4j5k6l7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # System-owned complexity catalog. No firm_id anywhere in this block.
    # ------------------------------------------------------------------
    op.create_table(
        "complexity_flags",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )

    op.create_table(
        "complexity_flag_engagement_types",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("flag_id", sa.Uuid(), nullable=False),
        sa.Column("engagement_type", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["flag_id"], ["complexity_flags.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "flag_id",
            "engagement_type",
            name="uq_complexity_flag_engagement_types_flag_type",
        ),
    )
    op.create_index(
        op.f("ix_complexity_flag_engagement_types_flag_id"),
        "complexity_flag_engagement_types",
        ["flag_id"],
        unique=False,
    )

    op.create_table(
        "complexity_dimensions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("flag_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "boolean",
                "numeric_range",
                "categorical",
                name="dimensionkind",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("question_text", sa.Text(), nullable=True),
        sa.Column("hierarchy_rank", sa.Integer(), server_default="0", nullable=False),
        sa.Column("linkable", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "default_role",
            sa.Enum(
                "priced",
                "informational",
                "guard",
                name="dimensionrole",
                native_enum=False,
            ),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["flag_id"], ["complexity_flags.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("flag_id", "key", name="uq_complexity_dimensions_flag_key"),
    )
    op.create_index(
        op.f("ix_complexity_dimensions_flag_id"),
        "complexity_dimensions",
        ["flag_id"],
        unique=False,
    )

    op.create_table(
        "complexity_dimension_units",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dimension_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["dimension_id"], ["complexity_dimensions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "dimension_id", "key", name="uq_complexity_dimension_units_dimension_key"
        ),
    )
    op.create_index(
        op.f("ix_complexity_dimension_units_dimension_id"),
        "complexity_dimension_units",
        ["dimension_id"],
        unique=False,
    )

    op.create_table(
        "complexity_vocabulary_options",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dimension_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["dimension_id"], ["complexity_dimensions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "dimension_id", "key", name="uq_complexity_vocabulary_options_dimension_key"
        ),
    )
    op.create_index(
        op.f("ix_complexity_vocabulary_options_dimension_id"),
        "complexity_vocabulary_options",
        ["dimension_id"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # Firm-scoped pricing attachment. Every table here carries firm_id.
    # ------------------------------------------------------------------
    op.create_table(
        "service_catalog_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("firm_id", sa.Uuid(), nullable=False),
        sa.Column("engagement_type", sa.String(length=50), nullable=False),
        sa.Column("is_offered", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "pricing_mode",
            sa.Enum(
                "fixed",
                "starting_at",
                "quote_required",
                name="pricingmode",
                native_enum=False,
            ),
            nullable=True,
        ),
        sa.Column("base_fee", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["firm_id"], ["firms.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "firm_id",
            "engagement_type",
            name="uq_service_catalog_entries_firm_engagement_type",
        ),
        comment=(
            "Rows are created lazily on first activation. Absence of a row "
            "means not offered, identical in meaning to a row with "
            "is_offered false."
        ),
    )
    op.create_index(
        op.f("ix_service_catalog_entries_firm_id"),
        "service_catalog_entries",
        ["firm_id"],
        unique=False,
    )

    # parent_tier_id is created as a bare column here. Its foreign key to
    # firm_tiers is added at the bottom of this function, once firm_tiers
    # exists. See the module docstring.
    op.create_table(
        "firm_dimension_configs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("firm_id", sa.Uuid(), nullable=False),
        sa.Column("dimension_id", sa.Uuid(), nullable=False),
        sa.Column(
            "role",
            sa.Enum(
                "priced",
                "informational",
                "guard",
                name="dimensionrole",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("unit_id", sa.Uuid(), nullable=True),
        sa.Column("guard_threshold", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("parent_tier_id", sa.Uuid(), nullable=True),
        sa.Column("parent_option_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "NOT (parent_tier_id IS NOT NULL AND parent_option_id IS NOT NULL)",
            name="ck_firm_dimension_configs_single_parent",
        ),
        sa.ForeignKeyConstraint(["firm_id"], ["firms.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["dimension_id"], ["complexity_dimensions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["unit_id"], ["complexity_dimension_units.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["parent_option_id"],
            ["complexity_vocabulary_options.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        # nulls_not_distinct is required for this constraint to bind the flat
        # case (both parents null), which is the common case. Under Postgres
        # default NULLS DISTINCT two identical flat configs would both insert.
        sa.UniqueConstraint(
            "firm_id",
            "dimension_id",
            "parent_tier_id",
            "parent_option_id",
            name="uq_firm_dimension_configs_firm_dimension_branch",
            postgresql_nulls_not_distinct=True,
        ),
    )
    op.create_index(
        op.f("ix_firm_dimension_configs_firm_id"),
        "firm_dimension_configs",
        ["firm_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_firm_dimension_configs_dimension_id"),
        "firm_dimension_configs",
        ["dimension_id"],
        unique=False,
    )

    op.create_table(
        "firm_tiers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("firm_id", sa.Uuid(), nullable=False),
        sa.Column("config_id", sa.Uuid(), nullable=False),
        sa.Column("range_min", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("range_max", sa.Numeric(precision=14, scale=2), nullable=True),
        # No default and no server_default, deliberately. NULL means unpriced
        # and routes to quote; 0.00 means priced at zero. Different facts.
        sa.Column("price", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["firm_id"], ["firms.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["config_id"], ["firm_dimension_configs.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_firm_tiers_firm_id"), "firm_tiers", ["firm_id"], unique=False
    )
    op.create_index(
        op.f("ix_firm_tiers_config_id"), "firm_tiers", ["config_id"], unique=False
    )

    op.create_table(
        "firm_option_prices",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("firm_id", sa.Uuid(), nullable=False),
        sa.Column("option_id", sa.Uuid(), nullable=False),
        # Same null-versus-zero law as firm_tiers.price.
        sa.Column("price", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["firm_id"], ["firms.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["option_id"], ["complexity_vocabulary_options.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "firm_id", "option_id", name="uq_firm_option_prices_firm_option"
        ),
    )
    op.create_index(
        op.f("ix_firm_option_prices_firm_id"),
        "firm_option_prices",
        ["firm_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_firm_option_prices_option_id"),
        "firm_option_prices",
        ["option_id"],
        unique=False,
    )

    # The circular half. Both tables now exist, so this can be a plain
    # ALTER TABLE ADD CONSTRAINT.
    op.create_foreign_key(
        "fk_firm_dimension_configs_parent_tier",
        "firm_dimension_configs",
        "firm_tiers",
        ["parent_tier_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    # Break the circle first, or the two drop_table calls deadlock on each
    # other's foreign key.
    op.drop_constraint(
        "fk_firm_dimension_configs_parent_tier",
        "firm_dimension_configs",
        type_="foreignkey",
    )

    op.drop_index(op.f("ix_firm_option_prices_option_id"), table_name="firm_option_prices")
    op.drop_index(op.f("ix_firm_option_prices_firm_id"), table_name="firm_option_prices")
    op.drop_table("firm_option_prices")

    op.drop_index(op.f("ix_firm_tiers_config_id"), table_name="firm_tiers")
    op.drop_index(op.f("ix_firm_tiers_firm_id"), table_name="firm_tiers")
    op.drop_table("firm_tiers")

    op.drop_index(
        op.f("ix_firm_dimension_configs_dimension_id"),
        table_name="firm_dimension_configs",
    )
    op.drop_index(
        op.f("ix_firm_dimension_configs_firm_id"), table_name="firm_dimension_configs"
    )
    op.drop_table("firm_dimension_configs")

    op.drop_index(
        op.f("ix_service_catalog_entries_firm_id"), table_name="service_catalog_entries"
    )
    op.drop_table("service_catalog_entries")

    op.drop_index(
        op.f("ix_complexity_vocabulary_options_dimension_id"),
        table_name="complexity_vocabulary_options",
    )
    op.drop_table("complexity_vocabulary_options")

    op.drop_index(
        op.f("ix_complexity_dimension_units_dimension_id"),
        table_name="complexity_dimension_units",
    )
    op.drop_table("complexity_dimension_units")

    op.drop_index(
        op.f("ix_complexity_dimensions_flag_id"), table_name="complexity_dimensions"
    )
    op.drop_table("complexity_dimensions")

    op.drop_index(
        op.f("ix_complexity_flag_engagement_types_flag_id"),
        table_name="complexity_flag_engagement_types",
    )
    op.drop_table("complexity_flag_engagement_types")

    op.drop_table("complexity_flags")
