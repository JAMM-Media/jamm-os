# app/models/service_catalog_entry.py

"""One firm's offering and top-level pricing stance for one engagement type."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

import sqlalchemy as sa
from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import PricingMode
from app.db.base_class import Base


class ServiceCatalogEntry(Base):
    __tablename__ = "service_catalog_entries"

    __table_args__ = (
        UniqueConstraint(
            "firm_id",
            "engagement_type",
            name="uq_service_catalog_entries_firm_engagement_type",
        ),
        {
            "comment": (
                "Rows are created lazily on first activation. Absence of a row "
                "means not offered, identical in meaning to a row with "
                "is_offered false."
            )
        },
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    firm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("firms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Plain String(50) matching Engagement.engagement_type. Validated against
    # EngagementType at the schema layer.
    engagement_type: Mapped[str] = mapped_column(String(50), nullable=False)

    is_offered: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    # Null until first activation. Activation requires it: a service cannot be
    # half-on. Enforced in pricing_config_service, not by a database
    # constraint, because the rule is conditional on is_offered.
    pricing_mode: Mapped[Optional[PricingMode]] = mapped_column(
        sa.Enum(PricingMode, name="pricingmode", native_enum=False),
        nullable=True,
    )

    # Null means no base fee set. For quote_required mode it stays null by
    # definition.
    base_fee: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)

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

    firm: Mapped["Firm"] = relationship(
        "Firm",
        back_populates="service_catalog_entries",
    )
