# app/models/complexity_dimension_unit.py

"""A unit of measure a numeric_range dimension can be counted in.

System-owned catalog content. NO firm_id, per the August 13, 2026 carve-out
documented in app/models/complexity_flag.py.

Only meaningful for numeric_range dimensions. Nothing at the database level
stops a unit being attached to a boolean or categorical dimension, because the
check needs to read the parent row; pricing_config_service rejects it at save
time instead.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class ComplexityDimensionUnit(Base):
    __tablename__ = "complexity_dimension_units"

    __table_args__ = (
        UniqueConstraint(
            "dimension_id",
            "key",
            name="uq_complexity_dimension_units_dimension_key",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    dimension_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("complexity_dimensions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    key: Mapped[str] = mapped_column(String(100), nullable=False)

    # e.g. transaction count, total proceeds, accounts.
    label: Mapped[str] = mapped_column(String(200), nullable=False)

    # The lead-facing question generated for this unit; content session fills it.
    question_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

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

    dimension: Mapped["ComplexityDimension"] = relationship(
        "ComplexityDimension",
        back_populates="units",
    )
