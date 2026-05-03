# app/schemas/stripe_connection.py

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.core.enums import StripeConnectionStatus


class StripeConnectionOut(BaseModel):
    id: uuid.UUID
    firm_id: uuid.UUID
    stripe_account_id: str
    status: StripeConnectionStatus
    country: Optional[str]
    default_currency: Optional[str]
    charges_enabled: bool
    payouts_enabled: bool
    details_submitted: bool
    connected_at: datetime
    updated_at: datetime
    disconnected_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class StripeConnectURLOut(BaseModel):
    url: str
    state: str


class StripeConnectionStatusOut(BaseModel):
    connected: bool
    charges_enabled: bool
    payouts_enabled: bool
    details_submitted: bool
    stripe_account_id: Optional[str] = None
    message: Optional[str] = None
