# app/models/firm_tier.py

"""One numeric bucket in a firm's configured numeric_range dimension.

The null-versus-zero law lives on this table and on firm_option_prices, and it
is the reason price has no default and no server_default:

    price IS NULL  -> unpriced. Routes to quote, by the universal quote law.
    price = 0.00   -> priced, at zero. The firm charges nothing for this tier.

These are different facts and must never collapse into each other. A default
of any kind would erase the distinction on every insert that omitted the
column, which is exactly the mistake this comment exists to prevent.
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class FirmTier(Base):
    __tablename__ = "firm_tiers"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    firm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("firms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    config_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("firm_dimension_configs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    range_min: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    # Null means open top. An open-top tier is automatically quote territory
    # and carries no price.
    range_max: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)

    # See the module docstring. No default, no server_default, deliberately.
    price: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)

    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)

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

    # foreign_keys disambiguates the circular reference with
    # firm_dimension_configs. See the note on parent_tier_id there.
    config: Mapped["FirmDimensionConfig"] = relationship(
        "FirmDimensionConfig",
        back_populates="tiers",
        foreign_keys=[config_id],
    )

    # Configs that hang under this tier. Non-empty means this tier is an
    # interior node of a chain, so by the leaf-only pricing law its own price
    # must be null.
    child_configs: Mapped[list["FirmDimensionConfig"]] = relationship(
        "FirmDimensionConfig",
        back_populates="parent_tier",
        foreign_keys="FirmDimensionConfig.parent_tier_id",
    )
