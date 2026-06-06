# app/schemas/engagement_template.py

import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, model_validator


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
    is_recurring: bool = False
    recurrence_cadence: Optional[str] = None
    recurrence_day: Optional[int] = None
    recurrence_month: Optional[int] = None
    recurrence_advance_days: Optional[int] = 14



class EngagementTemplateCreate(EngagementTemplateBase):
    @model_validator(mode='after')
    def validate_recurrence(self) -> 'EngagementTemplateCreate':
        if self.is_recurring:
            if self.recurrence_cadence not in ('monthly', 'quarterly', 'annually'):
                raise ValueError("recurrence_cadence must be 'monthly', 'quarterly', or 'annually' when is_recurring is True")
            if self.recurrence_day is None or not (1 <= self.recurrence_day <= 28):
                raise ValueError("recurrence_day must be between 1 and 28 when is_recurring is True")
        if self.recurrence_cadence == 'annually':
            if self.recurrence_month is None or not (1 <= self.recurrence_month <= 12):
                raise ValueError("recurrence_month must be between 1 and 12 when cadence is 'annually'")
        return self


class EngagementTemplateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    engagement_type: Optional[str] = None
    estimated_hours: Optional[float] = None
    task_templates: Optional[list[TaskTemplateItem]] = None
    document_checklist: Optional[list[str]] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None
    is_recurring: Optional[bool] = None
    recurrence_cadence: Optional[str] = None
    recurrence_day: Optional[int] = None
    recurrence_month: Optional[int] = None
    recurrence_advance_days: Optional[int] = None
    last_spawned_at: Optional[datetime] = None

    @model_validator(mode='after')
    def validate_recurrence(self) -> 'EngagementTemplateUpdate':
        if self.is_recurring is True:
            if self.recurrence_cadence not in ('monthly', 'quarterly', 'annually'):
                raise ValueError("recurrence_cadence must be 'monthly', 'quarterly', or 'annually' when is_recurring is True")
            if self.recurrence_day is None or not (1 <= self.recurrence_day <= 28):
                raise ValueError("recurrence_day must be between 1 and 28 when is_recurring is True")
        if self.recurrence_cadence == 'annually':
            if self.recurrence_month is None or not (1 <= self.recurrence_month <= 12):
                raise ValueError("recurrence_month must be between 1 and 12 when cadence is 'annually'")
        return self


class EngagementTemplateOut(EngagementTemplateBase):
    id: uuid.UUID
    firm_id: uuid.UUID
    is_active: bool
    use_count: int
    last_spawned_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
