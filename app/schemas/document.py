# app/schemas/document.py

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class DocumentOut(BaseModel):
    id: uuid.UUID
    firm_id: uuid.UUID
    client_id: uuid.UUID
    engagement_id: uuid.UUID
    uploaded_by: Optional[uuid.UUID]
    filename: str
    s3_key: str
    content_type: str
    size_bytes: int
    category: Optional[str] = "other"
    visibility: str = "internal"
    is_superseded: bool = False
    created_at: datetime
    updated_at: datetime
    envelope_status: Optional[str] = None
    # Enrichment fields — populated by API layer, not from DB model
    client_name: Optional[str] = None
    engagement_title: Optional[str] = None
    uploaded_by_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class DocumentSupersededUpdate(BaseModel):
    is_superseded: bool


class DocumentDownloadResponse(BaseModel):
    """Returned by the download endpoint — contains a short-lived presigned URL."""
    document_id: uuid.UUID
    filename: str
    url: str
    expires_in_seconds: int


class AuditLogOut(BaseModel):
    id: uuid.UUID
    firm_id: uuid.UUID
    document_id: Optional[uuid.UUID]
    user_id: Optional[uuid.UUID]
    action: str
    ip_address: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
