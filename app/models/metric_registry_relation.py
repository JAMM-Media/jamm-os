# app/models/metric_registry_relation.py

"""One directional "related metric" link between two registry rows.

Platform-global reference data, a child of metric_registry, and covered by
the same documented carve-out as its parent (Sep 10, 2026 session): NO
firm_id, no firm ever writes to it, tenant isolation does not apply.

Related metrics are DIRECTIONAL and authored per card (ruling R4): a row
(A, B) means A's drill-in shows B alongside it and says nothing about B's
drill-in. A metric may not list itself; the schema refuses it first and
ck_metric_registry_relations_not_self is the second line of defence.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class MetricRegistryRelation(Base):
    __tablename__ = "metric_registry_relations"

    __table_args__ = (
        UniqueConstraint(
            "metric_id",
            "related_metric_id",
            name="uq_metric_registry_relations_pair",
        ),
        CheckConstraint(
            "metric_id != related_metric_id",
            name="ck_metric_registry_relations_not_self",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # The card being authored.
    metric_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("metric_registry.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # The metric shown alongside it.
    related_metric_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("metric_registry.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

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
