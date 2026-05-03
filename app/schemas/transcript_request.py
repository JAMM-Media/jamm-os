# app/schemas/transcript_request.py

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


VALID_TRANSCRIPT_TYPES = {
    "wage_and_income",
    "account",
    "tax_return",
    "record_of_account",
}

VALID_STATUSES = {"pending", "retrieved", "failed"}


class TranscriptRequestBase(BaseModel):
    transcript_type: str
    tax_year: int

    @field_validator("transcript_type")
    @classmethod
    def validate_transcript_type(cls, v):
        if v not in VALID_TRANSCRIPT_TYPES:
            raise ValueError(
                f"transcript_type must be one of "
                f"{sorted(VALID_TRANSCRIPT_TYPES)}, got '{v}'"
            )
        return v

    @field_validator("tax_year")
    @classmethod
    def validate_tax_year(cls, v):
        from datetime import date
        current_year = date.today().year
        if v < 2000 or v > current_year:
            raise ValueError(
                f"tax_year must be between 2000 and {current_year}"
            )
        return v


class TranscriptRequestCreate(TranscriptRequestBase):
    client_id: UUID
    # irs_authorization_id is resolved server-side from the active 8821
    # for this client — never accepted from the request body


class TranscriptRequestUpdate(BaseModel):
    status: Optional[str] = None
    retrieved_at: Optional[datetime] = None
    document_id: Optional[UUID] = None
    error_message: Optional[str] = None
    provider_reference_id: Optional[str] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        if v is None:
            return v
        if v not in VALID_STATUSES:
            raise ValueError(f"Invalid status '{v}'")
        return v


class TranscriptRequestOut(TranscriptRequestBase):
    id: UUID
    firm_id: UUID
    client_id: UUID
    irs_authorization_id: UUID
    status: str
    retrieved_at: Optional[datetime] = None
    document_id: Optional[UUID] = None
    error_message: Optional[str] = None
    provider_reference_id: Optional[str] = None
    requested_by: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
