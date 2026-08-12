# app/schemas/referral_partner.py

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ReferralPartnerBase(BaseModel):
    name: str
    type: Optional[str] = None
    notes: Optional[str] = None


class ReferralPartnerCreate(ReferralPartnerBase):
    pass


class ReferralPartnerUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    notes: Optional[str] = None


class ReferralPartnerOut(ReferralPartnerBase):
    id: uuid.UUID
    firm_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
