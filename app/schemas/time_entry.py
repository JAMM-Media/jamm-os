# app/schemas/time_entry.py

from __future__ import annotations

import uuid
from datetime import date, datetime, time
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict


class TimeEntryBase(BaseModel):
    engagement_id: uuid.UUID
    task_id: Optional[uuid.UUID] = None
    description: str
    hours: Decimal
    hourly_rate: Decimal
    is_billable: bool = True
    date: date


class TimeEntryCreate(TimeEntryBase):
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    activity_type: Optional[str] = None


class TimeEntryUpdate(BaseModel):
    task_id: Optional[uuid.UUID] = None
    description: Optional[str] = None
    hours: Optional[Decimal] = None
    hourly_rate: Optional[Decimal] = None
    is_billable: Optional[bool] = None
    date: Optional[date] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    activity_type: Optional[str] = None


class SubmittedEditPayload(BaseModel):
    hours: Optional[Decimal] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    activity_type: Optional[str] = None
    description: Optional[str] = None
    edit_note: Optional[str] = None


class TimesheetSummaryRow(BaseModel):
    user_id: uuid.UUID
    user_name: str
    date: date
    total_hours: float
    billable_hours: float
    billable_pct: float
    entry_count: int
    is_submitted: bool
    has_edits: bool


class TimeEntryOut(TimeEntryBase):
    id: uuid.UUID
    firm_id: uuid.UUID
    user_id: uuid.UUID
    invoice_id: Optional[uuid.UUID]
    is_billed: bool
    created_at: datetime
    updated_at: datetime
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    activity_type: Optional[str] = None
    is_submitted: bool = False
    submitted_at: Optional[datetime] = None
    is_approved: bool = False
    approved_at: Optional[datetime] = None
    approved_by_id: Optional[uuid.UUID] = None
    edited_after_submission: bool = False
    edit_note: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
