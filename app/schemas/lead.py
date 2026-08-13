# app/schemas/lead.py

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.core.enums import (
    LeadStage,
    LeadLostReason,
    ReferralSource,
    SourcePlatform,
    LeadProvenance,
)


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
    provenance: Optional[LeadProvenance] = None
    first_response_time: Optional[int] = None


class LeadOut(LeadBase):
    id: uuid.UUID
    firm_id: uuid.UUID
    provenance: LeadProvenance
    first_response_time: Optional[int] = None
    converted_client_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
