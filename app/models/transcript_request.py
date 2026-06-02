# app/models/transcript_request.py

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class TranscriptRequest(Base):
    """
    Tracks an IRS transcript request for a client.

    Transcript types:
      wage_and_income   — W-2s, 1099s, other income documents the IRS has
      account           — Account balance, payment history, penalties, interest
      tax_return        — Copy of a previously filed return
      record_of_account — Combination of account + tax return transcripts

    Requires an active Form 8821 (Tax Information Authorization) before
    a request can be submitted. The irs_authorization_id FK enforces this
    at the data layer.

    The actual IRS API call (via IRS e-Services TDS or a third-party
    provider like SurePrep) is stubbed in this phase. The stub sets
    status to 'pending' and logs the request. When the live integration
    is configured post-launch, only the service layer changes — the
    model, API, and tests stay identical.

    When a transcript is retrieved, it is stored in S3 and a Document
    record is created (category='irs_transcript'). The document_id FK
    is set at that point.

    RBAC: manager and firm_owner only.
    """

    __tablename__ = "transcript_requests"

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

    # The 8821 authorization that covers this request.
    # Required — cannot request a transcript without active authorization.
    irs_authorization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("irs_authorizations.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # wage_and_income | account | tax_return | record_of_account
    transcript_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    # The tax year being requested, e.g. 2023
    tax_year: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    # pending | retrieved | failed
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
    )

    # Set when transcript is successfully retrieved and stored in S3
    retrieved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # FK to Document — set when the retrieved PDF is stored
    # Document will have category='irs_transcript'
    document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Error message if status = 'failed'
    error_message: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )

    # Reference ID returned by the IRS API or third-party provider
    # Used for polling and correlation. Null until request is submitted.
    provider_reference_id: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
    )

    requested_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
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
    irs_authorization: Mapped["IrsAuthorization"] = relationship(
        "IrsAuthorization",
        foreign_keys=[irs_authorization_id],
    )
    document: Mapped[Optional["Document"]] = relationship(
        "Document",
        foreign_keys=[document_id],
    )
    requested_by_user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[requested_by],
    )
