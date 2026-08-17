# app/models/firm_dimension_config.py

"""One firm's decision to configure one system complexity dimension.

A config is either flat or dependent, never both:

- Both parent columns null  -> flat. The dimension is priced on its own and
  stacks additively with every other flat config. A chain of length one.
- Exactly one parent set    -> dependent. The dimension hangs under that
  numeric tier or that categorical option, and prices live only at the leaf
  of the chain.

The check constraint below enforces "never both". It deliberately does not
enforce "at least one", because both-null is the legitimate flat case.

Separately from direction, every config carries a SCOPE, added August 17, 2026:
service_catalog_entry_id names the engagement type this config tree applies to,
or is NULL for a blanket config that applies to every engagement type the
system catalog maps the flag to. See the column comment below.
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

import sqlalchemy as sa
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import DimensionRole
from app.db.base_class import Base


class FirmDimensionConfig(Base):
    __tablename__ = "firm_dimension_configs"

    __table_args__ = (
        CheckConstraint(
            "NOT (parent_tier_id IS NOT NULL AND parent_option_id IS NOT NULL)",
            name="ck_firm_dimension_configs_single_parent",
        ),
        # The same dimension may be configured once per branch PER SCOPE, never
        # twice on the same branch within the same scope. service_catalog_entry_id
        # joined this constraint on August 17, 2026, which is what lets a firm
        # configure the same dimension on the same branch position once as a
        # blanket config and again scoped to a particular engagement type.
        #
        # postgresql_nulls_not_distinct is load-bearing here, not decoration,
        # and it is now load-bearing for THREE nullable columns rather than two.
        # Under Postgres default NULLS DISTINCT, two flat blanket configs for
        # the same dimension both read as (firm, dim, NULL, NULL, NULL) and BOTH
        # insert cleanly, because NULL never equals NULL. That silently
        # un-enforces this constraint for the flat blanket case, which is the
        # common case. Postgres 16.10 is live here and supports NULLS NOT
        # DISTINCT, which makes the constraint mean what it says.
        UniqueConstraint(
            "firm_id",
            "dimension_id",
            "service_catalog_entry_id",
            "parent_tier_id",
            "parent_option_id",
            name="uq_firm_dimension_configs_firm_dimension_branch",
            postgresql_nulls_not_distinct=True,
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    firm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("firms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    dimension_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("complexity_dimensions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # The engagement type this config tree is scoped to, added August 17, 2026.
    #
    #   NULL     -> BLANKET. Applies to every engagement type the system catalog
    #               maps this dimension's flag to.
    #   non-NULL -> SCOPED. Applies ONLY when pricing that engagement type.
    #
    # Precedence is WHOLESALE replacement, never a field-level merge: if any
    # scoped root config exists for (dimension, engagement type), that tree
    # entirely supplies the config and the blanket tree is not consulted at all.
    #
    # SCOPE IS UNIFORM WITHIN A TREE. Every child config under a scoped root
    # carries the same scope as its root. That is enforced in
    # pricing_config_service, NOT by this constraint, because a child references
    # its parent tier or parent option rather than its parent config, so the
    # database has no single row to compare against. The service guard is the
    # only thing holding it.
    #
    # CASCADE rather than SET NULL, deliberately: a firm deleting its catalog
    # entry for an engagement type is deleting the thing this tree exists to
    # price. Demoting the tree to blanket on that delete would silently widen a
    # per-engagement override to every engagement type, which is a mispricing
    # rather than a cleanup.
    service_catalog_entry_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey(
            "service_catalog_entries.id",
            ondelete="CASCADE",
            name="fk_firm_dimension_configs_service_catalog_entry",
        ),
        nullable=True,
        index=True,
    )

    role: Mapped[DimensionRole] = mapped_column(
        sa.Enum(DimensionRole, name="dimensionrole", native_enum=False),
        nullable=False,
    )

    # Required for numeric_range usage; enforced in pricing_config_service.
    # SET NULL rather than CASCADE: losing a unit from the system catalog
    # should not silently delete a firm's whole configured branch.
    unit_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("complexity_dimension_units.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Required when role is guard; enforced in pricing_config_service.
    guard_threshold: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(14, 2),
        nullable=True,
    )

    # Circular FK: firm_tiers.config_id points back at this table, so one of
    # the two directions has to be added after both tables exist. use_alter
    # does that, and the name is given EXPLICITLY. An unnamed use_alter FK is a
    # known live defect in this repo (app/models/sequence.py:39) -- SQLAlchemy
    # cannot emit DROP CONSTRAINT for it, which is what makes pytest exit 1
    # during conftest teardown today. Not reproducing that here.
    parent_tier_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey(
            "firm_tiers.id",
            ondelete="CASCADE",
            use_alter=True,
            name="fk_firm_dimension_configs_parent_tier",
        ),
        nullable=True,
    )

    parent_option_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("complexity_vocabulary_options.id", ondelete="CASCADE"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # The tiers this config owns. foreign_keys is required because this table
    # and firm_tiers reference each other; without it SQLAlchemy cannot tell
    # which FK defines the relationship.
    tiers: Mapped[list["FirmTier"]] = relationship(
        "FirmTier",
        back_populates="config",
        foreign_keys="FirmTier.config_id",
        cascade="all, delete-orphan",
    )

    # The tier this config hangs under, when dependent on a numeric branch.
    parent_tier: Mapped[Optional["FirmTier"]] = relationship(
        "FirmTier",
        back_populates="child_configs",
        foreign_keys=[parent_tier_id],
    )
