# app/models/irs_authorization.py

import uuid
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import String, Date, DateTime, ForeignKey, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class IrsAuthorization(Base):
    """
    Tracks IRS authorization forms (8821 and 2848) for a client.

    8821 — Tax Information Authorization: allows the firm to receive
           IRS transcripts and account information on behalf of the client.
    2848 — Power of Attorney: allows the firm to represent the client
           before the IRS in audits, appeals, and other proceedings.

    Each record represents one authorization form for one client.
    A client can have multiple records (e.g. separate 8821 and 2848,
    or renewals after expiry).

    The signing flow reuses the existing SignatureEnvelope infrastructure.
    When status is 'pending_signature', a SignatureEnvelope exists with
    the pre-filled PDF. When the webhook fires and the envelope is signed,
    status transitions to 'active' and signed_document_id is populated.

    RBAC: firm_owner and manager only. Staff cannot view or create.
    """

    __tablename__ = "irs_authorizations"

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

    # "8821" or "2848" — stored as VARCHAR
    form_type: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
    )

    # pending_signature | active | expired | revoked
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending_signature",
    )

    # FK to SignatureEnvelope — set when the form is sent for signing.
    signature_envelope_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("signature_envelopes.id", ondelete="SET NULL"),
        nullable=True,
    )

    # FK to Document — set by webhook handler when signing completes.
    signed_document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Tax years this authorization covers — e.g. [2022, 2023, 2024]
    tax_years: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    valid_from: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # None = indefinite authorization (common for 8821)
    valid_until: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Prevents duplicate expiry alerts from the scheduler
    expiry_notification_sent: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
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
    firm: Mapped["Firm"] = relationship("Firm")
    client: Mapped["Client"] = relationship("Client")

    signature_envelope: Mapped[Optional["SignatureEnvelope"]] = relationship(
        "SignatureEnvelope",
        foreign_keys=[signature_envelope_id],
    )

    signed_document: Mapped[Optional["Document"]] = relationship(
        "Document",
        foreign_keys=[signed_document_id],
    )
