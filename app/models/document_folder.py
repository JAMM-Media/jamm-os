# app/models/document_folder.py

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import CheckConstraint, String, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class DocumentFolder(Base):
    """
    General-purpose named container for the filesystem build.

    Supersedes the portal-specific 'folders' table, which remains untouched
    for backward compatibility with PortalDocuments.tsx and its API endpoints.
    This table supports all three document scopes and arbitrary nesting depth.

    Scope rules (enforced by a database CHECK constraint):
      engagement:   engagement_id NOT NULL AND client_id NOT NULL
      client:       client_id NOT NULL AND engagement_id IS NULL
      firm_library: client_id IS NULL AND engagement_id IS NULL

    Nesting: parent_folder_id is self-referential with no database-level depth
    limit. A depth-20 creation tripwire must be enforced at the service layer
    when folder CRUD endpoints are added in a later phase.

    Phase 3 soft-delete note: when folder deletion is built, it must soft-delete
    the folder AND cascade the same soft-delete state to all contained documents
    (set deleted_at/deleted_by on every Document where folder_id = this folder),
    matching the document-level soft-delete pattern from Phase 3. The current
    ondelete=SET NULL on Document.folder_id handles the FK null-out for hard
    deletes but does not cascade soft-delete state -- that cascade must be
    implemented explicitly in the folder-delete service function.
    """

    __tablename__ = "document_folders"
    __table_args__ = (
        CheckConstraint(
            "(scope = 'engagement' AND engagement_id IS NOT NULL AND client_id IS NOT NULL)"
            " OR (scope = 'client' AND client_id IS NOT NULL AND engagement_id IS NULL)"
            " OR (scope = 'firm_library' AND client_id IS NULL AND engagement_id IS NULL)",
            name="ck_document_folders_scope_fk_consistency",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    firm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("firms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Discriminator enforced by the DB CHECK constraint above.
    scope: Mapped[str] = mapped_column(String(20), nullable=False)

    # Nullable; NULL for firm_library scope.
    client_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Nullable; only set for engagement scope.
    engagement_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("engagements.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Self-referential for arbitrary nesting. SET NULL so deleting a parent
    # folder makes its children top-level rather than deleting them.
    parent_folder_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("document_folders.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    firm: Mapped["Firm"] = relationship("Firm")
    client: Mapped[Optional["Client"]] = relationship("Client", foreign_keys=[client_id])
    engagement: Mapped[Optional["Engagement"]] = relationship(
        "Engagement", foreign_keys=[engagement_id]
    )
    parent: Mapped[Optional["DocumentFolder"]] = relationship(
        "DocumentFolder",
        remote_side="DocumentFolder.id",
        foreign_keys=[parent_folder_id],
    )
