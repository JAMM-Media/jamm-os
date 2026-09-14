# app/schemas/document_request_template.py

import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class DocumentRequestItem(BaseModel):
    label: str
    is_required: bool = True


class DocumentRequestTemplateBase(BaseModel):
    name: str
    engagement_type: str
    title_default: Optional[str] = None
    items: list[DocumentRequestItem] = []


class DocumentRequestTemplateCreate(DocumentRequestTemplateBase):
    pass


class DocumentRequestTemplateUpdate(BaseModel):
    name: Optional[str] = None
    engagement_type: Optional[str] = None
    title_default: Optional[str] = None
    items: Optional[list[DocumentRequestItem]] = None
    is_active: Optional[bool] = None


class DocumentRequestTemplateOut(DocumentRequestTemplateBase):
    id: uuid.UUID
    firm_id: uuid.UUID
    is_active: bool
    use_count: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
