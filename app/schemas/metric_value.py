# app/schemas/metric_value.py

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class MetricValueBase(BaseModel):
    # firm_id is intentionally absent — it is injected from the JWT tenant
    # context (or the nightly run's own firm loop), never from a request body.
    metric_id: UUID
    week_start: date
    value: Optional[Decimal] = None
    sample_size: int
    std_dev: Optional[Decimal] = None
    computed_at: datetime


class MetricValueCreate(MetricValueBase):
    pass


class MetricValueUpdate(BaseModel):
    value: Optional[Decimal] = None
    sample_size: Optional[int] = None
    std_dev: Optional[Decimal] = None
    computed_at: Optional[datetime] = None


class MetricValueOut(MetricValueBase):
    id: UUID
    firm_id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
