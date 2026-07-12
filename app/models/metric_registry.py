# app/models/metric_registry.py

import uuid
from datetime import datetime
from typing import Optional

import sqlalchemy as sa
from sqlalchemy import Boolean, Integer, String, DateTime, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import BetterDirection
from app.db.base_class import Base


class MetricRegistry(Base):
    """
    Platform-global reference data: the shared vocabulary for metrics.
    No firm_id. Tenant isolation does not apply to this table.
    """

    __tablename__ = "metric_registry"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    key: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)

    display_name: Mapped[str] = mapped_column(String(255), nullable=False)

    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    unit: Mapped[str] = mapped_column(String(50), nullable=False)

    better_direction: Mapped[BetterDirection] = mapped_column(
        sa.Enum(BetterDirection, native_enum=False), nullable=False
    )

    benchmark_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    tier: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=True,
    )
