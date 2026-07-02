# app/models/client.py

import uuid
from datetime import datetime, timezone
from typing import Optional
import sqlalchemy as sa
from sqlalchemy import String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.core.enums import ReferralSource


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # firm_id scopes this client to exactly one accounting firm.
    # A client record for "John Smith" at Firm A is completely separate
    # from a client record for "John Smith" at Firm B — even if it's the
    # same real person. This is intentional: each firm manages their own
    # client list independently.
    firm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("firms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50))

    company_name: Mapped[str | None] = mapped_column(String(200))
    tax_id: Mapped[str | None] = mapped_column(String(100))

    address_line1: Mapped[str | None] = mapped_column(String(200))
    address_line2: Mapped[str | None] = mapped_column(String(200))
    city: Mapped[str | None] = mapped_column(String(100))
    state: Mapped[str | None] = mapped_column(String(100))
    postal_code: Mapped[str | None] = mapped_column(String(20))
    country: Mapped[str | None] = mapped_column(String(100))

    quickbooks_customer_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)

    # How this client found the firm. Nullable -- required-ness is enforced in the
    # UI later, not the API, so manual create, CSV import, and Concierge paths
    # keep working without it.
    referral_source: Mapped[Optional[ReferralSource]] = mapped_column(
        sa.Enum(ReferralSource, name="referralsource", native_enum=False),
        nullable=True,
    )

    # Self-referential FK: the existing client who referred this one, when
    # referral_source is client_referral. Bare FK only -- no relationship(),
    # since nothing needs to traverse it yet.
    referring_client_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("clients.id", ondelete="SET NULL"),
        nullable=True,
    )

    # entity_type classifies the client for tax purposes.
    # individual = personal 1040 filer
    # business   = corporation, LLC, partnership
    # trust      = trust or estate requiring 1041
    # estate     = estate requiring 706 (death-related)
    entity_type: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="individual | business | trust | estate | non_profit",
    )

    entity_subtype: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="sole_proprietor | partnership | llc | s_corp | c_corp | professional_corp | revocable_trust | irrevocable_trust | charitable_trust | special_needs_trust | public_charity | private_foundation | social_welfare | other_tax_exempt",
    )

    tags: Mapped[str | None] = mapped_column(String(500))
    notes: Mapped[str | None] = mapped_column(String(2000))

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # --- Client Portal fields ---
    portal_password_hash: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    portal_invite_token: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    portal_invite_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    portal_access_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    portal_last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationship back to the Firm that owns this client.
    firm: Mapped["Firm"] = relationship("Firm", back_populates="clients")

    tasks: Mapped[list["Task"]] = relationship(
        "Task",
        back_populates="client",
        cascade="all, delete-orphan",
    )

    engagements: Mapped[list["Engagement"]] = relationship(
        "Engagement",
        back_populates="client",
        cascade="all, delete-orphan",
    )

    contacts: Mapped[list["Contact"]] = relationship(
        "Contact",
        back_populates="client",
        cascade="all, delete-orphan",
    )

    documents: Mapped[list["Document"]] = relationship(
        "Document",
        back_populates="client",
        cascade="all, delete-orphan",
    )

    document_requests: Mapped[list["DocumentRequest"]] = relationship(
        "DocumentRequest",
        back_populates="client",
        cascade="all, delete-orphan",
    )

    signature_envelopes: Mapped[list["SignatureEnvelope"]] = relationship(
        "SignatureEnvelope",
        back_populates="client",
        cascade="all, delete-orphan",
    )

    portal_sessions: Mapped[list["PortalSession"]] = relationship(
        "PortalSession",
        back_populates="client",
        cascade="all, delete-orphan",
    )

    portal_notifications: Mapped[list["PortalNotification"]] = relationship(
        "PortalNotification",
        back_populates="client",
        cascade="all, delete-orphan",
    )

    invoices: Mapped[list["Invoice"]] = relationship("Invoice", back_populates="client")