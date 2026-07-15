# app/models/metric_run_log.py

import uuid
from datetime import datetime
from typing import Optional

import sqlalchemy as sa
from sqlalchemy import DateTime, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import MetricRunStatus
from app.db.base_class import Base


class MetricRunLog(Base):
    """
    One row per nightly metric computation run. System-level table -- no
    firm_id. Deviation from the standing per-firm-scoping rule is approved
    for this table only, since a run covers every firm in one pass.
    """

    __tablename__ = "metric_run_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    status: Mapped[MetricRunStatus] = mapped_column(
        sa.Enum(MetricRunStatus, native_enum=False), nullable=False
    )

    error_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

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
