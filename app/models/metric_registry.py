# app/models/metric_registry.py

import uuid
from datetime import datetime, timezone
from typing import Optional

import sqlalchemy as sa
from sqlalchemy import Boolean, Integer, String, DateTime, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import (
    BetterDirection,
    MetricEntityType,
    MetricPillar,
    MetricWindowType,
)
from app.db.base_class import Base


class MetricRegistry(Base):
    """
    Platform-global reference data: the shared vocabulary for metrics.
    No firm_id. Tenant isolation does not apply to this table.

    Since Sep 10, 2026 the row also carries display curation fields
    (pillar, entity_type, attention_weight, synonyms) and owns two child
    tables, metric_registry_axes and metric_registry_relations, which
    inherit this carve-out. Every curation field ships NULL or empty and
    is filled by the authoring session. NULL means not yet authored, never
    a default; a later migration tightens pillar and entity_type to NOT
    NULL once every active row carries them.
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

    window_type: Mapped[MetricWindowType] = mapped_column(
        sa.Enum(MetricWindowType, native_enum=False), nullable=False
    )

    tier: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Display curation fields, added Sep 10, 2026. All ship unauthored.

    # Which Firm Profile pillar section the card lives in. NULL means not
    # yet authored.
    pillar: Mapped[Optional[MetricPillar]] = mapped_column(
        sa.Enum(MetricPillar, native_enum=False), nullable=True
    )

    # What kind of thing one unit of this metric counts. NULL means not
    # yet authored.
    entity_type: Mapped[Optional[MetricEntityType]] = mapped_column(
        sa.Enum(MetricEntityType, native_enum=False), nullable=True
    )

    # Authored score used to order cards within a pillar. The scale is to be
    # authored; NULL means not yet authored.
    attention_weight: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Search vocabulary only. Never referenced by anything, so no integrity
    # constraint is wanted here.
    synonyms: Mapped[list[str]] = mapped_column(
        ARRAY(String(100)),
        nullable=False,
        server_default="{}",
        default=list,
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

    # Sliceable axes (breakdown and filter are one list, ruled Sep 10, 2026).
    axes: Mapped[list["MetricRegistryAxis"]] = relationship(
        "MetricRegistryAxis",
        order_by="MetricRegistryAxis.sort_order",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # Related metrics this card's drill-in shows alongside it. Directional
    # and authored per card: A listing B does not imply B lists A, which is
    # why this is joined on metric_id only and there is no back-reference
    # from the related_metric_id side.
    related: Mapped[list["MetricRegistryRelation"]] = relationship(
        "MetricRegistryRelation",
        foreign_keys="MetricRegistryRelation.metric_id",
        order_by="MetricRegistryRelation.sort_order",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
