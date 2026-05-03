# app/schemas/integration.py

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class IntegrationBase(BaseModel):
    provider: str
    status: str


class IntegrationCreate(BaseModel):
    provider: str


class IntegrationUpdate(BaseModel):
    status: Optional[str] = None
    error_message: Optional[str] = None
    last_synced_at: Optional[datetime] = None


class QuickBooksConnectResponse(BaseModel):
    authorization_url: str


class IntegrationOut(BaseModel):
    id: uuid.UUID
    firm_id: uuid.UUID
    provider: str
    status: str
    token_expires_at: Optional[datetime] = None
    scopes: Optional[str] = None
    external_account_id: Optional[str] = None
    connected_at: Optional[datetime] = None
    last_synced_at: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
