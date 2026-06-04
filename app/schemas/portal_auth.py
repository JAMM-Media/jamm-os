# app/schemas/portal_auth.py

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr

from app.schemas.portal_notification import PortalNotificationOut


class PortalLoginRequest(BaseModel):
    email: EmailStr
    firm_slug: Optional[str] = None  # Optional: looked up by email globally when omitted
    password: str


class PortalSetPasswordRequest(BaseModel):
    current_password: Optional[str] = None
    new_password: str
    confirm_password: str


class PortalRequestMagicLinkRequest(BaseModel):
    email: EmailStr


class PortalTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class PortalInviteRequest(BaseModel):
    client_id: UUID
    send_email: bool = False


class PortalInviteAcceptRequest(BaseModel):
    token: str
    new_password: str  # min_length enforced in the endpoint


class PortalPasswordResetRequest(BaseModel):
    email: EmailStr


class PortalPasswordResetConfirm(BaseModel):
    token: str
    new_password: str  # min_length enforced in the endpoint


class PortalDashboardOut(BaseModel):
    active_engagements: list[dict]
    pending_document_requests: list[dict]
    pending_signatures: list[dict]
    unread_notification_count: int
    recent_notifications: list[PortalNotificationOut]
