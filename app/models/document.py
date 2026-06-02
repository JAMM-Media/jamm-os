# app/models/document.py

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class Document(Base):
    """
    Represents a file stored in S3 and linked to a client + engagement.

    The file itself never lives on the application server. Only the S3 key,
    metadata, and a reference to the owning firm/client/engagement are stored
    here. Downloads are served exclusively via short-lived presigned URLs.
    """

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # Tenant isolation — every document belongs to one firm.
    firm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("firms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Documents are dual-keyed: they belong to both a client and an engagement.
    client_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    engagement_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("engagements.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Who uploaded this document. SET NULL so the document survives if the
    # user is deleted (e.g. a staff member leaves the firm).
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # The original filename as provided by the uploader.
    filename: Mapped[str] = mapped_column(String(255), nullable=False)

    # Full S3 object key: {firm_id}/{client_id}/{engagement_id_or_none}/{doc_id}/{filename}
    # Unique constraint prevents accidental overwrites.
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
    client: Mapped["Client"] = relationship("Client", back_populates="documents")
    engagement: Mapped["Engagement"] = relationship("Engagement", back_populates="documents")
    uploader: Mapped["User | None"] = relationship("User", foreign_keys=[uploaded_by])
    audit_logs: Mapped[list["DocumentAuditLog"]] = relationship(
        "DocumentAuditLog",
        back_populates="document",
        cascade="all, delete-orphan",
    )


class DocumentAuditLog(Base):
    """
    Immutable record of every significant action taken on a document.

    Written on: upload, download, delete.
    Never updated — append-only by design.
    """

    __tablename__ = "document_audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    firm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("firms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Nullable so audit records survive document deletion.
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Nullable so audit records survive user deletion.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # "upload" | "download" | "delete"
    action: Mapped[str] = mapped_column(String(50), nullable=False)

    # Stored for security auditing. IPv6 max length is 45 chars.
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    document: Mapped["Document | None"] = relationship("Document", back_populates="audit_logs")
    user: Mapped["User | None"] = relationship("User", foreign_keys=[user_id])

