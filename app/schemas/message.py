# app/schemas/message.py

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class ClientMessageBase(BaseModel):
    body: str

    @field_validator("body")
    @classmethod
    def body_not_empty(cls, v: str) -> str:
        if len(v.strip()) < 1:
            raise ValueError("body must not be empty")
        return v


class ClientMessageCreate(ClientMessageBase):
    # sender_id and sender_role are injected server-side — never accepted from client
    pass


class ClientMessageOut(BaseModel):
    id: uuid.UUID
    firm_id: uuid.UUID
    client_id: uuid.UUID
    sender_id: Optional[uuid.UUID] = None
    sender_role: str
    body: str
    is_deleted: bool
    created_at: datetime
    sender_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class UnreadCountOut(BaseModel):
    client_id: uuid.UUID
    unread_count: int
