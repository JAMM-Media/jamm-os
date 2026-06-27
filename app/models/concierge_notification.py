# app/models/concierge_notification.py

import uuid
from datetime import datetime, timezone

from typing import Optional
from sqlalchemy import Boolean, DateTime, Index, JSON, String, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class ConciergeNotification(Base):
    __tablename__ = "concierge_notifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    firm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("firms.id", ondelete="CASCADE"), nullable=False
    )
    trigger_type: Mapped[str] = mapped_column(String(60), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notification_metadata: Mapped[Optional[dict]] = mapped_column(JSON, name="metadata", nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_concierge_notification_firm_is_read", "firm_id", "is_read"),
        Index(
            "ux_concierge_notification_firm_trigger_unread",
            "firm_id",
            "trigger_type",
            unique=True,
            postgresql_where="is_read = false",
        ),
    )
