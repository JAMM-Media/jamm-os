# app/schemas/availability_window.py

import uuid
from datetime import datetime, time
from typing import Optional

from pydantic import BaseModel, ConfigDict


class AvailabilityWindowBase(BaseModel):
    day_of_week: int
    start_time: time
    end_time: time
    buffer_before_minutes: int = 0
    buffer_after_minutes: int = 0
    meeting_duration_minutes: int
    daily_cap: Optional[int] = None


class AvailabilityWindowCreate(AvailabilityWindowBase):
    user_id: uuid.UUID


class AvailabilityWindowUpdate(BaseModel):
    day_of_week: Optional[int] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    buffer_before_minutes: Optional[int] = None
    buffer_after_minutes: Optional[int] = None
    meeting_duration_minutes: Optional[int] = None
    daily_cap: Optional[int] = None


class AvailabilityWindowOut(AvailabilityWindowBase):
    id: uuid.UUID
    firm_id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
