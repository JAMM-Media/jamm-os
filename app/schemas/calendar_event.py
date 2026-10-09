# app/schemas/calendar_event.py

import uuid
from datetime import datetime
from typing import Optional

from pydantic import AwareDatetime, BaseModel, ConfigDict, computed_field, field_validator, model_validator


class CalendarEventBase(BaseModel):
    title: str

    @field_validator('title', mode='before')
    @classmethod
    def strip_title(cls, v: str) -> str:
        if not isinstance(v, str):
            raise ValueError('title must be a string')
        v = v.strip()
        if not 1 <= len(v) <= 255:
            raise ValueError('title must be between 1 and 255 characters')
        return v


class CalendarEventCreate(CalendarEventBase):
    start_at: AwareDatetime
    end_at: AwareDatetime
    category_id: Optional[uuid.UUID] = None
    client_id: Optional[uuid.UUID] = None
    owner_user_id: Optional[uuid.UUID] = None


class CalendarEventUpdate(BaseModel):
    title: Optional[str] = None
    start_at: Optional[AwareDatetime] = None
    end_at: Optional[AwareDatetime] = None
    category_id: Optional[uuid.UUID] = None
    client_id: Optional[uuid.UUID] = None
    owner_user_id: Optional[uuid.UUID] = None
    staff_notes: Optional[str] = None
    is_done: Optional[bool] = None

    @field_validator('title', mode='before')
    @classmethod
    def strip_title(cls, v):
        if v is None:
            return v
        if not isinstance(v, str):
            raise ValueError('title must be a string')
        v = v.strip()
        if not 1 <= len(v) <= 255:
            raise ValueError('title must be between 1 and 255 characters')
        return v

    @field_validator('staff_notes', mode='before')
    @classmethod
    def strip_staff_notes(cls, v):
        if v is None:
            return None
        if not isinstance(v, str):
            raise ValueError('staff_notes must be a string')
        v = v.strip()
        if len(v) > 2000:
            raise ValueError('staff_notes must be at most 2000 characters')
        return v if v else None

    @model_validator(mode='after')
    def _reject_explicit_nulls(self):
        for field in ('title', 'start_at', 'end_at'):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f'{field} cannot be null')
        return self


class CalendarEventDeleteRequest(BaseModel):
    reason: Optional[str] = None

    @field_validator('reason', mode='before')
    @classmethod
    def strip_reason(cls, v):
        if v is None:
            return None
        if not isinstance(v, str):
            raise ValueError('reason must be a string')
        v = v.strip()
        if len(v) > 500:
            raise ValueError('reason must be at most 500 characters')
        return v if v else None


class CalendarEventOut(BaseModel):
    id: uuid.UUID
    title: str
    start_at: datetime
    end_at: datetime
    event_timezone: str
    category_id: Optional[uuid.UUID] = None
    category_name: Optional[str] = None
    category_color: Optional[str] = None
    client_id: Optional[uuid.UUID] = None
    client_name: Optional[str] = None
    owner_user_id: Optional[uuid.UUID] = None
    owner_name: Optional[str] = None
    created_by: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None
    staff_notes: Optional[str] = None
    completed_at: Optional[datetime] = None
    delete_requested_at: Optional[datetime] = None
    delete_requested_by: Optional[uuid.UUID] = None
    delete_request_reason: Optional[str] = None

    @computed_field
    @property
    def is_done(self) -> bool:
        return self.completed_at is not None

    model_config = ConfigDict(from_attributes=True)
