# app/schemas/import_batch.py

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict

from app.core.enums import ImportBatchStatus, ImportConflictPolicy, ImportItemStatus


# ---------------------------------------------------------------------------
# Item schemas
# ---------------------------------------------------------------------------

class ImportItemBase(BaseModel):
    relative_path: str
    filename: str
    expected_bytes: int
    mime_type: Optional[str] = None
    conflict_override: Optional[ImportConflictPolicy] = None


class ImportItemCreate(ImportItemBase):
    """Per-file entry submitted by the browser.
    firm_id, import_batch_id, ordinal, and normalized_relative_path are
    never accepted from the client -- they are computed server-side."""
    pass


class ImportItemOut(ImportItemBase):
    id: uuid.UUID
    import_batch_id: uuid.UUID
    firm_id: uuid.UUID
    ordinal: int
    normalized_relative_path: str
    status: ImportItemStatus
    attempt_count: int
    available_at: datetime
    staging_s3_key: Optional[str] = None
    final_document_id: Optional[uuid.UUID] = None
    final_folder_id: Optional[uuid.UUID] = None
    error_code: Optional[str] = None
    error_detail: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Batch schemas
# ---------------------------------------------------------------------------

class ImportBatchBase(BaseModel):
    scope: str
    client_id: Optional[uuid.UUID] = None
    engagement_id: Optional[uuid.UUID] = None
    destination_folder_id: Optional[uuid.UUID] = None
    conflict_policy: ImportConflictPolicy


class ImportBatchCreate(ImportBatchBase):
    """Submitted by the browser after enumerating the folder tree.
    firm_id and created_by_user_id are never accepted from the client."""
    items: List[ImportItemCreate]


class ImportBatchUpdate(BaseModel):
    """Currently unused in Phase 2. Reserved for future cancel action."""
    pass


class ImportBatchOut(ImportBatchBase):
    id: uuid.UUID
    firm_id: uuid.UUID
    created_by_user_id: Optional[uuid.UUID] = None
    status: ImportBatchStatus
    total_files: int
    total_bytes: int
    completed_files: int
    failed_files: int
    skipped_files: int
    last_error: Optional[str] = None
    created_at: datetime
    confirmed_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    items: List[ImportItemOut] = []

    model_config = ConfigDict(from_attributes=True)


class ItemUploadUrlOut(BaseModel):
    """Response from POST /import-batches/{batch_id}/items/{item_id}/upload-url."""
    item_id: uuid.UUID
    upload_url: str
    staging_s3_key: str
    expires_in_seconds: int


# ---------------------------------------------------------------------------
# Preview schemas
# ---------------------------------------------------------------------------

class ImportItemPreview(BaseModel):
    """Per-item result from the read-only conflict preview endpoint."""
    item_id: uuid.UUID
    resolved: bool
    has_conflict: bool
    existing_document_id: Optional[uuid.UUID] = None
    existing_document_filename: Optional[str] = None


class ImportBatchPreview(BaseModel):
    """Response from GET /import-batches/{batch_id}/preview."""
    batch_id: uuid.UUID
    items: List[ImportItemPreview]
