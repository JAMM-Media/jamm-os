# app/models/notification.py

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base_class import Base
from app.core.enums import RecipientType, NotificationType, NotificationTier


class Notification(Base):
    """
    In-app notification for any recipient type (staff or client).

    recipient_id is a soft reference — no FK constraint because it can point
    to either users or client_portal_users depending on recipient_type.
    related_entity_type + related_entity_id are also soft references so they
    survive deletion of the referenced entity.
    Notifications are immutable once created — no updated_at.
    """

    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    firm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("firms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Polymorphic soft reference — no FK so it can point to users OR portal clients
    recipient_id: Mapped[uuid.UUID] = mapped_column(nullable=False)

    recipient_type: Mapped[RecipientType] = mapped_column(
        SAEnum(RecipientType, name="recipienttype", native_enum=False),
        nullable=False,
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    notification_type: Mapped[NotificationType] = mapped_column(
        SAEnum(NotificationType, name="notificationtype", native_enum=False),
        nullable=False,
    )

    tier: Mapped[NotificationTier] = mapped_column(
        SAEnum(NotificationTier, name="notificationtier", native_enum=False),
        nullable=False,
    )

    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Soft reference to the entity this notification is about
    related_entity_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    related_entity_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # --- Relationships ---
    firm: Mapped["Firm"] = relationship("Firm", back_populates="notifications")
