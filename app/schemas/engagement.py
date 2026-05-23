# app/schemas/engagement.py

from datetime import date, datetime
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, ConfigDict, field_validator

from app.schemas.task import TaskSummary
from app.schemas.client import ClientOut
from app.core.enums import EngagementType


class EngagementBase(BaseModel):
    name: str
    description: Optional[str] = None
    status: Optional[str] = "planning"
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    notes: Optional[str] = None
    is_active: bool = True
    engagement_type: Optional[str] = None
    filing_deadline: Optional[date] = None
    extended_deadline: Optional[date] = None


class EngagementCreate(EngagementBase):
    client_id: UUID

    @field_validator("engagement_type")
    @classmethod
    def validate_engagement_type(cls, v):
        if v is None:
            return v
        valid = {e.value for e in EngagementType}
        if v not in valid:
            raise ValueError(f"Invalid engagement_type '{v}'. Must be one of: {sorted(valid)}")
        return v


class EngagementUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None
    engagement_type: Optional[str] = None
    filing_deadline: Optional[date] = None
    extended_deadline: Optional[date] = None

    @field_validator("engagement_type")
    @classmethod
    def validate_engagement_type(cls, v):
        if v is None:
            return v
        valid = {e.value for e in EngagementType}
        if v not in valid:
            raise ValueError(f"Invalid engagement_type '{v}'. Must be one of: {sorted(valid)}")
        return v


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


class DeadlineWatchItem(BaseModel):
    engagement_id: UUID
    engagement_name: str
    client_id: UUID
    client_name: str
    engagement_type: Optional[str]
    filing_deadline: Optional[date]
    extended_deadline: Optional[date]
    effective_deadline: Optional[date]   # extended_deadline if set, else filing_deadline
    days_remaining: Optional[int]
    status: str

    model_config = ConfigDict(from_attributes=True)


class BulkEngagementFieldUpdate(BaseModel):
    status: Optional[str] = None
    deadline_push_days: Optional[int] = None


class BulkEngagementUpdate(BaseModel):
    ids: list[UUID]
    update: BulkEngagementFieldUpdate


class CalendarEngagementItem(BaseModel):
    engagement_id: UUID
    engagement_name: str
    engagement_type: Optional[str]
    client_id: UUID
    client_name: str
    effective_deadline: date
    deadline_type: str  # "extended" or "filing"
    status: str

    model_config = ConfigDict(from_attributes=True)


class CalendarResponse(BaseModel):
    items: list[CalendarEngagementItem]


class BulkEngagementCreate(BaseModel):
    client_ids: list[UUID]
    name: str
    engagement_type: Optional[str] = None
    status: Optional[str] = "planning"
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    notes: Optional[str] = None
    filing_deadline: Optional[date] = None

    @field_validator("engagement_type")
    @classmethod
    def validate_engagement_type(cls, v):
        if v is None:
            return v
        valid = {e.value for e in EngagementType}
        if v not in valid:
            raise ValueError(f"Invalid engagement_type '{v}'. Must be one of: {sorted(valid)}")
        return v


class BulkEngagementCreateResult(BaseModel):
    created: int
    engagement_ids: list[UUID]
    skipped: int


class BulkSendLetterRequest(BaseModel):
    engagement_ids: list[UUID]
    template_id: UUID
    fee_amount: Optional[str] = ""


class BulkSendLetterResult(BaseModel):
    sent: int
    failed: int
    errors: list[str]