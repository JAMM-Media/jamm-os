# app/models/signature_envelope.py

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String, Integer, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class SignatureEnvelope(Base):
    """
    Represents an e-signature envelope sent via an external provider (e.g. Dropbox Sign).

    Tracks the full lifecycle of a signing request: draft → sent → completed (or declined/expired).
    Two Document FKs are used: document_id points to the unsigned source document,
    signed_document_id is populated via webhook once signing is complete.
    """

    __tablename__ = "signature_envelopes"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    firm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("firms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    client_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    engagement_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("engagements.id", ondelete="SET NULL"),
        nullable=True,
    )

    # The unsigned source document sent out for signing.
    document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
    )

    # The completed signed PDF — populated by webhook after all parties sign.
    signed_document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
    )

    # The e-sign provider. Defaults to Dropbox Sign; extensible for DocuSign, etc.
    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="dropbox_sign",
    )

    # The provider's own envelope/signature request ID — used for webhook correlation.
    provider_envelope_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )

    # Lifecycle status: "draft" | "sent" | "completed" | "declined" | "expired" | "cancelled"
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="draft",
    )

    # List of signer dicts: [{name, email, status, signed_at}]
    # Updated incrementally as webhook events arrive.
    signers: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    subject: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    message: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)

    sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    reminder_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    last_reminder_sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    auto_reminder_sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    escalated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    followup_task_id: Mapped[Optional[uuid.UUID]] = mapped_column(
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

    # --- Relationships ---

    firm: Mapped["Firm"] = relationship(
        "Firm",
        back_populates="signature_envelopes",
    )

    client: Mapped["Client"] = relationship(
        "Client",
        back_populates="signature_envelopes",
    )

    engagement: Mapped[Optional["Engagement"]] = relationship(
        "Engagement",
        back_populates="signature_envelopes",
    )

    # Explicit foreign_keys required because two FKs point at the same Document table.
    source_document: Mapped[Optional["Document"]] = relationship(
        "Document",
        foreign_keys=[document_id],
    )

    signed_document: Mapped[Optional["Document"]] = relationship(
        "Document",
        foreign_keys=[signed_document_id],
    )
