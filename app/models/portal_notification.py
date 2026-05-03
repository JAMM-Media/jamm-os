# app/models/portal_notification.py

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Boolean, DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class PortalNotification(Base):
    """
    In-app notification delivered to a client via the portal.

    notification_type controls the icon/action in the UI.
    related_entity_type + related_entity_id are soft references — no FK
    constraint so they survive if the referenced entity is deleted.
    """

    __tablename__ = "portal_notifications"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

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

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # "document_request" | "signature_needed" | "message" | "payment_due"
    # | "engagement_update" | "system"
    notification_type: Mapped[str] = mapped_column(String(50), nullable=False)

    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Soft reference — e.g. "engagement", "document_request", "invoice"
    related_entity_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    # FK-less soft reference, looked up at read time
    related_entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # --- Relationships ---
    firm: Mapped["Firm"] = relationship("Firm", back_populates="portal_notifications")
    client: Mapped["Client"] = relationship("Client", back_populates="portal_notifications")
