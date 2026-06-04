# app/schemas/document_expiry.py

from datetime import date, datetime
from typing import Optional
import uuid
from pydantic import BaseModel, ConfigDict


class DocumentExpiryBase(BaseModel):
    document_type: str
    description: Optional[str] = None
    expires_on: date
    status: str = "active"


class DocumentExpiryCreate(DocumentExpiryBase):
    client_id: uuid.UUID
    document_id: Optional[uuid.UUID] = None


class DocumentExpiryUpdate(BaseModel):
    document_type: Optional[str] = None
    description: Optional[str] = None
    expires_on: Optional[date] = None
    status: Optional[str] = None


class DocumentExpiryOut(DocumentExpiryBase):
    id: uuid.UUID
    firm_id: uuid.UUID
    client_id: uuid.UUID
    document_id: Optional[uuid.UUID] = None
    expiry_notification_sent: bool
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
