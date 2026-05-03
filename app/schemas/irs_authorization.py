# app/schemas/irs_authorization.py

from datetime import date, datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


VALID_FORM_TYPES = {"8821", "2848"}
VALID_STATUSES = {"pending_signature", "active", "expired", "revoked"}


class IrsAuthorizationBase(BaseModel):
    form_type: str
    tax_years: List[int] = []
    valid_from: Optional[date] = None
    valid_until: Optional[date] = None

    @field_validator("form_type")
    @classmethod
    def validate_form_type(cls, v):
        if v not in VALID_FORM_TYPES:
            raise ValueError(f"form_type must be '8821' or '2848', got '{v}'")
        return v

    @field_validator("tax_years")
    @classmethod
    def validate_tax_years(cls, v):
        current_year = date.today().year
        for year in v:
            if not isinstance(year, int):
                raise ValueError("Each tax year must be an integer")
            if year < 2000 or year > current_year + 1:
                raise ValueError(f"Tax year {year} is out of valid range (2000–{current_year + 1})")
        return sorted(set(v))


class IrsAuthorizationCreate(IrsAuthorizationBase):
    client_id: UUID


class IrsAuthorizationUpdate(BaseModel):
    status: Optional[str] = None
    tax_years: Optional[List[int]] = None
    valid_from: Optional[date] = None
    valid_until: Optional[date] = None
    signature_envelope_id: Optional[UUID] = None
    signed_document_id: Optional[UUID] = None
    expiry_notification_sent: Optional[bool] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        if v is None:
            return v
        if v not in VALID_STATUSES:
            raise ValueError(f"Invalid status '{v}'. Must be one of: {sorted(VALID_STATUSES)}")
        return v


class IrsAuthorizationOut(IrsAuthorizationBase):
    id: UUID
    firm_id: UUID
    client_id: UUID
    status: str
    signature_envelope_id: Optional[UUID] = None
    signed_document_id: Optional[UUID] = None
    expiry_notification_sent: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class IrsAuthorizationSendRequest(BaseModel):
    """Request body for POST /irs-authorizations/send."""
    client_id: UUID
    form_type: str
    tax_years: List[int] = []
    valid_from: Optional[date] = None
    valid_until: Optional[date] = None

    @field_validator("form_type")
    @classmethod
    def validate_form_type(cls, v):
        if v not in VALID_FORM_TYPES:
            raise ValueError(f"form_type must be '8821' or '2848', got '{v}'")
        return v

    @field_validator("tax_years")
    @classmethod
    def validate_tax_years(cls, v):
        current_year = date.today().year
        for year in v:
            if not isinstance(year, int):
                raise ValueError("Each tax year must be an integer")
            if year < 2000 or year > current_year + 1:
                raise ValueError(f"Tax year {year} is out of valid range")
        return sorted(set(v))
