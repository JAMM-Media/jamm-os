# app/schemas/metric_registry_axis.py

"""Schemas for metric_registry_axes, the sliceable axes on a metric.

The Create schema checks SHAPE only: a complexity_dimension key must be
written "flag_key.dimension_key" because dimension keys are unique only
within their flag (Sep 10, 2026 ruling R3). Whether the flag and dimension
EXIST is the service's job (app/services/metric_registry_service.py), which
is the only place that can read the catalog.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator

from app.core.enums import MetricAxisKind

DIMENSION_KEY_SHAPE_MESSAGE = (
    "A complexity dimension axis key must be written as flag_key.dimension_key."
)


def split_dimension_key(axis_key: str) -> tuple[str, str]:
    """Split a complexity_dimension axis key on its FIRST dot.

    Raises ValueError with the shape message when there is no dot or either
    side is empty. Shared by the schema and the service so the two agree on
    what a well-formed key is.
    """
    flag_key, dot, dimension_key = axis_key.partition(".")
    if not dot or not flag_key or not dimension_key:
        raise ValueError(DIMENSION_KEY_SHAPE_MESSAGE)
    return flag_key, dimension_key


class MetricRegistryAxisBase(BaseModel):
    metric_id: UUID
    axis_kind: MetricAxisKind
    axis_key: str
    sort_order: int = 0


class MetricRegistryAxisCreate(MetricRegistryAxisBase):
    @model_validator(mode="after")
    def _refuse_malformed_dimension_key(self) -> "MetricRegistryAxisCreate":
        if self.axis_kind == MetricAxisKind.complexity_dimension:
            split_dimension_key(self.axis_key)
        return self


class MetricRegistryAxisUpdate(BaseModel):
    sort_order: Optional[int] = None


class MetricRegistryAxisOut(MetricRegistryAxisBase):
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
