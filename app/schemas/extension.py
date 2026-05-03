# app/schemas/extension.py

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


VALID_FORM_TYPES = {"4868", "7004", "8868"}
VALID_STATUSES = {"not_filed", "filed", "confirmed"}

# Standard extended deadlines by form type.
# These are the defaults — firm can override if IRS grants a different date.
DEFAULT_EXTENDED_DEADLINES: dict[str, tuple[int, int]] = {
    "4868": (10, 15),   # October 15 for individuals
    "7004": (9, 15),    # September 15 for most businesses
    "8868": (11, 15),   # November 15 for most exempt orgs
}


class ExtensionBase(BaseModel):
    form_type: str
    filed_at: Optional[date] = None  # defaults to today server-side
    extended_deadline: Optional[date] = None  # auto-set from form_type if not provided
    status: Optional[str] = "filed"
    notes: Optional[str] = None

    @field_validator("form_type")
    @classmethod
    def validate_form_type(cls, v):
        if v not in VALID_FORM_TYPES:
            raise ValueError(
                f"form_type must be one of {sorted(VALID_FORM_TYPES)}, got '{v}'"
            )
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        if v is None:
            return v
        if v not in VALID_STATUSES:
            raise ValueError(f"Invalid status '{v}'. Must be one of: {sorted(VALID_STATUSES)}")
        return v


class ExtensionCreate(ExtensionBase):
    engagement_id: UUID
    client_id: UUID


class ExtensionUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None
    extended_deadline: Optional[date] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        if v is None:
            return v
        if v not in VALID_STATUSES:
            raise ValueError(f"Invalid status '{v}'")
        return v


class ExtensionOut(ExtensionBase):
    id: UUID
    firm_id: UUID
    client_id: UUID
    engagement_id: UUID
    filed_at: date
    extended_deadline: date
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
