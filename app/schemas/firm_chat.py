# app/schemas/firm_chat.py

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class ChannelBase(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v or len(v.strip()) == 0:
            raise ValueError("name must not be empty")
        if len(v) > 100:
            raise ValueError("name must be 100 characters or fewer")
        return v


class ChannelCreate(ChannelBase):
    pass


class ChannelUpdate(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v or len(v.strip()) == 0:
            raise ValueError("name must not be empty")
        if len(v) > 100:
            raise ValueError("name must be 100 characters or fewer")
        return v


class ChannelOut(BaseModel):
    id: uuid.UUID
    firm_id: uuid.UUID
    name: str
    created_by: Optional[uuid.UUID] = None
    created_at: datetime
    is_deleted: bool
    unread_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class FirmMessageCreate(BaseModel):
    body: str
    mentions: list[uuid.UUID] = []

    @field_validator("body")
    @classmethod
    def body_not_empty(cls, v: str) -> str:
        if not v or len(v.strip()) == 0:
            raise ValueError("body must not be empty")
        return v


class FirmMessageOut(BaseModel):
    id: uuid.UUID
    firm_id: uuid.UUID
    channel_id: uuid.UUID
    sender_id: Optional[uuid.UUID] = None
    body: str
    attachment_key: Optional[str] = None
    attachment_url: Optional[str] = None  # signed URL, populated by service
    mentions: Optional[list[uuid.UUID]] = []
    created_at: datetime
    is_deleted: bool
    sender_name: Optional[str] = None  # populated by service

    model_config = ConfigDict(from_attributes=True)


class FirmChatUnreadOut(BaseModel):
    total_unread: int
    per_channel: dict[str, int]  # channel_id (str) -> unread count


class ChannelMemberOut(BaseModel):
    id: uuid.UUID
    channel_id: uuid.UUID
    user_id: uuid.UUID
    user_full_name: str
    user_email: str
    added_at: datetime

    model_config = ConfigDict(from_attributes=True)
