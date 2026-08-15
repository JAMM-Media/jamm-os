# app/schemas/booking.py

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.core.enums import BookingStatus


class BookingBase(BaseModel):
    start_time: datetime
    end_time: datetime
    status: BookingStatus = BookingStatus.scheduled
    location_snapshot: Optional[str] = None


class BookingCreate(BookingBase):
    lead_id: Optional[uuid.UUID] = None
    staff_user_id: Optional[uuid.UUID] = None


class BookingUpdate(BaseModel):
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    status: Optional[BookingStatus] = None
    location_snapshot: Optional[str] = None


class BookingOut(BookingBase):
    id: uuid.UUID
    firm_id: uuid.UUID
    lead_id: Optional[uuid.UUID] = None
    staff_user_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
