# app/schemas/metric_registry_relation.py

"""Schemas for metric_registry_relations, the directional related-metric links.

The self-relation refusal lives here first, so the database check constraint
ck_metric_registry_relations_not_self is the second line of defence, not the
first (Sep 10, 2026 ruling R4).
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator

SELF_RELATION_MESSAGE = "A metric cannot list itself as a related metric."


class MetricRegistryRelationBase(BaseModel):
    metric_id: UUID
    related_metric_id: UUID
    sort_order: int = 0

    @model_validator(mode="after")
    def _refuse_self_relation(self) -> "MetricRegistryRelationBase":
        if self.metric_id == self.related_metric_id:
            raise ValueError(SELF_RELATION_MESSAGE)
        return self


class MetricRegistryRelationCreate(MetricRegistryRelationBase):
    pass


class MetricRegistryRelationUpdate(BaseModel):
    sort_order: Optional[int] = None


class MetricRegistryRelationOut(MetricRegistryRelationBase):
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
