# app/schemas/notification_preference.py

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.core.enums import RecipientType, NotificationEventType, NotificationChannel


class NotificationPreferenceBase(BaseModel):
    recipient_id: UUID
    recipient_type: RecipientType
    event_type: NotificationEventType
    channel: NotificationChannel = NotificationChannel.both


class NotificationPreferenceCreate(NotificationPreferenceBase):
    """firm_id is always injected server-side — never in this schema."""
    pass


class NotificationPreferenceUpdate(BaseModel):
    channel: NotificationChannel


class NotificationPreferenceOut(NotificationPreferenceBase):
    id: UUID
    firm_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
