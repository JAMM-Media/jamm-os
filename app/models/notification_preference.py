# app/models/notification_preference.py

import uuid
from datetime import datetime

from sqlalchemy import UniqueConstraint, ForeignKey, DateTime
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base_class import Base
from app.core.enums import RecipientType, NotificationEventType, NotificationChannel


class NotificationPreference(Base):
    """
    Per-recipient preference for how each notification event type is delivered.

    One row per (firm_id, recipient_id, recipient_type, event_type).
    If no row exists for a given event type, the default channel is "both".
    recipient_id is a soft reference — no FK constraint (same pattern as Notification).
    """

    __tablename__ = "notification_preferences"

    __table_args__ = (
        UniqueConstraint(
            "firm_id", "recipient_id", "recipient_type", "event_type",
            name="uq_notif_pref_recipient_event",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    firm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("firms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Polymorphic soft reference — no FK
    recipient_id: Mapped[uuid.UUID] = mapped_column(nullable=False)

    recipient_type: Mapped[RecipientType] = mapped_column(
        SAEnum(RecipientType, name="recipienttype", native_enum=False),
        nullable=False,
    )

    event_type: Mapped[NotificationEventType] = mapped_column(
        SAEnum(NotificationEventType, name="notificationeventtype", native_enum=False),
        nullable=False,
    )

    channel: Mapped[NotificationChannel] = mapped_column(
        SAEnum(NotificationChannel, name="notificationchannel", native_enum=False),
        nullable=False,
        default=NotificationChannel.both,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # --- Relationships ---
    firm: Mapped["Firm"] = relationship("Firm", back_populates="notification_preferences")
