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
        # The same dimension may be configured once per branch, never twice on
        # the same branch.
        #
        # postgresql_nulls_not_distinct is load-bearing here, not decoration.
        # Under Postgres default NULLS DISTINCT, two flat configs for the same
        # dimension both read as (firm, dim, NULL, NULL) and BOTH insert
        # cleanly, because NULL never equals NULL. That silently un-enforces
        # this constraint for the flat case, which is the common case. Postgres
        # 16.10 is live here and supports NULLS NOT DISTINCT, which makes the
        # constraint mean what it says.
        UniqueConstraint(
            "firm_id",
            "dimension_id",
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
