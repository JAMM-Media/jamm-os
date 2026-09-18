# app/models/import_item.py

"""
Import item -- one file within an import batch.

One row represents a single file the browser enumerated from the dragged folder
tree. Items move from planned through uploaded, processing, and then to a
terminal status (completed, failed, skipped, or back to retryable on transient
errors).

Lease design: a future APScheduler-driven claim loop will atomically set
claimed_by + lease_expires_at on a row in planned or retryable status, then
process it. If the worker crashes, the expired lease makes the item claimable
again on the next poll. available_at provides retry backoff: after a transient
failure the worker sets available_at to a future time and status to retryable.
The claim query filters status IN (planned, retryable) AND available_at <= now.

firm_id is denormalized from the batch so item queries can always lead with
firm_id without joining import_batches, matching the pattern already used in
task_file_link.py for the same reason.

Both raw and normalized paths are stored: relative_path is exactly what the
browser provided (e.g. webkitRelativePath), normalized_relative_path is the
sanitized version used for actual folder/file creation. Storing both makes any
rejected or reinterpreted path auditable against what the browser actually sent.

final_document_id is the idempotency fence: a finalizer checks for a non-null
value before creating a Document row so a retry after a commit-then-crash never
creates the same document twice.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

import sqlalchemy as sa
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import ImportConflictPolicy, ImportItemStatus
from app.db.base_class import Base


class ImportItem(Base):
    __tablename__ = "import_items"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    import_batch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("import_batches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Denormalized from the batch for tenant-isolated item queries without joins.
    firm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("firms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Original enumeration order from the browser. Used for deterministic
    # processing and display in the pre-commit preview.
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)

    # Raw path as supplied by the browser (e.g. webkitRelativePath value).
    relative_path: Mapped[str] = mapped_column(Text, nullable=False)

    # Sanitized path used for actual folder and file creation. Stored so a
    # rejected or reinterpreted path is auditable against what was sent.
    normalized_relative_path: Mapped[str] = mapped_column(Text, nullable=False)

    filename: Mapped[str] = mapped_column(String(255), nullable=False)

    expected_bytes: Mapped[int] = mapped_column(Integer, nullable=False)

    mime_type: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    status: Mapped[str] = mapped_column(
        sa.Enum(ImportItemStatus, native_enum=False, length=20),
        nullable=False,
        default=ImportItemStatus.planned,
        index=True,
    )

    # Per-item conflict resolution override. Null means defer to the batch
    # default (import_batches.conflict_policy).
    conflict_override: Mapped[Optional[str]] = mapped_column(
        sa.Enum(ImportConflictPolicy, native_enum=False, length=20),
        nullable=True,
    )

    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Lease fields for crash-safe claim-and-retry. claimed_by is a string
    # worker/process identifier, not a FK, because this is a lease marker
    # not a durable relationship.
    claimed_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    lease_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Earliest time this item may next be claimed. Defaults to now (immediately
    # claimable). Set to a future time after a transient failure for backoff.
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # S3 key where the browser stages the file before finalization. Null until
    # the browser receives a presigned URL and confirms the upload.
    staging_s3_key: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    # The Document row this item became. Non-null is the idempotency fence: a
    # finalizer checks this before creating a Document to prevent duplicates on
    # retry after a commit-then-crash.
    final_document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
    )

    # The real folder the file landed in after any folder creation this import
    # triggered. Null until finalization resolves the destination.
    final_folder_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("document_folders.id", ondelete="SET NULL"),
        nullable=True,
    )

    error_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    error_detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
