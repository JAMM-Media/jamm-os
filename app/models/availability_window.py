# app/models/availability_window.py

import uuid
from datetime import datetime, time, timezone

import sqlalchemy as sa
from sqlalchemy import DateTime, ForeignKey, Integer, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class AvailabilityWindow(Base):
    """Per-staff weekly availability window for native booking.

    One row = one day-of-week slot for one staff member. A staff member may
    have multiple rows (e.g. different hours on different days).

    day_of_week follows Python's datetime.weekday() convention: 0=Monday,
    6=Sunday.

    meeting_duration_minutes and daily_cap are logically per-staff settings
    (uniform across all windows for a given user) but are stored here for
    simplicity in this foundation task. They can be extracted to User or a
    separate StaffSchedulingSettings model if that proves cleaner once the
    booking engine is built.
    """

    __tablename__ = "availability_windows"

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "day_of_week",
            name="uq_availability_window_user_day",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    firm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("firms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # 0=Monday ... 6=Sunday (Python weekday() convention).
    day_of_week: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    start_time: Mapped[time] = mapped_column(
        Time,
        nullable=False,
    )

    end_time: Mapped[time] = mapped_column(
        Time,
        nullable=False,
    )

    # Minutes of unbooked time required immediately before each meeting.
    buffer_before_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    # Minutes of unbooked time required immediately after each meeting.
    buffer_after_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    # How long each bookable meeting slot is, in minutes.
    meeting_duration_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    # Maximum meetings this staff member will take in a single calendar day.
    # NULL means no cap enforced.
    daily_cap: Mapped[int | None] = mapped_column(
        Integer,
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

    user: Mapped["User"] = relationship("User", back_populates="availability_windows")
    firm: Mapped["Firm"] = relationship("Firm")
