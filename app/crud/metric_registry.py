# app/crud/metric_registry.py

"""Plain reads for the metric registry and its two curation child tables.

Pure reads only. No HTTPException here; refusals live in
app/services/metric_registry_service.py. The registry is platform-global
(no firm_id, see the model docstrings), so nothing in this module takes a
firm_id and nothing filters on one.
"""

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import MetricAxisKind
from app.models.metric_registry import MetricRegistry
from app.models.metric_registry_axis import MetricRegistryAxis
from app.models.metric_registry_relation import MetricRegistryRelation


def get_metric(db: Session, metric_id: UUID) -> Optional[MetricRegistry]:
    return db.get(MetricRegistry, metric_id)


def get_metric_by_key(db: Session, key: str) -> Optional[MetricRegistry]:
    return db.execute(
        select(MetricRegistry).where(MetricRegistry.key == key)
    ).scalar_one_or_none()


def list_axes_for_metric(db: Session, metric_id: UUID) -> list[MetricRegistryAxis]:
    return list(
        db.execute(
            select(MetricRegistryAxis)
            .where(MetricRegistryAxis.metric_id == metric_id)
            .order_by(MetricRegistryAxis.sort_order, MetricRegistryAxis.axis_key)
        ).scalars()
    )


def get_axis(
    db: Session, metric_id: UUID, axis_kind: MetricAxisKind, axis_key: str
) -> Optional[MetricRegistryAxis]:
    return db.execute(
        select(MetricRegistryAxis).where(
            MetricRegistryAxis.metric_id == metric_id,
            MetricRegistryAxis.axis_kind == axis_kind,
            MetricRegistryAxis.axis_key == axis_key,
        )
    ).scalar_one_or_none()


def list_relations_for_metric(
    db: Session, metric_id: UUID
) -> list[MetricRegistryRelation]:
    """Relations authored ON this metric (metric_id side). Directional: a
    relation listing this metric as the related side is not returned."""
    return list(
        db.execute(
            select(MetricRegistryRelation)
            .where(MetricRegistryRelation.metric_id == metric_id)
            .order_by(MetricRegistryRelation.sort_order)
        ).scalars()
    )


def get_relation(
    db: Session, metric_id: UUID, related_metric_id: UUID
) -> Optional[MetricRegistryRelation]:
    return db.execute(
        select(MetricRegistryRelation).where(
            MetricRegistryRelation.metric_id == metric_id,
            MetricRegistryRelation.related_metric_id == related_metric_id,
        )
    ).scalar_one_or_none()
