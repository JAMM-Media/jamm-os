# app/schemas/engagement.py

from datetime import date, datetime
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, ConfigDict

from app.schemas.task import TaskSummary
from app.schemas.client import ClientOut


class EngagementBase(BaseModel):
    name: str
    description: Optional[str] = None
    status: Optional[str] = "planning"
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    notes: Optional[str] = None
    is_active: bool = True


class EngagementCreate(EngagementBase):
    client_id: UUID


class EngagementUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class EngagementOut(EngagementBase):
    id: UUID
    client_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EngagementOverview(BaseModel):
    engagement: EngagementOut
    client: ClientOut
    tasks: List[TaskSummary]