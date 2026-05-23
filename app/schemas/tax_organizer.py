# app/schemas/tax_organizer.py

from datetime import datetime
from typing import Optional, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


VALID_ORGANIZER_TYPES = {"individual", "business", "rental", "custom"}
VALID_STATUSES = {"sent", "in_progress", "submitted"}


# ── Template schemas ──────────────────────────────────────────────────────────

class TaxOrganizerTemplateBase(BaseModel):
    name: str
    organizer_type: str = "custom"
    sections: list = []
    is_default: bool = False
    is_active: bool = True

    @field_validator("organizer_type")
    @classmethod
    def validate_organizer_type(cls, v):
        if v not in VALID_ORGANIZER_TYPES:
            raise ValueError(
                f"organizer_type must be one of {sorted(VALID_ORGANIZER_TYPES)}"
            )
        return v


class TaxOrganizerTemplateCreate(TaxOrganizerTemplateBase):
    pass


class TaxOrganizerTemplateUpdate(BaseModel):
    name: Optional[str] = None
    sections: Optional[list] = None
    is_active: Optional[bool] = None


class TaxOrganizerTemplateOut(TaxOrganizerTemplateBase):
    id: UUID
    firm_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Organizer schemas ─────────────────────────────────────────────────────────

class TaxOrganizerBase(BaseModel):
    tax_year: int
    client_message: Optional[str] = None


class TaxOrganizerSendRequest(TaxOrganizerBase):
    """Request body for POST /tax-organizers/send."""
    client_id: UUID
    engagement_id: UUID
    template_id: UUID

    @field_validator("tax_year")
    @classmethod
    def validate_tax_year(cls, v):
        from datetime import date
        current_year = date.today().year
        if v < 2000 or v > current_year + 1:
            raise ValueError(f"tax_year must be between 2000 and {current_year + 1}")
        return v


class TaxOrganizerOut(TaxOrganizerBase):
    id: UUID
    firm_id: UUID
    client_id: UUID
    engagement_id: UUID
    template_id: UUID
    status: str
    responses: dict
    submitted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TaxOrganizerWithTemplate(TaxOrganizerOut):
    """Extended response that includes the template sections for rendering."""
    template: TaxOrganizerTemplateOut


class PortalOrganizerSaveRequest(BaseModel):
    """Portal client saves partial or full responses."""
    responses: dict[str, Any]
    submit: bool = False  # True = client is submitting final answers
