# app/schemas/note.py

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class NoteBase(BaseModel):
    body: str
    is_private: bool = False

    @field_validator("body")
    @classmethod
    def body_not_empty(cls, v: str) -> str:
        if len(v.strip()) < 1:
            raise ValueError("body must contain at least one character")
        return v


class NoteCreate(NoteBase):
    entity_type: str
    entity_id: uuid.UUID


class NoteMarkReadRequest(BaseModel):
    entity_type: str
    entity_id: uuid.UUID


class NoteUpdate(BaseModel):
    body: str

    @field_validator("body")
    @classmethod
    def body_not_empty(cls, v: str) -> str:
        if len(v.strip()) < 1:
            raise ValueError("body must contain at least one character")
        return v


class NoteOut(NoteBase):
    id: uuid.UUID
    firm_id: uuid.UUID
    entity_type: str
    entity_id: uuid.UUID
    author_id: uuid.UUID
    is_deleted: bool
    is_read: bool = False
    created_at: datetime
    updated_at: datetime
    author_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
