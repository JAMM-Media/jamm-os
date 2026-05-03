# app/schemas/portal_session.py

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PortalSessionBase(BaseModel):
    client_id: UUID
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


class PortalSessionCreate(PortalSessionBase):
    refresh_token_hash: str
    access_jti: str
    expires_at: datetime
    firm_id: UUID


class PortalSessionUpdate(BaseModel):
    is_revoked: Optional[bool] = None
    revoked_at: Optional[datetime] = None
    revoked_by: Optional[str] = None
    last_active_at: Optional[datetime] = None
    access_jti: Optional[str] = None


class PortalSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    firm_id: UUID
    client_id: UUID
    access_jti: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime
    last_active_at: datetime
    expires_at: datetime
    is_revoked: bool
    revoked_at: Optional[datetime] = None
    revoked_by: Optional[str] = None
