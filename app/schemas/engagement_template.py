# app/schemas/engagement_template.py

import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class TaskTemplateItem(BaseModel):
    title: str
    description: Optional[str] = None
    order: int = 0


class EngagementTemplateBase(BaseModel):
    name: str
    description: Optional[str] = None
    engagement_type: Optional[str] = None
    estimated_hours: Optional[float] = None
    task_templates: list[TaskTemplateItem] = []
    document_checklist: list[str] = []
    notes: Optional[str] = None


class EngagementTemplateCreate(EngagementTemplateBase):
    pass


class EngagementTemplateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    engagement_type: Optional[str] = None
    estimated_hours: Optional[float] = None
    task_templates: Optional[list[TaskTemplateItem]] = None
    document_checklist: Optional[list[str]] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class EngagementTemplateOut(EngagementTemplateBase):
    id: uuid.UUID
    firm_id: uuid.UUID
    is_active: bool
    use_count: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
