# app/models/import_batch.py

"""
Import batch parent record.

One row represents a single bulk-import attempt: the firm owner dragged a folder
tree into a destination (engagement, client permanent docs, or Firm Library),
the browser enumerated the files, and this row was created. The batch moves
through ImportBatchStatus states as the job progresses. ImportItem rows carry
the per-file detail.

Scope rules mirror Document and DocumentFolder exactly -- the same CHECK
constraint (ck_import_batches_scope_fk_consistency) is applied here so the
database rejects a row whose FK combination contradicts its declared scope.

destination_folder_id is the folder inside the destination into which all
files will be placed. SET NULL on folder delete: a deleted destination folder
should not destroy the batch history, but the destination reference becomes null
(the importer would need to re-resolve it before processing).

conflict_policy is the batch-level default for how filename collisions are
resolved. Import items may carry a per-item conflict_override that supersedes
this default for that file only.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

import sqlalchemy as sa
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import ImportBatchStatus, ImportConflictPolicy
from app.db.base_class import Base


class ImportBatch(Base):
    __tablename__ = "import_batches"
    __table_args__ = (
        CheckConstraint(
            "(scope = 'engagement' AND engagement_id IS NOT NULL AND client_id IS NOT NULL)"
            " OR (scope = 'client' AND client_id IS NOT NULL AND engagement_id IS NULL)"
            " OR (scope = 'firm_library' AND client_id IS NULL AND engagement_id IS NULL)",
            name="ck_import_batches_scope_fk_consistency",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # Tenant isolation -- every batch belongs to one firm.
    firm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("firms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # created_by_user_id is informational; SET NULL if the user is removed so
    # the batch itself is not cascade-deleted with the user.
    created_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # scope discriminator -- same values as Document.scope and DocumentFolder.scope.
    scope: Mapped[str] = mapped_column(String(20), nullable=False)

    client_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    engagement_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("engagements.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # The folder inside the destination where files will land.
    # SET NULL on delete: batch history is preserved even if the folder is removed.
    destination_folder_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("document_folders.id", ondelete="SET NULL"),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        sa.Enum(ImportBatchStatus, native_enum=False, length=30),
        nullable=False,
        default=ImportBatchStatus.draft,
    )

    # Batch-level conflict resolution default.
    conflict_policy: Mapped[str] = mapped_column(
        sa.Enum(ImportConflictPolicy, native_enum=False, length=20),
        nullable=False,
        default=ImportConflictPolicy.skip,
    )

    # Running counters -- updated as items are processed.
    total_files: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_files: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_files: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_files: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # confirmed_at: when the firm owner approved the preview and committed the import.
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # finished_at: when the batch reached a terminal status (completed, canceled, etc.).
    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
