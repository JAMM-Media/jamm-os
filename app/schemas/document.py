# app/schemas/document.py

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class DocumentOut(BaseModel):
    id: uuid.UUID
    firm_id: uuid.UUID
    client_id: Optional[uuid.UUID] = None
    engagement_id: Optional[uuid.UUID] = None
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
    # Soft-delete fields (Phase 3): present in trash list; null for live documents.
    deleted_at: Optional[datetime] = None
    deleted_by: Optional[uuid.UUID] = None
    folder_id: Optional[uuid.UUID] = None
    # Enrichment fields -- populated by API layer, not from DB model
    client_name: Optional[str] = None
    engagement_title: Optional[str] = None
    uploaded_by_name: Optional[str] = None
    copied_from_document_id: Optional[uuid.UUID] = None
    triage_status: str = "filed"
    client_note: Optional[str] = None
    description: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class DocumentSupersededUpdate(BaseModel):
    is_superseded: bool


class DocumentDownloadResponse(BaseModel):
    document_id: uuid.UUID
    filename: str
    url: str
    expires_in_seconds: int


class PurgeConfirm(BaseModel):
    """Body required for single-document permanent purge (Phase 3)."""
    confirm: bool


class PurgeAllConfirm(BaseModel):
    """Body required for trash/purge-all (Phase 3)."""
    confirm: bool
    scope: Optional[str] = None           # "engagement" | "client" | "firm_library" | None (whole firm)
    engagement_id: Optional[uuid.UUID] = None
    client_id: Optional[uuid.UUID] = None


class AuditLogOut(BaseModel):
    id: uuid.UUID
    firm_id: uuid.UUID
    document_id: Optional[uuid.UUID]
    user_id: Optional[uuid.UUID]
    action: str
    ip_address: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UploadUrlRequest(BaseModel):
    client_id: Optional[uuid.UUID] = None
    engagement_id: Optional[uuid.UUID] = None
    filename: str
    content_type: str
    folder_id: Optional[uuid.UUID] = None


class UploadUrlResponse(BaseModel):
    document_id: uuid.UUID
    upload_url: str
    s3_key: str
    expires_in_seconds: int


class DuplicateConflict(BaseModel):
    existing_id: uuid.UUID
    filename: str


class UploadCompleteRequest(BaseModel):
    filename: str
    content_type: str
    client_id: Optional[uuid.UUID] = None
    engagement_id: Optional[uuid.UUID] = None
    folder_id: Optional[uuid.UUID] = None
    duplicate_action: Optional[str] = None  # "replace" | "keep_both"
    description: Optional[str] = None


class UploadCompleteResponse(BaseModel):
    document: Optional[DocumentOut] = None
    conflict: Optional[DuplicateConflict] = None


class DocumentRenameRequest(BaseModel):
    filename: str


class DocumentMoveRequest(BaseModel):
    folder_id: Optional[uuid.UUID] = None
    engagement_id: Optional[uuid.UUID] = None
    client_id: Optional[uuid.UUID] = None


class DocumentCopyRequest(BaseModel):
    folder_id: Optional[uuid.UUID] = None
    duplicate_action: Optional[str] = None


class DocumentPreviewResponse(BaseModel):
    document_id: uuid.UUID
    preview_available: bool
    url: Optional[str] = None
    expires_in_seconds: Optional[int] = None
    reason: Optional[str] = None
