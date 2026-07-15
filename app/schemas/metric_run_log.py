# app/schemas/metric_run_log.py

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.core.enums import MetricRunStatus


class MetricRunLogBase(BaseModel):
    started_at: datetime
    finished_at: Optional[datetime] = None
    status: MetricRunStatus
    error_summary: Optional[str] = None


class MetricRunLogCreate(MetricRunLogBase):
    pass


class MetricRunLogUpdate(BaseModel):
    finished_at: Optional[datetime] = None
    status: Optional[MetricRunStatus] = None
    error_summary: Optional[str] = None


class MetricRunLogOut(MetricRunLogBase):
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
