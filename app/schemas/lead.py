# app/schemas/lead.py

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

from app.core.enums import (
    EngagementType,
    LeadStage,
    LeadLostReason,
    ReferralSource,
    SourcePlacement,
    SourcePlatform,
    LeadProvenance,
)
from app.schemas.enrollment import EnrollmentOut


class LeadBase(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    stage: LeadStage = LeadStage.identified
    lost_reason: Optional[LeadLostReason] = None
    referral_source: Optional[ReferralSource] = None
    source_platform: Optional[SourcePlatform] = None
    utm_campaign: Optional[str] = None
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_content: Optional[str] = None
    utm_term: Optional[str] = None
    referring_client_id: Optional[uuid.UUID] = None
    referral_partner_id: Optional[uuid.UUID] = None
    service_interest: Optional[str] = None
    entity_type: Optional[str] = None
    revenue_band: Optional[str] = None
    urgency: Optional[str] = None
    hot: bool = False

    @field_validator("service_interest", mode="before")
    @classmethod
    def validate_service_interest(cls, v: object) -> object:
        if v is None:
            return v
        valid = {e.value for e in EngagementType}
        if v not in valid:
            raise ValueError(
                f"service_interest must be a valid EngagementType value, got {v!r}. "
                f"Valid values include: tax_return_1040, bookkeeping_monthly, payroll_tax_941, etc."
            )
        return v


class LeadCreate(LeadBase):
    provenance: LeadProvenance


class LeadUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    stage: Optional[LeadStage] = None
    lost_reason: Optional[LeadLostReason] = None
    referral_source: Optional[ReferralSource] = None
    source_platform: Optional[SourcePlatform] = None
    utm_campaign: Optional[str] = None
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_content: Optional[str] = None
    utm_term: Optional[str] = None
    referring_client_id: Optional[uuid.UUID] = None
    referral_partner_id: Optional[uuid.UUID] = None
    service_interest: Optional[str] = None
    entity_type: Optional[str] = None
    revenue_band: Optional[str] = None
    urgency: Optional[str] = None
    hot: Optional[bool] = None

    @field_validator("service_interest", mode="before")
    @classmethod
    def validate_service_interest(cls, v: object) -> object:
        if v is None:
            return v
        valid = {e.value for e in EngagementType}
        if v not in valid:
            raise ValueError(
                f"service_interest must be a valid EngagementType value, got {v!r}. "
                f"Valid values include: tax_return_1040, bookkeeping_monthly, payroll_tax_941, etc."
            )
        return v
    provenance: Optional[LeadProvenance] = None
    first_response_time: Optional[int] = None


class LeadOut(LeadBase):
    id: uuid.UUID
    firm_id: uuid.UUID
    provenance: LeadProvenance
    # Read-only. Derived at public intake from the UTM tags and never
    # accepted from a client, which is why it appears here and not on
    # LeadBase (R3, Sep 17, 2026).
    source_placement: Optional[SourcePlacement] = None
    first_response_time: Optional[int] = None
    converted_client_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LeadDetail(LeadOut):
    """Single-lead GET response. Extends LeadOut with data not needed
    in the list endpoint. actionable_enrollments carries enrollments
    that require a manager action (held_for_approval or completed_dead_end)."""
    actionable_enrollments: list[EnrollmentOut] = []
