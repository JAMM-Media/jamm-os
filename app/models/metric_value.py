# app/models/metric_value.py

import uuid
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class MetricValue(Base):
    """
    One computed metric observation for one firm, for one metric, for one
    week. value is null when sample_size is 0 -- there was nothing to
    observe that week, which is different from observing a zero.
    """

    __tablename__ = "metric_values"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    firm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("firms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    metric_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("metric_registry.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    week_start: Mapped[date] = mapped_column(Date, nullable=False)

    value: Mapped[Optional[float]] = mapped_column(Numeric(12, 4), nullable=True)

    sample_size: Mapped[int] = mapped_column(Integer, nullable=False)

    std_dev: Mapped[Optional[float]] = mapped_column(Numeric(12, 4), nullable=True)

    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=True,
    )

    __table_args__ = (
        UniqueConstraint("firm_id", "metric_id", "week_start", name="uq_metric_value_firm_metric_week"),
    )
