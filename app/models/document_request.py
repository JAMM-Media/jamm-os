# app/models/document_request.py

import uuid
from datetime import datetime, date, timezone
from typing import Optional

from sqlalchemy import String, Integer, Date, DateTime, ForeignKey, JSON, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class DocumentRequest(Base):
    """
    A request sent to a client asking them to upload specific documents.

    Each request contains a checklist of individual items the client must
    supply (e.g. "2023 W-2", "Bank statement — January"). The overall
    status rolls up from the item-level statuses: once every required item
    is approved, the request is marked complete.

    checklist_items is a JSON array of objects, each with the shape:
        {
            "id":          "<uuid string>",
            "label":       "2023 W-2",
            "description": "Your W-2 from your primary employer.",
            "is_required": true,
            "status":      "pending"   # pending | uploaded | approved | rejected
        }
    """

    __tablename__ = "document_requests"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # Tenant isolation — every request belongs to one firm.
    firm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("firms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # The client being asked to provide documents.
    client_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # The engagement this document request belongs to.
    engagement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("engagements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Human-readable name for the request, e.g. "2024 Tax Return Documents".
    title: Mapped[str] = mapped_column(String(255), nullable=False)

    # Structured checklist stored as a JSON array. Each element is a dict
    # with keys: id, label, description, is_required, status.
    # Status values per item: pending | uploaded | approved | rejected.
    checklist_items: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    # Overall rollup status of the request.
    # pending   — no items uploaded yet
    # partial   — some items uploaded/approved, but not all required items done
    # complete  — all required items approved
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")

    # Optional deadline shown to the client on the portal.
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Tracks how many reminder emails have been sent for this request.
    reminder_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Timestamp of the most recent reminder, for throttling logic.
    last_reminder_sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Set when all required checklist items are approved.
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # server_default lets the DB fill this in even for rows inserted outside
    # the ORM (e.g. raw SQL in migrations or seed scripts).
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    firm: Mapped["Firm"] = relationship("Firm", back_populates="document_requests")
    client: Mapped["Client"] = relationship("Client", back_populates="document_requests")
    engagement: Mapped["Engagement"] = relationship("Engagement", back_populates="document_requests")
