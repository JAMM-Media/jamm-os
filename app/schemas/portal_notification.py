# app/schemas/portal_notification.py

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PortalNotificationBase(BaseModel):
    title: str
    body: Optional[str] = None
    notification_type: str
    related_entity_type: Optional[str] = None
    related_entity_id: Optional[UUID] = None


class PortalNotificationCreate(PortalNotificationBase):
    firm_id: UUID
    client_id: UUID
    is_pinned: bool = False


class PortalNotificationUpdate(BaseModel):
    is_read: Optional[bool] = None
    read_at: Optional[datetime] = None


class PortalNotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    firm_id: UUID
    client_id: UUID
    title: str
    body: Optional[str] = None
    notification_type: str
    is_read: bool
    is_pinned: bool
    read_at: Optional[datetime] = None
    related_entity_type: Optional[str] = None
    related_entity_id: Optional[UUID] = None
    created_at: datetime
