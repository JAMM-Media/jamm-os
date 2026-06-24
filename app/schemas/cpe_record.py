# app/schemas/cpe_record.py

from datetime import date, datetime
from typing import Optional
import uuid

from pydantic import BaseModel, ConfigDict, computed_field

from app.core.enums import CPEStatus


class CPERecordBase(BaseModel):
    reporting_period_start: date
    reporting_period_end: date
    hours_required: float
    hours_completed: float = 0
    deadline: Optional[date] = None
    notes: Optional[str] = None


class CPERecordCreate(CPERecordBase):
    user_id: uuid.UUID


class CPERecordUpdate(BaseModel):
    reporting_period_start: Optional[date] = None
    reporting_period_end: Optional[date] = None
    hours_required: Optional[float] = None
    hours_completed: Optional[float] = None
    deadline: Optional[date] = None
    notes: Optional[str] = None


class CPERecordOut(CPERecordBase):
    id: uuid.UUID
    firm_id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @computed_field
    @property
    def hours_remaining(self) -> float:
        return max(0.0, float(self.hours_required) - float(self.hours_completed))

    @computed_field
    @property
    def status(self) -> CPEStatus:
        remaining = self.hours_remaining
        if remaining == 0:
            return CPEStatus.complete
        if self.deadline is not None and self.deadline < date.today() and remaining > 0:
            return CPEStatus.overdue
        return CPEStatus.in_progress
