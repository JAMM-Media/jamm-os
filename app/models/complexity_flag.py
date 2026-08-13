# app/models/complexity_flag.py

"""System-owned complexity flag.

CARVE-OUT (ruled August 13, 2026): this table and the rest of the system
complexity catalog (complexity_dimensions, complexity_dimension_units,
complexity_vocabulary_options, complexity_flag_engagement_types) are
system-owned shared content and are the documented exception to the firm_id
rule. They carry NO firm_id. No firm ever writes to them. Tenant isolation
applies to the firm-scoped pricing attachment tables instead
(service_catalog_entries, firm_dimension_configs, firm_tiers,
firm_option_prices). This carve-out covers these tables only.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class ComplexityFlag(Base):
    __tablename__ = "complexity_flags"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # Stable machine key, e.g. crypto, k1s_received. Global, not per firm,
    # because the catalog itself is system-owned.
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    # Lead-facing flag name.
    name: Mapped[str] = mapped_column(String(200), nullable=False)

    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
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

    engagement_types: Mapped[list["ComplexityFlagEngagementType"]] = relationship(
        "ComplexityFlagEngagementType",
        back_populates="flag",
        cascade="all, delete-orphan",
    )

    dimensions: Mapped[list["ComplexityDimension"]] = relationship(
        "ComplexityDimension",
        back_populates="flag",
        cascade="all, delete-orphan",
    )
