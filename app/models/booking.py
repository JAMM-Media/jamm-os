# app/models/booking.py

import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional

from app.db.base_class import Base
from app.core.enums import BookingStatus


class Booking(Base):
    """One row per real scheduled meeting with a lead.

    start_time and end_time are full UTC timestamps (unlike AvailabilityWindow
    which stores time-of-day only), because a booking is a specific appointment
    on a specific date.

    lead_id uses ondelete=SET NULL so that booking history survives even if
    a lead record is ever removed (matching the pattern on Lead.converted_client_id).
    The contract says lost leads are never purged, but the FK is defensive.

    staff_user_id uses ondelete=RESTRICT. A staff member with real booking history
    cannot be deleted outright -- the intelligence layer depends on being able to
    trace historical meeting performance back to a specific staff member, even after
    that person leaves the firm. A firm that needs to remove a departed staff
    member's User row must go through a real off-boarding path (not yet built) that
    either reassigns or explicitly archives their booking history first. Deletion
    is deliberately blocked, not silently allowed to lose data.

    location_snapshot: captures the meeting location string (video link, phone
    number, or office address) as it existed at booking time. The underlying
    per-staff setting (not yet built) can change; a past booking's record must
    not silently reflect that change. This field is the snapshot.

    DEFERRED: the per-staff meeting location setting (video room link, phone
    number, or office address) described in section 7.2 as a "per-staff setting,
    set once" does not yet exist on User or any other model. It will be added
    to User (or a separate StaffMeetingSettings model) in a future task. When
    the booking-action endpoint is built, it will read the staff member's current
    location setting and write it into location_snapshot at booking time.
    """

    __tablename__ = "bookings"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    firm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("firms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Nullable: booking survives lead deletion.
    lead_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("leads.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # RESTRICT: deletion of a user who has bookings is blocked at the DB level.
    # Staff attribution must not be silently lost (see class docstring).
    staff_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    # Full UTC timestamps -- a specific appointment on a specific date.
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    end_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    status: Mapped[BookingStatus] = mapped_column(
        sa.Enum(BookingStatus, name="bookingstatus", native_enum=False),
        nullable=False,
        default=BookingStatus.scheduled,
        server_default="scheduled",
    )

    # Snapshot of the meeting location at booking time (video link, phone, or
    # office address). Written once when the booking is created; never updated
    # when the underlying staff setting changes.
    location_snapshot: Mapped[Optional[str]] = mapped_column(
        Text,
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

    lead: Mapped[Optional["Lead"]] = relationship("Lead", back_populates="bookings")
    staff_user: Mapped[Optional["User"]] = relationship("User", back_populates="bookings")
    firm: Mapped["Firm"] = relationship("Firm")
