# app/schemas/calendar_category.py

import re
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


class CalendarCategoryBase(BaseModel):
    name: str
    color: str
    sort_order: int = 0

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, v: str) -> str:
        if not isinstance(v, str):
            raise ValueError("name must be a string")
        v = v.strip()
        if not 1 <= len(v) <= 100:
            raise ValueError("name must be between 1 and 100 characters")
        return v

    @field_validator("color")
    @classmethod
    def validate_color(cls, v: str) -> str:
        if not _COLOR_RE.match(v):
            raise ValueError("color must match #RRGGBB (e.g. #3B82F6)")
        return v


class CalendarCategoryCreate(CalendarCategoryBase):
    pass


class CalendarCategoryUpdate(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, v):
        if v is None:
            return v
        if not isinstance(v, str):
            raise ValueError("name must be a string")
        v = v.strip()
        if not 1 <= len(v) <= 100:
            raise ValueError("name must be between 1 and 100 characters")
        return v

    @field_validator("color")
    @classmethod
    def validate_color(cls, v):
        if v is None:
            return v
        if not _COLOR_RE.match(v):
            raise ValueError("color must match #RRGGBB (e.g. #3B82F6)")
        return v

    @model_validator(mode="after")
    def _reject_explicit_nulls(self):
        for field in ("name", "color", "sort_order", "is_active"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class CalendarCategoryOut(CalendarCategoryBase):
    id: uuid.UUID
    firm_id: uuid.UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
