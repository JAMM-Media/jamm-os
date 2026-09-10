# app/models/metric_registry_axis.py

"""One sliceable axis on a registry metric.

Platform-global reference data, a child of metric_registry, and covered by
the same documented carve-out as its parent (Sep 10, 2026 session): NO
firm_id, no firm ever writes to it, tenant isolation does not apply.

Breakdown axes and filter axes are ONE list per metric (ruling R1), so this
is the only axes table. A row is (metric, axis_kind, axis_key, sort_order)
(ruling R2). There is no shared axes master table; each kind resolves
against its own existing source of truth (ruling R3):

  engagement_category  -> ServiceCategory in app/core/enums.py. Breakdowns
                          are category-only, never per engagement type, so
                          no engagement_type kind exists (ruling R5).
  complexity_flag      -> complexity_flags.key.
  complexity_dimension -> the PAIR (complexity_flags.key,
                          complexity_dimensions.key). Dimension keys are
                          unique only within their flag
                          (uq_complexity_dimensions_flag_key), so the
                          axis_key is written "flag_key.dimension_key" and
                          split on the FIRST dot.
  referral_source      -> ReferralSource in app/core/enums.py.

Two of those sources are code constants, so no database foreign key can
express the rule. Resolution is enforced at the service layer
(app/services/metric_registry_service.py, 422 on a key that does not
resolve for its kind) and pinned by tests (ruling R7).
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

import sqlalchemy as sa
from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import MetricAxisKind
from app.db.base_class import Base


class MetricRegistryAxis(Base):
    __tablename__ = "metric_registry_axes"

    __table_args__ = (
        UniqueConstraint(
            "metric_id",
            "axis_kind",
            "axis_key",
            name="uq_metric_registry_axes_metric_kind_key",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    metric_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("metric_registry.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    axis_kind: Mapped[MetricAxisKind] = mapped_column(
        sa.Enum(MetricAxisKind, native_enum=False), nullable=False
    )

    # Resolved per axis_kind; see the module docstring for the rule.
    axis_key: Mapped[str] = mapped_column(String(200), nullable=False)

    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

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
