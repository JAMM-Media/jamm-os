# app/models/time_entry.py

import uuid
from datetime import date, datetime, time, timezone

from sqlalchemy import String, Boolean, DateTime, Date, ForeignKey, Numeric, Time, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional

from app.db.base_class import Base


class TimeEntry(Base):
    __tablename__ = "time_entries"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    firm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("firms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    engagement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("engagements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    invoice_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("invoices.id", ondelete="SET NULL"),
        nullable=True,
    )

    description: Mapped[str] = mapped_column(String(500), nullable=False)
    hours: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    hourly_rate: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)

    is_billable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_billed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    date: Mapped[date] = mapped_column(Date, nullable=False)

    start_time: Mapped[Optional[time]] = mapped_column(
        Time, nullable=True
    )
    end_time: Mapped[Optional[time]] = mapped_column(
        Time, nullable=True
    )
    activity_type: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    is_submitted: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    submitted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_approved: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    approved_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    edited_after_submission: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    edit_note: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    firm: Mapped["Firm"] = relationship("Firm", back_populates="time_entries")
    engagement: Mapped["Engagement"] = relationship("Engagement", back_populates="time_entries")
    user: Mapped["User"] = relationship(
        "User", back_populates="time_entries", foreign_keys=[user_id]
    )
    invoice: Mapped[Optional["Invoice"]] = relationship("Invoice", back_populates="time_entries")
    approved_by: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[approved_by_id],
        primaryjoin="TimeEntry.approved_by_id == User.id",
    )
