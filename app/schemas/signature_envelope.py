# app/schemas/signature_envelope.py

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

VALID_STATUSES = {"draft", "sent", "viewed", "signed", "declined", "expired", "voided"}
VALID_PROVIDERS = {"dropbox_sign"}


class SignatureEnvelopeBase(BaseModel):
    provider: str = "dropbox_sign"
    status: str = "draft"
    subject: Optional[str] = None
    message: Optional[str] = None
    signers: list[dict] = []
    expires_at: Optional[datetime] = None


class SignatureEnvelopeCreate(SignatureEnvelopeBase):
    # firm_id is intentionally absent — injected from the JWT tenant context
    # in the route handler, never accepted from the request body.
    client_id: UUID
    engagement_id: Optional[UUID] = None
    document_id: Optional[UUID] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in VALID_STATUSES:
            raise ValueError(f"status must be one of {sorted(VALID_STATUSES)}")
        return v

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        if v not in VALID_PROVIDERS:
            raise ValueError(f"provider must be one of {sorted(VALID_PROVIDERS)}")
        return v


class SignatureEnvelopeUpdate(BaseModel):
    status: Optional[str] = None
    subject: Optional[str] = None
    message: Optional[str] = None
    signers: Optional[list[dict]] = None
    expires_at: Optional[datetime] = None
    provider_envelope_id: Optional[str] = None
    sent_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    reminder_count: Optional[int] = None
    last_reminder_sent_at: Optional[datetime] = None
    signed_document_id: Optional[UUID] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_STATUSES:
            raise ValueError(f"status must be one of {sorted(VALID_STATUSES)}")
        return v


class SignatureEnvelopeOut(SignatureEnvelopeBase):
    id: UUID
    firm_id: UUID
    client_id: UUID
    engagement_id: Optional[UUID] = None
    document_id: Optional[UUID] = None
    signed_document_id: Optional[UUID] = None
    provider_envelope_id: Optional[str] = None
    sent_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    reminder_count: int = 0
    last_reminder_sent_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
