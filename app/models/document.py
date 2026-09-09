# app/models/document.py

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, CheckConstraint, String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class Document(Base):
    """
    Represents a file stored in S3, scoped to a firm and optionally to a client
    and/or engagement.

    Scope rules (enforced by a database CHECK constraint):
      engagement:   engagement_id NOT NULL AND client_id NOT NULL
      client:       client_id NOT NULL AND engagement_id IS NULL
      firm_library: client_id IS NULL AND engagement_id IS NULL

    Source:
      staff:  uploaded by a staff member (uploaded_by is set)
      client: uploaded via the client portal (source_client_id is set, uploaded_by null)
      system: auto-generated (both uploaded_by and source_client_id are null)

    Triage status:
      pending: newly client-uploaded, awaiting staff review/filing (Phase 5)
      filed:   placed in a final location; no further triage needed
    """

    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint(
            "(scope = 'engagement' AND engagement_id IS NOT NULL AND client_id IS NOT NULL)"
            " OR (scope = 'client' AND client_id IS NOT NULL AND engagement_id IS NULL)"
            " OR (scope = 'firm_library' AND client_id IS NULL AND engagement_id IS NULL)",
            name="ck_documents_scope_fk_consistency",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # Tenant isolation -- every document belongs to one firm.
    firm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("firms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # client_id is nullable to support firm_library-scoped documents.
    # For engagement and client scopes it is always populated.
    client_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    engagement_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("engagements.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Discriminator enforced by the DB CHECK constraint above.
    scope: Mapped[str] = mapped_column(String(20), nullable=False)

    # Who uploaded this document. SET NULL so the document survives if the
    # user is deleted. Null for client-sourced and system-generated documents.
    uploaded_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Upload source classification.
    # staff:  uploaded by a staff member (uploaded_by is set)
    # client: uploaded via the portal (source_client_id is set)
    # system: auto-generated (e.g. signed PDFs from e-sign flow)
    source: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="staff",
    )

    # The portal client who uploaded this document, when source='client'.
    # Distinct from client_id, which records whose document binder this belongs to.
    source_client_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("clients.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Triage lifecycle. 'filed' means the document is placed; 'pending' means
    # it awaits staff review. New uploads default to 'filed' until the Phase 5
    # triage tray is built -- do NOT change this default before Phase 5 ships,
    # or client-uploaded files will become invisible to staff.
    triage_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="filed",
    )

    # Optional note from the client explaining what they are uploading.
    # Populated only for client-sourced uploads; null for staff and system.
    client_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # The original filename as provided by the uploader.
    filename: Mapped[str] = mapped_column(String(255), nullable=False)

    # Full S3 object key. Unique constraint prevents accidental overwrites.
    s3_key: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)

    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)

    # Document category for filtering and display.
    # Values: tax_document | irs_transcript | irs_authorization |
    #         engagement_letter | tax_organizer_response |
    #         bank_statement | signed_letter | other
    category: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        default="other",
    )

    is_superseded: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    # Visibility controls whether this document appears in the client portal.
    # internal       = staff only, never shown in portal
    # client_visible = shown in client portal documents tab
    visibility: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="internal",
    )

    # Folder assignment. NULL means the document lives at root level.
    #
    # TODO(filesystem-phase-4): this column currently has NO database-level FK
    # constraint. It holds a document_folders.id when set by staff-side move/copy
    # operations (Phase 4 Task 2), or a folders.id (old portal-era table) when set
    # by the portal move endpoint -- two different tables, one column, no way to
    # tell which from the value alone.
    #
    # This is a deliberate, temporary state, not an oversight. The real fix is
    # migrating the portal's GET /portal/folders endpoint and PortalDocuments.tsx
    # off the old 'folders' table and onto 'document_folders' entirely, then
    # dropping the old 'folders' table for good. That migration is scoped as its
    # own separate task (supersede old folders, D4 decision made 2026-09-09) and
    # is NOT solved here.
    #
    # Until that task ships: application-layer checks enforce which table is in
    # use for a given write path. See app/api/portal.py (portal_move_document)
    # and app/services/document_service.py (move_document, copy_document).
    folder_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        nullable=True,
        index=True,
    )

    # Soft delete support (Phase 3). The existing hard-delete endpoint is not
    # changed by this task; these columns are wired in Phase 3.
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    deleted_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Provenance for copied documents. Not a FK -- the source may be in a
    # different scope or may have been purged after the copy was made.
    copied_from_document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    firm: Mapped["Firm"] = relationship("Firm", back_populates="documents")
    client: Mapped[Optional["Client"]] = relationship(
        "Client", foreign_keys=[client_id], back_populates="documents"
    )
    source_client: Mapped[Optional["Client"]] = relationship(
        "Client", foreign_keys=[source_client_id]
    )
    engagement: Mapped[Optional["Engagement"]] = relationship(
        "Engagement", back_populates="documents"
    )
    uploader: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[uploaded_by]
    )
    deleter: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[deleted_by]
    )
    folder: Mapped[Optional["DocumentFolder"]] = relationship(
        "DocumentFolder",
        primaryjoin="Document.folder_id == DocumentFolder.id",
        foreign_keys="[Document.folder_id]",
    )
    audit_logs: Mapped[list["DocumentAuditLog"]] = relationship(
        "DocumentAuditLog",
        back_populates="document",
        cascade="all, delete-orphan",
    )


class DocumentAuditLog(Base):
    """
    Immutable record of every significant action taken on a document.

    Written on: upload, download, delete.
    Never updated -- append-only by design.
    """

    __tablename__ = "document_audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    firm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("firms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Nullable so audit records survive document deletion.
    document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Nullable so audit records survive user deletion.
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # "upload" | "download" | "delete"
    action: Mapped[str] = mapped_column(String(50), nullable=False)

    # Stored for security auditing. IPv6 max length is 45 chars.
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    document: Mapped[Optional["Document"]] = relationship(
        "Document", back_populates="audit_logs"
    )
    user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[user_id])
