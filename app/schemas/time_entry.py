# app/schemas/time_entry.py

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict


class TimeEntryBase(BaseModel):
    engagement_id: uuid.UUID
    description: str
    hours: Decimal
    hourly_rate: Decimal
    is_billable: bool = True
    date: date


class TimeEntryCreate(TimeEntryBase):
    pass


class TimeEntryUpdate(BaseModel):
    description: Optional[str] = None
    hours: Optional[Decimal] = None
    hourly_rate: Optional[Decimal] = None
    is_billable: Optional[bool] = None
    date: Optional[date] = None


class TimeEntryOut(TimeEntryBase):
    id: uuid.UUID
    firm_id: uuid.UUID
    user_id: uuid.UUID
    invoice_id: Optional[uuid.UUID]
    is_billed: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
