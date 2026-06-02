# app/models/extension.py

import uuid
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import String, Date, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class Extension(Base):
    """
    Records an IRS extension filing for a specific engagement.

    When a firm files an extension, the IRS grants extra time to submit
    the return. This record captures which form was filed and what the
    new deadline is. On creation, the linked Engagement's extended_deadline
    field is updated automatically — that field is what the deadline
    scheduler and all UI components use going forward.

    Form types:
      4868 — Individual income tax (extends 1040 deadline to Oct 15)
      7004 — Business returns (extends 1120/1065/1120S to Sep 15)
      8868 — Exempt organization returns (extends to Nov 15)

    RBAC: manager and firm_owner only can file extensions.
    Staff can read but not create or update.
    """

    __tablename__ = "extensions"

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

    engagement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("engagements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # "4868" | "7004" | "8868"
    form_type: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
    )

    # Date the extension was filed with the IRS
    filed_at: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        default=date.today,
    )

    # The new IRS deadline after extension.
    # This value is written to Engagement.extended_deadline on creation.
    extended_deadline: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    # not_filed | filed | confirmed
    # confirmed = IRS acceptance received (manual update by firm)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="filed",
    )

    notes: Mapped[Optional[str]] = mapped_column(
        String(500),
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
    firm: Mapped["Firm"] = relationship("Firm")
    client: Mapped["Client"] = relationship("Client")
    engagement: Mapped["Engagement"] = relationship("Engagement")
