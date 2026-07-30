# app/schemas/irs_authorization_warning.py

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class IrsAuthorizationWarningBase(BaseModel):
    # Days before valid_until that this tier represents. 0 is the expiry date.
    threshold_days: int
    sent_at: datetime


class IrsAuthorizationWarningCreate(IrsAuthorizationWarningBase):
    # firm_id is injected server-side from the JWT and is never accepted here.
    authorization_id: UUID


class IrsAuthorizationWarningUpdate(BaseModel):
    threshold_days: Optional[int] = None
    sent_at: Optional[datetime] = None


class IrsAuthorizationWarningOut(IrsAuthorizationWarningBase):
    id: UUID
    firm_id: UUID
    authorization_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
