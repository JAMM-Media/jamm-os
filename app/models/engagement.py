# app/models/engagement.py

import uuid
from datetime import datetime, date, timezone
from typing import Optional
from sqlalchemy import String, Boolean, Date, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class Engagement(Base):
    __tablename__ = "engagements"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # firm_id scopes this engagement to one accounting firm.
    firm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("firms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    client_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), default="planning")

    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)

    # Tax-specific fields — added in Phase 13A
    engagement_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
    )

    filing_deadline: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="IRS filing deadline. Auto-set from engagement_type on creation. "
                "Use extended_deadline instead if an extension has been filed.",
    )

    extended_deadline: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="Extended IRS deadline after extension filing. "
                "This field overrides filing_deadline in all scheduler checks.",
    )

    efiled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    irs_confirmation_number: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )

    @property
    def is_efileable(self) -> bool:
        from app.core.enums import EFILEABLE_ENGAGEMENT_TYPES
        return self.engagement_type in EFILEABLE_ENGAGEMENT_TYPES

    notes: Mapped[str | None] = mapped_column(Text)           # internal staff notes — never shown to client
    notes_client_visible: Mapped[str | None] = mapped_column(Text)  # shown in client portal
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    firm: Mapped["Firm"] = relationship("Firm", back_populates="engagements")
    client: Mapped["Client"] = relationship(back_populates="engagements")
    tasks: Mapped[list["Task"]] = relationship(
        "Task",
        back_populates="engagement",
        cascade="all, delete-orphan",
    )

    members: Mapped[list["EngagementMember"]] = relationship(
        "EngagementMember",
        back_populates="engagement",
        cascade="all, delete-orphan",
    )

    documents: Mapped[list["Document"]] = relationship(
        "Document",
        back_populates="engagement",
        cascade="all, delete-orphan",
    )

    document_requests: Mapped[list["DocumentRequest"]] = relationship(
        "DocumentRequest",
        back_populates="engagement",
        cascade="all, delete-orphan",
    )

    signature_envelopes: Mapped[list["SignatureEnvelope"]] = relationship(
        "SignatureEnvelope",
        back_populates="engagement",
    )

    invoices: Mapped[list["Invoice"]] = relationship("Invoice", back_populates="engagement")
    time_entries: Mapped[list["TimeEntry"]] = relationship("TimeEntry", back_populates="engagement")