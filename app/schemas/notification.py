# app/schemas/notification.py

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.core.enums import RecipientType, NotificationType, NotificationTier


class NotificationBase(BaseModel):
    recipient_id: UUID
    recipient_type: RecipientType
    title: str
    body: str
    notification_type: NotificationType
    tier: NotificationTier
    related_entity_type: Optional[str] = None
    related_entity_id: Optional[UUID] = None


class NotificationCreate(NotificationBase):
    """firm_id is always injected server-side from JWT — never in this schema."""
    pass


class NotificationUpdate(BaseModel):
    is_read: Optional[bool] = None


class NotificationOut(NotificationBase):
    id: UUID
    firm_id: UUID
    is_read: bool
    read_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
