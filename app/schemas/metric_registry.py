# app/schemas/metric_registry.py

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.core.enums import BetterDirection, MetricWindowType


class MetricRegistryBase(BaseModel):
    key: str
    display_name: str
    description: Optional[str] = None
    unit: str
    better_direction: BetterDirection
    benchmark_eligible: bool = False
    window_type: MetricWindowType
    tier: int = 1
    is_active: bool = True


class MetricRegistryCreate(MetricRegistryBase):
    pass


class MetricRegistryUpdate(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    unit: Optional[str] = None
    better_direction: Optional[BetterDirection] = None
    benchmark_eligible: Optional[bool] = None
    window_type: Optional[MetricWindowType] = None
    tier: Optional[int] = None
    is_active: Optional[bool] = None


class MetricRegistryOut(MetricRegistryBase):
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
